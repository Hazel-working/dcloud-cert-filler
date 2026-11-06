# -*- coding: utf-8 -*-
"""解析层单测：只依赖标准库，不需要浏览器、不需要登录态。"""
from pathlib import Path

import pytest

from dcf.parser import (
    decode_bytes,
    normalize_signature,
    parse_file,
    parse_text,
    public_fields,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.txt"

SHA1 = "06:39:72:E8:9A:26:F7:41:91:7C:C6:20:E6:2A:A9:80:E9:A8:E6:8F"
MD5 = "B6:8F:8E:F4:0E:A8:F1:D5:23:CE:A9:05:8C:F8:7D:07"
SHA256 = (
    "8D:07:27:3F:27:7A:C4:1A:DA:C0:2E:EC:8D:A8:72:8F:"
    "90:89:F3:53:02:2A:CC:F0:8F:69:AE:F1:32:6A:10:EC"
)


def test_sample_parses_folded_package_and_split_byte():
    """包名被折行、SHA256 被从字节中间折断，都应完整还原。"""
    result = parse_file(FIXTURE)
    assert result.ok, result.errors
    assert result.info.package == "com.beikeyanshou.www"
    assert result.info.md5 == MD5
    assert result.info.sha1 == SHA1
    assert result.info.sha256 == SHA256


def test_sensitive_fields_never_appear_in_output():
    result = parse_file(FIXTURE)
    blob = str(public_fields(result.info)) + str(result.warnings) + str(result.errors)
    assert "123456" not in blob
    assert "keystore" not in blob.lower()
    assert "别名" not in blob


def test_incomplete_sha256_is_rejected():
    text = FIXTURE.read_text(encoding="utf-8").replace("0;EC", "0;E")
    result = parse_text(text)
    assert not result.ok
    assert result.info is None
    assert any("SHA256" in e for e in result.errors)


def test_missing_required_field_is_reported():
    text = FIXTURE.read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if "SHA1" not in line)
    result = parse_text(text)
    assert not result.ok
    assert any("SHA1" in e for e in result.errors)


def test_invalid_package_is_reported():
    text = FIXTURE.read_text(encoding="utf-8").replace(
        "包名: com.beikeyanshou.ww\nw", "包名: 123.bad\n"
    )
    result = parse_text(text)
    assert not result.ok
    assert any("包名" in e for e in result.errors)


def test_optional_md5_can_be_absent():
    text = "\n".join(line for line in FIXTURE.read_text(encoding="utf-8").splitlines() if "MD5" not in line)
    result = parse_text(text)
    assert result.ok, result.errors
    assert result.info.md5 is None
    assert any("MD5" in w for w in result.warnings)


def test_fullwidth_separator_is_tolerated():
    value, err = normalize_signature("aa：bb " + ":".join(["00"] * 14), "md5")
    assert err is None
    assert value.startswith("AA:BB:")
    assert len(value.split(":")) == 16


def test_fullwidth_letters_are_rejected_not_guessed():
    value, err = normalize_signature("ＡＡ：ＢＢ", "md5")
    assert value is None
    assert err is not None


def test_decode_gbk_fallback():
    raw = (
        f"包名: com.foo.bar\nAndroid 应用签名SHA1: {SHA1}\nAndroid 应用签名SHA256: {SHA256}"
    ).encode("gb18030")
    text, encoding = decode_bytes(raw)
    assert encoding == "gb18030"
    assert parse_text(text).ok


def test_wrong_group_count_is_rejected():
    value, err = normalize_signature(SHA1, "sha256")
    assert value is None
    assert err and "长度异常" in err


@pytest.mark.parametrize("algo,value", [("md5", MD5), ("sha1", SHA1), ("sha256", SHA256)])
def test_normalize_signature_roundtrip(algo, value):
    normalized, err = normalize_signature(value, algo)
    assert err is None
    assert normalized == value
