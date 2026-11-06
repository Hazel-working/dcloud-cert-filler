# -*- coding: utf-8 -*-
"""生成可直接粘贴进 DevTools Console（开发者工具控制台）的脚本。

零安装兜底通道，且不要求预先绑定 appid：脚本内嵌所有已解析的包，
页面 appid 能匹配就自动选，匹配不上就弹窗让使用者按序号选包。
解析仍由 Python 侧完成，避免同一套规则维护两份。
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import ROOT, AppEntry
from .parser import CertInfo

USERSCRIPT_TEMPLATE = ROOT / "userscript" / "dcloud-filler.user.js"
EMBED_PLACEHOLDER = "  var EMBEDDED_DATA = null;"

_TEMPLATE = r"""(function () {
  'use strict';
  var DATA = __DATA__;
  var match = location.href.match(/[?&]appid=([^&#]+)/);
  var appid = match ? decodeURIComponent(match[1]) : '';
  var row = appid ? DATA.byAppid[appid] : null;

  if (!row) {
    if (!DATA.list.length) {
      console.error('[DCloud filler] 清单里没有可用的包，请先跑 python -m dcf check。');
      return;
    }
    var lines = DATA.list.map(function (x, i) {
      return (i + 1) + '. ' + x.package + (x.name ? '  (' + x.name + ')' : '');
    }).join('\n');
    var pickHint = appid
      ? '当前 appid=' + appid + ' 未绑定包名。'
      : '当前 URL 里没有 appid。';
    var pick = window.prompt(pickHint + '\n请选择要填入的包（输入序号，从 1 开始）：\n' + lines, '1');
    if (!pick) { console.warn('[DCloud filler] 已取消。'); return; }
    var idx = parseInt(pick, 10) - 1;
    if (isNaN(idx) || !DATA.list[idx]) {
      console.error('[DCloud filler] 序号无效。');
      return;
    }
    row = DATA.list[idx];
  }

  var FIELDS = [
    { label: '包名',   re: /包名/,    required: true,  value: row.package },
    { label: 'SHA1',  re: /SHA1/i,   required: true,  value: row.sha1 },
    { label: 'MD5',   re: /MD5/i,    required: false, value: row.md5 },
    { label: 'SHA256', re: /SHA256/i, required: true,  value: row.sha256 }
  ];

  // Vue/React 受控组件必须走原生 setter（属性赋值器）并派发 input/change 事件
  function setNativeValue(el, value) {
    var proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // DCloud 页面是 uni-app 组件：输入框本身无任何属性，
  // 字段名在独立的 <uni-text>/<span> 节点里，因此必须按标签文本定位。
  function findInput(re) {
    var SEL = 'input.uni-input-input, input[type=text], textarea';
    var inputs = [].slice.call(document.querySelectorAll(SEL));
    var flat = [].slice.call(document.querySelectorAll('*'));
    function pos(el) { return flat.indexOf(el); }

    var leaves = [].slice.call(document.querySelectorAll('span, uni-text, label, text, view, div, td, th, p'))
      .filter(function (n) {
        if (n.children.length) return false;
        var t = (n.innerText || n.textContent || '').trim();
        // 排除顶部「离线打包 Key 规则」那段长说明（里面也含 包名 / SHA1）
        return t && t.length <= 60 && t.indexOf('规则') < 0 &&
               t.indexOf('名额') < 0 && re.test(t);
      });

    // 策略 1：向上找「恰好包含 1 个输入框」的祖先容器（通常是 form-item）
    for (var a = 0; a < leaves.length; a++) {
      var box = leaves[a].parentElement;
      for (var up = 0; up < 8 && box; up++, box = box.parentElement) {
        var inBox = box.querySelectorAll(SEL);
        if (inBox.length === 1) return inBox[0];
        if (inBox.length > 1) break;
      }
    }

    // 策略 2：DOM 顺序上离字段名最近的输入框
    var best = Infinity, hit = null;
    leaves.forEach(function (n) {
      var p = pos(n);
      inputs.forEach(function (inp) {
        var d = pos(inp) - p;
        if (d !== 0 && Math.abs(d) < best) { best = Math.abs(d); hit = inp; }
      });
    });
    if (hit) return hit;

    // 策略 3：保底，回到原生属性匹配
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      var hint = (el.placeholder || '') + ' ' + (el.name || '') + ' ' +
                 (el.id || '') + ' ' + (el.getAttribute('aria-label') || '');
      if (re.test(hint)) return el;
    }
    return null;
  }

  var report = [];
  var missing = 0;
  FIELDS.forEach(function (f) {
    if (!f.value) {
      report.push({ 字段: f.label, 结果: f.required ? '缺失' : '可选，已跳过', 值: '' });
      return;
    }
    var el = findInput(f.re);
    if (!el) {
      missing += 1;
      report.push({ 字段: f.label, 结果: '未找到输入框', 值: f.value.slice(0, 24) + '...' });
      return;
    }
    setNativeValue(el, f.value);
    var order = [].slice.call(document.querySelectorAll('input.uni-input-input, input[type=text], textarea')).indexOf(el);
    report.push({
      字段: f.label,
      结果: el.value === f.value ? '回读一致' : '回读不一致',
      目标: '#' + order,
      值: f.value.slice(0, 24) + '...'
    });
  });

  console.table(report);
  console.log('[DCloud filler] 已选包：' + row.package + (row.name ? '（' + row.name + '）' : '') + '，页面 appid：' + (appid || '无'));

  if (missing > 0) {
    var inputs = document.querySelectorAll('input, textarea');
    var diag = [];
    diag.push('页面 URL: ' + location.href);
    diag.push('页面标题: ' + document.title);
    diag.push('输入框总数: ' + inputs.length);
    for (var k = 0; k < inputs.length && k < 60; k++) {
      var item = inputs[k];
      diag.push('  [' + k + '] ' + item.tagName + ' type=' + (item.type || '') +
        ' ph="' + (item.placeholder || '') + '" name=' + (item.name || '') +
        ' id=' + (item.id || '') + ' aria=' + (item.getAttribute('aria-label') || '') +
        ' visible=' + !!(item.offsetWidth || item.offsetHeight));
    }
    var frames = document.querySelectorAll('iframe');
    var frameList = [];
    for (var j = 0; j < frames.length; j++) frameList.push(frames[j].src || '(no src)');
    diag.push('iframe 数: ' + frames.length + (frameList.length ? ' -> ' + frameList.join(' , ') : ''));
    diag.push('页面含「包名」文字: ' + (document.body.innerText.indexOf('包名') >= 0));
    diag.push('页面含「SHA256」文字: ' + (document.body.innerText.indexOf('SHA256') >= 0));
    console.warn('[DCloud filler] 有 ' + missing + ' 个字段未找到输入框。诊断信息（请整段复制给维护者）：\n' + diag.join('\n'));
    console.error('[DCloud filler] 填写未完成，请勿保存。');
  } else {
    console.warn('[DCloud filler] 已填入，未点击保存。请人工核对后手动提交。');
  }
})();
"""


def _data_dict(entries: list[tuple[AppEntry, CertInfo]]) -> dict:
    rows: list[dict] = []
    by_appid: dict[str, dict] = {}
    for app, info in entries:
        row = {
            "appid": app.appid,
            "name": app.name,
            "package": info.package,
            "sha1": info.sha1,
            "sha256": info.sha256,
            "md5": info.md5 or "",
        }
        rows.append(row)
        if app.bound:
            by_appid[app.appid] = row
    return {"byAppid": by_appid, "list": rows}


def build_payload(entries: list[tuple[AppEntry, CertInfo]]) -> str:
    return _TEMPLATE.replace("__DATA__", json.dumps(_data_dict(entries), ensure_ascii=False, indent=2))


def build_userscript(entries: list[tuple[AppEntry, CertInfo]]) -> str:
    """把真实数据内嵌进油猴脚本模板，生成开箱即用的 .user.js。"""
    template = USERSCRIPT_TEMPLATE.read_text(encoding="utf-8")
    if EMBED_PLACEHOLDER not in template:
        raise ValueError(f"用户脚本模板缺少占位行：{USERSCRIPT_TEMPLATE}")
    blob = json.dumps(_data_dict(entries), ensure_ascii=False, indent=2)
    return template.replace(EMBED_PLACEHOLDER, "  var EMBEDDED_DATA = " + blob + ";", 1)


def write_payload(entries: list[tuple[AppEntry, CertInfo]], out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_payload(entries), encoding="utf-8")
    return path


def write_userscript(entries: list[tuple[AppEntry, CertInfo]], out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_userscript(entries), encoding="utf-8")
    return path
