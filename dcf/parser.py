# -*- coding: utf-8 -*-
"""打包信息 txt 的解析与签名校验。

这一层是纯函数：只依赖标准库，不碰浏览器、不读网络、不写文件。
输入输出都是数据，所以能单独写单测，也能被 Playwright 通道和
DevTools Console 通道共用。

设计前提（来自实际截图）：
1. 记事本「自动换行」会把长签名折成多行，SHA256 尤其明显；
2. txt 里含 keystore 密码等敏感信息，绝不能出现在结果或日志里；
3. 校验不通过时宁可停手，也不能把半截值填进正式版表单。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# 签名分组数（每组两位十六进制）
HEX_GROUPS = {"md5": 16, "sha1": 20, "sha256": 32}

# 字段别名：key 归一化后匹配。归一化 = 去空白 + 小写 + 去分隔符号
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "package": ("包名", "packagename", "package", "applicationid", "应用包名"),
    "md5": ("android应用签名md5", "应用签名md5", "签名md5", "md5", "androidmd5"),
    "sha1": ("android应用签名sha1", "应用签名sha1", "签名sha1", "sha1", "androidsha1"),
    "sha256": ("android应用签名sha256", "应用签名sha256", "签名sha256", "sha256", "androidsha256"),
}

# 命中这些 key 的行及其续行一律丢弃，不进入结果
SENSITIVE_MARKERS = ("密码", "别名", "证书文件", "keystore", "password", "alias", "有效期", "生成时间")

_FIELD_LINE = re.compile(r"^\s*([^:：]{1,60})[:：]\s*(.*)$")
_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")


@dataclass(frozen=True)
class CertInfo:
    """允许被填进 DCloud 表单的四个字段，不含任何敏感信息。"""

    package: str
    sha1: str
    sha256: str
    md5: str | None = None


@dataclass(frozen=True)
class ParseResult:
    info: CertInfo | None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.info is not None and not self.errors


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """按 utf-8-sig / utf-8 / gb18030 顺序探测编码，返回 (文本, 编码名)。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


def is_sensitive_key(raw_key: str) -> bool:
    """判断是否为密码/别名/证书路径等敏感字段行。"""
    key = re.sub(r"[\s_\-（）()]", "", raw_key).lower()
    return any(marker in key for marker in SENSITIVE_MARKERS)


def normalize_key(raw_key: str) -> str | None:
    """把中英文混杂的字段名归一到 package/md5/sha1/sha256；敏感或未知返回 None。"""
    key = re.sub(r"[\s_\-（）()]", "", raw_key).lower()
    if any(marker in key for marker in SENSITIVE_MARKERS):
        return None
    for canonical, aliases in FIELD_ALIASES.items():
        if key in aliases:
            return canonical
    return None


def normalize_signature(raw: str, algo: str) -> tuple[str | None, str | None]:
    """把可能被折行、含全角字符的签名还原成 AA:BB:... 形式。

    做法：剔除所有非十六进制字符（冒号、空格、换行、分号等），
    再按两位切分。这样「...:1」被折成下一行「0;EC」也能拼回完整字节。
    返回 (规范值, 错误信息)。
    """
    if algo not in HEX_GROUPS:
        return None, f"未知签名算法: {algo}"
    hex_only = re.sub(r"[^0-9A-Fa-f]", "", raw).upper()
    expected = HEX_GROUPS[algo] * 2
    if len(hex_only) != expected:
        return None, (
            f"{algo.upper()} 长度异常：期望 {expected} 个十六进制字符，"
            f"实得 {len(hex_only)} 个（疑似折行缺失或复制不全）"
        )
    groups = [hex_only[i : i + 2] for i in range(0, expected, 2)]
    return ":".join(groups), None


def parse_text(text: str) -> ParseResult:
    """解析 txt 全文。字段行之后的非字段行视为该字段的续行（自动换行折行）。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    buffers: dict[str, list[str]] = {}
    current: str | None = None
    warnings: list[str] = []

    for lineno, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        match = _FIELD_LINE.match(line)
        if match:
            raw_key = match.group(1)
            key = normalize_key(raw_key)
            if key is None and not is_sensitive_key(raw_key):
                # 形如 "8D:07:27:..." 的签名折行也含冒号，不能当成新字段
                if current is not None:
                    buffers.setdefault(current, []).append(stripped)
                    warnings.append(f"第 {lineno} 行按签名折行拼接")
                continue
            current = key
            if key is None:
                continue
            buffers.setdefault(key, []).append(match.group(2))
            continue
        # 非字段行：分隔线、标题等；仅当上一个字段是目标字段时才当续行
        if current is not None:
            if set(stripped) <= {"-", "=", "_", "*", " "}:
                current = None
                continue
            buffers.setdefault(current, []).append(stripped)
            warnings.append(f"第 {lineno} 行按续行拼接（记事本自动换行）")

    errors: list[str] = []
    values: dict[str, str] = {}

    for algo in ("md5", "sha1", "sha256"):
        raw = "".join(buffers.get(algo, []))
        if not raw:
            if algo == "md5":
                warnings.append("未提供 MD5（DCloud 页面已标注安卓平台不再支持，属可选字段）")
                continue
            errors.append(f"缺少必填字段：Android 应用签名{algo.upper()}")
            continue
        normalized, err = normalize_signature(raw, algo)
        if err:
            errors.append(err)
        else:
            values[algo] = normalized  # type: ignore[assignment]

    package_raw = "".join(buffers.get("package", []))
    package = re.sub(r"\s+", "", package_raw)
    if not package:
        errors.append("缺少必填字段：包名")
    elif not _PACKAGE_RE.match(package):
        errors.append(f"包名格式不合法：{package!r}（应为 com.xxx.yyy 形式）")
    else:
        values["package"] = package

    if errors:
        return ParseResult(info=None, errors=tuple(errors), warnings=tuple(warnings))

    return ParseResult(
        info=CertInfo(
            package=values["package"],
            sha1=values["sha1"],
            sha256=values["sha256"],
            md5=values.get("md5"),
        ),
        warnings=tuple(warnings),
    )


def parse_file(path: str | Path) -> ParseResult:
    """读取 txt 并解析；编码探测结果作为 warning 返回，便于现场排查乱码。"""
    p = Path(path)
    if not p.is_file():
        return ParseResult(info=None, errors=(f"找不到打包信息文件：{p}",))
    text, encoding = decode_bytes(p.read_bytes())
    result = parse_text(text)
    return ParseResult(
        info=result.info,
        errors=result.errors,
        warnings=(f"文件编码：{encoding}",) + result.warnings,
    )


def public_fields(info: CertInfo) -> dict[str, str]:
    """输出可安全打印/写报告的字段字典（永远不含密码、别名、证书路径）。"""
    data = {"包名": info.package, "SHA1": info.sha1, "SHA256": info.sha256}
    if info.md5:
        data["MD5"] = info.md5
    return data
