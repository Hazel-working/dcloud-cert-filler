# -*- coding: utf-8 -*-
"""目录自动发现与清单加载的单测，用临时目录，不依赖打包机 F 盘。"""
import os
import time
from pathlib import Path

import pytest

from dcf.config import ScanConfig, discover, load_settings

FIXTURE = Path(__file__).parent / "fixtures" / "sample.txt"


def make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "output"
    (root / "com.beikeyanshou.www").mkdir(parents=True)
    (root / "com.beikeyanshou.www" / "随便起的名字.txt").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "com.ritaiyanshou.www").mkdir()
    (root / "com.ritaiyanshou.www" / "readme.txt").write_text("这里没有签名信息", encoding="utf-8")
    (root / "com.test.demo").mkdir()
    return root


def test_discover_uses_content_not_filename(tmp_path):
    root = make_tree(tmp_path)
    found, notes = discover(ScanConfig(str(root), "*.txt", "SHA256"))
    assert set(found) == {"com.beikeyanshou.www"}
    assert any("com.ritaiyanshou.www" in n for n in notes)
    assert any("com.test.demo" in n for n in notes)


def test_discover_picks_newest_candidate(tmp_path):
    root = make_tree(tmp_path)
    folder = root / "com.beikeyanshou.www"
    old = folder / "随便起的名字.txt"
    new = folder / "后来的.txt"
    new.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    now = time.time()
    os.utime(old, (now - 3600, now - 3600))
    os.utime(new, (now, now))

    found, notes = discover(ScanConfig(str(root), "*.txt", "SHA256"))
    assert Path(found["com.beikeyanshou.www"]).name == "后来的.txt"
    assert any("采用最新的" in n for n in notes)


def test_discover_missing_root_returns_note(tmp_path):
    found, notes = discover(ScanConfig(str(tmp_path / "nope"), "*.txt", "SHA256"))
    assert found == {}
    assert any("不存在" in n for n in notes)


def test_load_settings_reports_unlisted_and_missing_txt(tmp_path):
    root = make_tree(tmp_path)
    (root / "com.extra.www").mkdir()
    (root / "com.extra.www" / "info.txt").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    apps = tmp_path / "apps.yaml"
    apps.write_text(
        f"""
version: 2
scan:
  root: "{root.as_posix()}"
  txt_glob: "*.txt"
  content_marker: "SHA256"
bindings:
  - appid: "__UNI__1000B17"
    package: "com.beikeyanshou.www"
    name: "测试星泉"
    enabled: true
  - appid: ""
    package: "com.yanshou.www"
    name: ""
    enabled: true
""",
        encoding="utf-8",
    )
    settings = load_settings(apps_path=apps)
    assert len(settings.apps) == 2
    assert settings.bound_entries[0].package == "com.beikeyanshou.www"
    assert settings.apps[1].txt == ""
    assert settings.unlisted == ("com.extra.www",)
    assert any("com.yanshou.www" in n for n in settings.notes)


def test_duplicate_appid_is_rejected(tmp_path):
    root = make_tree(tmp_path)
    apps = tmp_path / "apps.yaml"
    apps.write_text(
        f"""
version: 2
scan:
  root: "{root.as_posix()}"
bindings:
  - appid: "__UNI__SAME"
    package: "com.beikeyanshou.www"
  - appid: "__UNI__SAME"
    package: "com.test.demo"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="重复 appid"):
        load_settings(apps_path=apps)
