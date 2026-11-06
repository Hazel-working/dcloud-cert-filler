# -*- coding: utf-8 -*-
"""命令行入口。

  scan     扫描打包目录，列出发现的包与清单绑定状态（不解析、不开浏览器）
  check    解析与签名校验，不开浏览器（任何改动后先跑这个）
  probe    挂接浏览器，列出当前页所有输入框，用于校准 selectors.yaml
  console  生成 F12 可粘贴的 JS，零安装且不要求预先绑定 appid
  run      逐应用填写，每个应用填完暂停等人工确认，全程不点保存
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import ROOT, AppEntry, Settings, enabled_apps, load_settings
from .console_gen import write_payload, write_userscript
from .parser import CertInfo, public_fields

# 与 scripts/start_chrome_debug.bat 里的 %LOCALAPPDATA% 保持完全一致，
# 否则两边的 profile（用户数据目录）不同会找不到已登录的会话。
_LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
DEFAULT_PROFILE = str(_LOCAL_APPDATA / "DCloudFillerChromeProfile")
DEFAULT_CDP = "http://127.0.0.1:9222"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcf", description="DCloud 应用签名信息自动填写（只填不提交）"
    )
    parser.add_argument("--apps", default=None, help="应用清单，默认 config/apps.yaml")
    parser.add_argument("--selectors", default=None, help="选择器配置，默认 config/selectors.yaml")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="输出目录")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="扫描打包目录，列出发现的包与绑定状态")
    sub.add_parser("check", help="解析与校验，不打开浏览器")

    probe = sub.add_parser("probe", help="探测页面输入框结构")
    probe.add_argument("--driver", choices=("cdp", "persistent"), default="cdp")
    probe.add_argument("--cdp-url", default=DEFAULT_CDP)
    probe.add_argument("--profile-dir", default=DEFAULT_PROFILE)

    sub.add_parser("console", help="生成 DevTools Console 可粘贴的 JS（不要求 appid）")

    run = sub.add_parser("run", help="逐应用填写（不提交）")
    run.add_argument("--driver", choices=("cdp", "persistent"), default="cdp")
    run.add_argument("--cdp-url", default=DEFAULT_CDP)
    run.add_argument("--profile-dir", default=DEFAULT_PROFILE)
    run.add_argument("--screenshot", action="store_true", help="每个应用保存一张页面截图")
    run.add_argument("--no-pause", action="store_true", help="应用之间不暂停（仍然不提交）")
    return parser


def collect(settings: Settings) -> tuple[list[tuple[AppEntry, CertInfo]], list[str], list[str]]:
    """解析所有启用应用，返回 (可用条目, 硬错误, 跳过说明)。"""
    from .parser import parse_file

    entries: list[tuple[AppEntry, CertInfo]] = []
    errors: list[str] = []
    skipped: list[str] = []
    apps = enabled_apps(settings)
    if not apps:
        return entries, errors, ["应用清单里没有 enabled: true 的条目"]

    for app in apps:
        if not app.txt:
            skipped.append(f"{app.package}: 目录扫描未找到对应 txt，跳过")
            continue
        result = parse_file(app.txt)
        for warning in result.warnings:
            print(f"  [提示] {app.package}: {warning}")
        if not result.ok or result.info is None:
            for err in result.errors:
                errors.append(f"{app.package}: {err}")
            continue
        info = result.info
        if info.package != app.package:
            errors.append(
                f"{app.package}: txt 里的包名是 {info.package}，与清单不一致，"
                f"已跳过（防止把 A 应用的签名填进 B 应用）"
            )
            continue
        if not app.bound:
            skipped.append(
                f"{app.package}: 未绑定 appid（解析通过，Console 通道可用；Playwright 自动切页跳过）"
            )
        entries.append((app, info))
    return entries, errors, skipped


def cmd_scan(settings: Settings) -> int:
    print(f"扫描根目录：{settings.scan.root}")
    print(f"匹配规则：{settings.scan.txt_glob}，内容含 {settings.scan.content_marker}\n")
    print(f"发现 {len(settings.discovered)} 个含打包信息的包：")
    for package, path in settings.discovered.items():
        print(f"  {package:<30} -> {path}")

    print("\n清单绑定状态：")
    for app in settings.apps:
        state = app.appid if app.bound else "未绑定 appid"
        flag = "启用" if app.enabled else "停用"
        print(f"  [{flag}] {app.package:<30} {state:<20} {app.txt or '未找到 txt'}")

    if settings.unlisted:
        print("\n目录里有、但清单里没有的包。复制模板补进 bindings 即可扩展：")
        for package in settings.unlisted:
            print("  - appid: \"\"")
            print(f"    package: \"{package}\"")
            print("    name: \"\"")
            print("    enabled: true")
    return 0


def cmd_check(entries) -> None:
    print("\n=== 解析结果（未打开浏览器）===")
    for app, info in entries:
        label = app.name or app.package
        print(f"\n{label}  appid={app.appid or '(未绑定)'}  txt={app.txt}")
        for key, value in public_fields(info).items():
            print(f"  {key:<7}: {value}")
    if entries:
        print(f"\n共 {len(entries)} 个包解析通过。")
    else:
        print("\n没有解析到任何包。请先跑 python -m dcf scan，确认 scan.root 指向打包机上的证书输出目录。")


def cmd_probe(args, settings: Settings, entries) -> int:
    from playwright.sync_api import sync_playwright

    from .filler import app_url, attach_context, dump_inputs

    with sync_playwright() as pw:
        ctx, owned = attach_context(pw, args.driver, args.cdp_url, args.profile_dir)
        try:
            page = ctx.new_page()
            page.goto(app_url(settings, entries[0][0]), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(settings.wait_ms)
            data = dump_inputs(page)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            print(f"\n共 {len(data)} 个输入框。请把 placeholder 与 config/selectors.yaml 对照。")
            page.close()
        finally:
            if owned:
                ctx.close()
    return 0


def cmd_console(args, entries) -> int:
    out = Path(args.out)
    path = write_payload(entries, out / "console_payload.js")
    print(f"已生成：{path}")
    try:
        user_path = write_userscript(entries, out / "dcloud-filler.user.js")
        print(f"已生成：{user_path}  （油猴脚本，已内嵌数据）")
    except Exception as exc:
        print(f"[提示] 油猴脚本未生成：{exc}（不影响 Console 通道）")
    print("Console 用法：打开应用信息页 → F12 → Console → 全选粘贴 console_payload.js → 回车。")
    print("油猴用法：把 dcloud-filler.user.js 装进 Tampermonkey，之后打开应用页自动/一键填入。")
    print("两条通道都只填不保存，核对后手动提交。")
    return 0


def cmd_run(args, settings: Settings, entries) -> int:
    from playwright.sync_api import sync_playwright

    from .filler import attach_context, fill_app
    from .report import write_reports

    outcomes = []
    with sync_playwright() as pw:
        ctx, owned = attach_context(pw, args.driver, args.cdp_url, args.profile_dir)
        try:
            for index, (app, info) in enumerate(entries, start=1):
                print(f"\n=== [{index}/{len(entries)}] {app.name or app.package}（{app.appid}）===")
                shots = Path(args.out) / "screenshots" if args.screenshot else None
                try:
                    page, outcome = fill_app(ctx, settings, app, info, screenshot_dir=shots)
                except Exception as exc:
                    print(f"  [失败] {type(exc).__name__}: {exc}")
                    continue
                for r in outcome.results:
                    print(f"  {'OK  ' if r.ok else 'FAIL'} {r.label}: {r.detail}")
                outcomes.append(outcome)
                print("  脚本未点击保存。请在浏览器里核对后手动提交。")
                if not args.no_pause and index < len(entries):
                    input("  核对完成，按回车继续下一个应用（Ctrl+C 中止）...")
                page.close()
        finally:
            if owned:
                ctx.close()

    if outcomes:
        md, js = write_reports(outcomes, args.out)
        print(f"\n报告：{md}\n      {js}")
    failed = [o for o in outcomes if not o.ok]
    return 1 if failed else 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(args.apps, args.selectors)
    except Exception as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return 2

    for note in settings.notes:
        print(f"[扫描提示] {note}")

    if args.cmd == "scan":
        return cmd_scan(settings)

    entries, errors, skipped = collect(settings)
    for err in errors:
        print(f"[校验失败] {err}", file=sys.stderr)
    for item in skipped:
        print(f"[跳过] {item}")

    if args.cmd == "check":
        cmd_check(entries)
        return 1 if errors else 0

    if errors or not entries:
        print("存在解析失败的条目，为安全起见整体停手。先修正 txt，再跑一次 check。", file=sys.stderr)
        return 1

    if args.cmd == "console":
        return cmd_console(args, entries)

    bound = [(app, info) for app, info in entries if app.bound]
    if not bound:
        print("没有绑定 appid 的包，Playwright 通道无法自动切换应用页。", file=sys.stderr)
        print("两个选择：① 在 config/apps.yaml 补 appid 后重跑；② 用 python -m dcf console 走零配置通道。", file=sys.stderr)
        return 1

    if args.cmd == "probe":
        return cmd_probe(args, settings, bound)
    if args.cmd == "run":
        return cmd_run(args, settings, bound)
    return 2
