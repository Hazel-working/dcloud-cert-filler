# -*- coding: utf-8 -*-
"""执行留痕：Markdown 对照表 + 结构化 JSON，便于复核与回溯。"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .filler import FillOutcome


def write_reports(outcomes: list["FillOutcome"], out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    md_path = out / f"report-{stamp}.md"
    json_path = out / f"report-{stamp}.json"

    now = datetime.now()
    lines = [
        "# DCloud 应用信息填写记录",
        "",
        f"生成时间：{now:%Y-%m-%d %H:%M:%S}",
        "",
        "> 脚本只填写、不提交。下表用于人工核对后手动点击保存。",
        "",
    ]
    for outcome in outcomes:
        lines += [
            f"## {outcome.app.name or outcome.app.package}（{outcome.app.appid}）",
            "",
            f"- 页面：{outcome.url}",
            f"- 结论：{'全部回读一致' if outcome.ok else '存在异常，需人工处理'}",
            "",
            "| 字段 | 填入值 | 结果 | 说明 |",
            "| --- | --- | --- | --- |",
        ]
        for r in outcome.results:
            lines.append(
                f"| {r.label} | `{r.value}` | {'OK' if r.ok else 'FAIL'} | {r.detail} |"
            )
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "submitted": False,
        "apps": [
            {
                "appid": o.app.appid,
                "name": o.app.name or o.app.package,
                "url": o.url,
                "ok": o.ok,
                "fields": [asdict(r) for r in o.results],
            }
            for o in outcomes
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path
