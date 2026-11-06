# -*- coding: utf-8 -*-
"""浏览器填表通道（Playwright）。

只填写、不提交、不处理账号密码；登录态来自人工已登录的浏览器。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import BrowserContext, Page

from .config import AppEntry, Settings
from .parser import CertInfo


@dataclass(frozen=True)
class FieldResult:
    key: str
    label: str
    value: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class FillOutcome:
    app: AppEntry
    url: str
    results: tuple[FieldResult, ...]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)


def attach_context(pw, driver: str, cdp_url: str, profile_dir: str) -> tuple[BrowserContext, bool]:
    """返回 (上下文, 是否由调用方负责关闭)。

    cdp        : 挂接到已打开的专用 Chrome，不关闭用户浏览器与已有标签页。
    persistent : 脚本自己启动同一个专用 profile（用户数据目录），用完可关闭。
    """
    if driver == "cdp":
        browser = pw.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            raise RuntimeError("调试端口已连上但没有浏览器上下文，请先在专用 Chrome 里打开一个页面。")
        return browser.contexts[0], False
    if driver == "persistent":
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        return ctx, True
    raise ValueError(f"未知 driver（驱动方式）: {driver}")


def app_url(settings: Settings, app: AppEntry) -> str:
    return settings.base_url.format(appid=app.appid)


def dump_inputs(page: Page) -> list[dict]:
    """把当前页所有输入框列出来，用于校准 selectors.yaml。"""
    return page.eval_on_selector_all(
        "input, textarea",
        """els => els.map((e, i) => ({
            index: i,
            tag: e.tagName,
            type: e.type || '',
            placeholder: e.placeholder || '',
            name: e.name || '',
            id: e.id || '',
            cls: (e.className || '').toString().slice(0, 80)
        }))""",
    )


def fill_app(
    ctx: BrowserContext,
    settings: Settings,
    app: AppEntry,
    info: CertInfo,
    screenshot_dir: str | Path | None = None,
) -> tuple[Page, FillOutcome]:
    url = app_url(settings, app)
    page = ctx.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(settings.wait_ms)

    # 二次防串号：确认落地页的 appid 与清单一致
    query = parse_qs(urlparse(page.url).query)
    landed = (query.get("appid") or [""])[0]
    if landed and landed != app.appid:
        page.close()
        raise RuntimeError(
            f"页面 appid 与清单不一致：页面={landed}，清单={app.appid}，已停止填写。"
        )

    values = {
        "package": info.package,
        "sha1": info.sha1,
        "sha256": info.sha256,
        "md5": info.md5,
    }
    results: list[FieldResult] = []

    for key, spec in settings.fields.items():
        value = values.get(key)
        if not value:
            results.append(
                FieldResult(
                    key=key,
                    label=spec.label,
                    value="",
                    ok=not spec.required,
                    detail="未提供，可选项已跳过" if not spec.required else "缺少必填值",
                )
            )
            continue

        locator = None
        for selector in spec.selectors:
            try:
                candidate = page.locator(selector)
                if candidate.count() > 0:
                    locator = candidate.first
                    break
            except Exception:
                continue
        if locator is None:
            results.append(
                FieldResult(key, spec.label, value, False, "未找到输入框，请运行 probe 校准 selectors.yaml")
            )
            continue

        try:
            # fill() 内部会派发 input/change 事件（输入/变更事件），SPA 受控组件能收到
            locator.fill(value, timeout=10000)
            readback = locator.input_value()
            ok = readback == value
            results.append(
                FieldResult(key, spec.label, value, ok, "回读一致" if ok else f"回读不一致：{readback[:40]}")
            )
        except Exception as exc:
            results.append(
                FieldResult(key, spec.label, value, False, f"填写失败：{type(exc).__name__}: {exc}")
            )

    if screenshot_dir:
        out = Path(screenshot_dir)
        out.mkdir(parents=True, exist_ok=True)
        try:
            page.screenshot(path=str(out / f"{app.appid}.png"), full_page=True)
        except Exception:
            pass

    return page, FillOutcome(app=app, url=url, results=tuple(results))
