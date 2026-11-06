# -*- coding: utf-8 -*-
"""配置加载 + 打包目录自动发现。

可扩展性的核心在这里：新增一个包只要在 config/apps.yaml 的 bindings 里加一行，
txt 路径由 discover() 按「文件夹名 + 文件内容」自动找出，不依赖文件命名。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .parser import decode_bytes

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APPS = ROOT / "config" / "apps.yaml"
EXAMPLE_APPS = ROOT / "config" / "apps.example.yaml"
DEFAULT_SELECTORS = ROOT / "config" / "selectors.yaml"


@dataclass(frozen=True)
class ScanConfig:
    root: str
    txt_glob: str
    content_marker: str


@dataclass(frozen=True)
class AppEntry:
    appid: str
    name: str
    package: str
    txt: str
    enabled: bool = True

    @property
    def bound(self) -> bool:
        """是否绑定了 DCloud 的 appid（Playwright 自动切页需要）。"""
        return bool(self.appid.strip())


@dataclass(frozen=True)
class FieldSelector:
    label: str
    required: bool
    selectors: tuple[str, ...]


@dataclass(frozen=True)
class Settings:
    scan: ScanConfig
    apps: tuple[AppEntry, ...]
    discovered: dict[str, str]
    unlisted: tuple[str, ...]
    notes: tuple[str, ...]
    base_url: str
    wait_ms: int
    fields: dict[str, "FieldSelector"]

    @property
    def bound_entries(self) -> tuple[AppEntry, ...]:
        return tuple(a for a in self.apps if a.enabled and a.bound)


def discover(scan: ScanConfig) -> tuple[dict[str, str], list[str]]:
    """扫描 output 根目录，返回 (包名 -> txt 路径, 提示信息)。

    判定依据是内容而不是文件名：候选项含 content_marker（默认 SHA256）
    才算打包信息文件。所以「变更信息 / 変更信息 / 证书信息」等命名都能识别。
    同目录多个候选时取修改时间最新的一个，并给出提示。
    """
    root = Path(scan.root)
    found: dict[str, str] = {}
    notes: list[str] = []
    if not root.is_dir():
        return found, [f"扫描根目录不存在或不可访问：{root}"]

    for folder in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        package = folder.name
        try:
            candidates = list(folder.glob(scan.txt_glob))
        except OSError as exc:
            notes.append(f"{package}: 读取目录失败 {exc}")
            continue

        hits: list[Path] = []
        for path in candidates:
            if not path.is_file():
                continue
            try:
                text, _ = decode_bytes(path.read_bytes())
            except OSError as exc:
                notes.append(f"{package}: 读取 {path.name} 失败 {exc}")
                continue
            if scan.content_marker.lower() in text.lower():
                hits.append(path)

        if not hits:
            notes.append(f"{package}: 未找到含 {scan.content_marker} 的打包信息 txt，已跳过")
            continue
        hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        if len(hits) > 1:
            notes.append(f"{package}: 找到 {len(hits)} 个候选，采用最新的 {hits[0].name}")
        found[package] = str(hits[0])
    return found, notes


def load_settings(
    apps_path: str | Path | None = None,
    selectors_path: str | Path | None = None,
) -> Settings:
    apps_file = Path(apps_path) if apps_path else DEFAULT_APPS
    if not apps_file.is_file():
        raise FileNotFoundError(
            f"缺少应用清单：{apps_file}\n请先复制 config/apps.example.yaml 为 config/apps.yaml 并填写。"
        )
    sel_file = Path(selectors_path) if selectors_path else DEFAULT_SELECTORS

    raw_apps = yaml.safe_load(apps_file.read_text(encoding="utf-8")) or {}
    raw_sel = yaml.safe_load(sel_file.read_text(encoding="utf-8")) or {}

    scan_raw = raw_apps.get("scan") or {}
    scan = ScanConfig(
        root=str(scan_raw.get("root", "F:/生成证书/output")),
        txt_glob=str(scan_raw.get("txt_glob", "*")),
        content_marker=str(scan_raw.get("content_marker", "SHA256")),
    )
    discovered, notes = discover(scan)

    apps: list[AppEntry] = []
    for index, item in enumerate(raw_apps.get("bindings", []), start=1):
        package = str(item.get("package") or "").strip()
        if not package:
            raise ValueError(f"bindings 第 {index} 项缺少 package")
        txt = discovered.get(package, "")
        if not txt:
            notes.append(f"{package}: 清单里配置了，但目录扫描没找到对应 txt")
        apps.append(
            AppEntry(
                appid=str(item.get("appid") or ""),
                name=str(item.get("name") or ""),
                package=package,
                txt=txt,
                enabled=bool(item.get("enabled", True)),
            )
        )

    bound_ids = [a.appid for a in apps if a.bound]
    if len(bound_ids) != len(set(bound_ids)):
        raise ValueError("bindings 里存在重复 appid，会导致填错应用，请先清理。")
    packages = [a.package for a in apps]
    if len(packages) != len(set(packages)):
        raise ValueError("bindings 里存在重复 package，请先清理。")

    listed = set(packages)
    unlisted = tuple(p for p in discovered if p not in listed)

    fields: dict[str, FieldSelector] = {}
    for name, spec in (raw_sel.get("fields") or {}).items():
        fields[name] = FieldSelector(
            label=str(spec.get("label", name)),
            required=bool(spec.get("required", False)),
            selectors=tuple(spec.get("selectors", ())),
        )

    return Settings(
        scan=scan,
        apps=tuple(apps),
        discovered=discovered,
        unlisted=unlisted,
        notes=tuple(notes),
        base_url=str(raw_sel.get("base_url", "https://dev.dcloud.net.cn/pages/app/detail/info?appid={appid}")),
        wait_ms=int(raw_sel.get("wait_ms", 1500)),
        fields=fields,
    )


def enabled_apps(settings: Settings) -> tuple[AppEntry, ...]:
    return tuple(a for a in settings.apps if a.enabled)
