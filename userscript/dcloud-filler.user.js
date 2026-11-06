// ==UserScript==
// @name         DCloud 应用签名自动填写
// @namespace    https://github.com/Hazel-working/dcloud-cert-filler
// @version      1.0.0
// @description  把打包机证书信息填入 DCloud 应用信息表单（只填不提交）
// @match        https://dev.dcloud.net.cn/pages/app/detail/info*
// @match        https://dev.dcloud.net.cn/pages/app/list/info*
// @grant        GM_setValue
// @grant        GM_getValue
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // python -m dcf console 生成 dist/dcloud-filler.user.js 时，会把这一行替换成真实数据。
  // 通用版保持 null，改用页面上的「导入数据」按钮把数据存进本机浏览器。
  var EMBEDDED_DATA = null;

  var STORE_KEY = 'dcf_data_v1';
  var AUTO_KEY = 'dcf_auto_v1';
  var SRC_NAME_KEY = 'dcf_src_name_v1';
  var SEL = 'input.uni-input-input, input[type=text], textarea';

  var FIELDS = [
    { key: 'package', label: '包名',   re: /包名/ },
    { key: 'sha1',    label: 'SHA1',  re: /SHA1/i },
    { key: 'md5',     label: 'MD5',   re: /MD5/i },
    { key: 'sha256',  label: 'SHA256',re: /SHA256/i }
  ];

  var store = {
    get: function (k, d) {
      try { if (typeof GM_getValue === 'function') return GM_getValue(k, d); } catch (e) {}
      try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; }
    },
    set: function (k, v) {
      try { if (typeof GM_setValue === 'function') { GM_setValue(k, v); return; } } catch (e) {}
      try { localStorage.setItem(k, v); } catch (e) {}
    }
  };

  function currentAppid() {
    var m = location.href.match(/[?&]appid=([^&#]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  // DCloud 是 uni-app 组件：输入框没有任何属性，字段名在独立的 <uni-text>/<span> 节点里。
  function findInput(re) {
    var inputs = [].slice.call(document.querySelectorAll(SEL));
    var flat = [].slice.call(document.querySelectorAll('*'));
    function pos(el) { return flat.indexOf(el); }

    var leaves = [].slice.call(document.querySelectorAll('span,uni-text,label,text,view,div,td,th,p'))
      .filter(function (n) {
        if (n.children.length) return false;
        var t = (n.innerText || n.textContent || '').trim();
        return t && t.length <= 60 && t.indexOf('规则') < 0 &&
               t.indexOf('名额') < 0 && re.test(t);
      });

    for (var a = 0; a < leaves.length; a++) {
      var box = leaves[a].parentElement;
      for (var up = 0; up < 8 && box; up++, box = box.parentElement) {
        var inBox = box.querySelectorAll(SEL);
        if (inBox.length === 1) return inBox[0];
        if (inBox.length > 1) break;
      }
    }

    var best = Infinity, hit = null;
    leaves.forEach(function (n) {
      var p = pos(n);
      inputs.forEach(function (inp) {
        var d = pos(inp) - p;
        if (d !== 0 && Math.abs(d) < best) { best = Math.abs(d); hit = inp; }
      });
    });
    if (hit) return hit;

    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      var hint = (el.placeholder || '') + ' ' + (el.name || '') + ' ' +
                 (el.id || '') + ' ' + (el.getAttribute('aria-label') || '');
      if (re.test(hint)) return el;
    }
    return null;
  }

  function setNativeValue(el, value) {
    var proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // 支持粘贴 console_payload.js 全文，也支持只粘 DATA 对象或纯 JSON
  function extractData(src) {
    src = String(src || '').trim();
    var start = -1;
    var m = src.match(/var\s+(?:EMBEDDED_)?DATA\s*=\s*/);
    if (m) start = src.indexOf('{', m.index + m[0].length);
    else if (src.charAt(0) === '{') start = 0;
    if (start < 0) throw new Error('没找到 DATA 对象，请粘贴 console_payload.js 全文');

    var depth = 0, inStr = false, esc = false;
    for (var j = start; j < src.length; j++) {
      var c = src.charAt(j);
      if (inStr) {
        if (esc) esc = false;
        else if (c === '\\') esc = true;
        else if (c === '"') inStr = false;
        continue;
      }
      if (c === '"') inStr = true;
      else if (c === '{') depth++;
      else if (c === '}') {
        depth--;
        if (depth === 0) return JSON.parse(src.slice(start, j + 1));
      }
    }
    throw new Error('DATA 对象不完整，确认复制了完整文件');
  }

  function loadData() {
    if (EMBEDDED_DATA && EMBEDDED_DATA.list) return EMBEDDED_DATA;
    try {
      var raw = store.get(STORE_KEY, '');
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function fill(row) {
    var lines = [];
    FIELDS.forEach(function (f) {
      var value = row[f.key] || '';
      if (!value) { lines.push(f.label + ': 跳过（无值）'); return; }
      var el = findInput(f.re);
      if (!el) { lines.push(f.label + ': 未找到输入框'); return; }
      setNativeValue(el, value);
      var ok = el.value === value;
      el.style.outline = ok ? '2px solid #16a34a' : '2px solid #dc2626';
      lines.push(f.label + ': ' + (ok ? 'OK' : '回读不一致'));
    });
    return lines;
  }

  var panel = document.createElement('div');
  panel.setAttribute('id', 'dcf-panel');
  panel.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:999999;width:290px;' +
    'background:#fff;border:1px solid #d0d7de;border-radius:10px;' +
    'box-shadow:0 6px 24px rgba(0,0,0,.18);font:13px/1.5 system-ui,sans-serif;' +
    'color:#24292f;padding:12px;box-sizing:border-box;';
  panel.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
      '<strong style="font-size:13px">DCloud 签名填写</strong>' +
      '<button id="dcf-toggle" style="border:0;background:none;cursor:pointer;font-size:16px">−</button>' +
    '</div>' +
    '<div id="dcf-body">' +
      '<div id="dcf-status" style="color:#57606a;font-size:12px;margin-bottom:8px"></div>' +
      '<select id="dcf-pick" style="width:100%;margin-bottom:8px;padding:4px"></select>' +
      '<div style="display:flex;gap:6px;margin-bottom:6px">' +
        '<button id="dcf-fill" style="flex:1;padding:6px;cursor:pointer">填入当前页</button>' +
        '<button id="dcf-import" style="flex:1;padding:6px;cursor:pointer">导入数据</button>' +
      '</div>' +
      '<label style="font-size:12px;display:block;margin-bottom:6px">' +
        '<input type="checkbox" id="dcf-auto"> 打开页面时自动填入' +
      '</label>' +
      '<div style="font-size:11px;color:#8c959f;margin-bottom:6px">只填不提交，核对后请手动点保存</div>' +
      '<pre id="dcf-log" style="white-space:pre-wrap;word-break:break-all;font:11px/1.5 monospace;' +
        'background:#f6f8fa;border-radius:6px;padding:8px;margin:0;min-height:18px"></pre>' +
    '</div>';
  document.body.appendChild(panel);

  function log(text) { panel.querySelector('#dcf-log').textContent = text; }

  panel.querySelector('#dcf-toggle').onclick = function () {
    var body = panel.querySelector('#dcf-body');
    var hidden = body.style.display === 'none';
    body.style.display = hidden ? '' : 'none';
    this.textContent = hidden ? '−' : '+';
  };

  function refresh() {
    var data = loadData();
    var sel = panel.querySelector('#dcf-pick');
    sel.innerHTML = '';
    if (data && data.list) {
      var selected = 0;
      var row = data.byAppid && currentAppid() ? data.byAppid[currentAppid()] : null;
      data.list.forEach(function (r, i) {
        if (row && r.package === row.package) selected = i;
        var o = document.createElement('option');
        o.value = String(i);
        o.textContent = (i + 1) + '. ' + r.package + (r.name ? ' (' + r.name + ')' : '');
        sel.appendChild(o);
      });
      sel.value = String(selected);
    }
    var srcName = store.get(SRC_NAME_KEY, '');
    panel.querySelector('#dcf-status').textContent =
      (data && data.list ? '已导入 ' + data.list.length + ' 个包' : '尚未导入数据') +
      (srcName ? ' · 来源 ' + srcName : '') +
      ' · appid ' + (currentAppid() || '无');
    panel.querySelector('#dcf-auto').checked = store.get(AUTO_KEY, '0') === '1';
  }

  function doFill(retry) {
    retry = retry || 0;
    var data = loadData();
    if (!data || !data.list || !data.list.length) { log('请先点「导入数据」'); return; }
    var idx = parseInt(panel.querySelector('#dcf-pick').value, 10);
    var row = data.list[idx];
    if (!row) { log('请先选择一个包'); return; }
    var lines = fill(row);
    var missing = lines.some(function (l) { return l.indexOf('未找到输入框') >= 0; });
    if (missing && retry < 3) {
      log('页面还在渲染，' + (retry + 1) + '/3 次重试…');
      setTimeout(function () { doFill(retry + 1); }, 900);
      return;
    }
    log('填入 ' + row.package + '：\n' + lines.join('\n') + '\n\n【未点击保存】请核对后手动提交');
  }

  panel.querySelector('#dcf-fill').onclick = function () { doFill(0); };
  panel.querySelector('#dcf-auto').onchange = function () {
    store.set(AUTO_KEY, this.checked ? '1' : '0');
  };

  panel.querySelector('#dcf-import').onclick = function () {
    var mask = document.createElement('div');
    mask.style.cssText = 'position:fixed;inset:0;z-index:1000000;background:rgba(0,0,0,.45);' +
      'display:flex;align-items:center;justify-content:center;';
    var box = document.createElement('div');
    box.style.cssText = 'width:640px;max-width:92vw;background:#fff;border-radius:10px;' +
      'padding:16px;box-sizing:border-box;font:13px system-ui,sans-serif;color:#24292f;';
    box.innerHTML =
      '<div style="font-weight:600;margin-bottom:6px">导入打包数据</div>' +
      '<div style="color:#57606a;font-size:12px;margin-bottom:8px">' +
        '推荐：直接选 dist/console_payload.js（或内嵌数据版 dcloud-filler.user.js），选完自动导入。' +
        '也可以把文件全文粘到下面。数据只存在本机浏览器，不上传。' +
      '</div>' +
      '<div style="margin-bottom:8px">' +
        '<input type="file" id="dcf-file" accept=".js,.json,.txt" style="font-size:12px;width:100%">' +
      '</div>' +
      '<textarea id="dcf-src" style="width:100%;height:210px;box-sizing:border-box;font:12px monospace"></textarea>' +
      '<div id="dcf-err" style="color:#dc2626;min-height:18px;margin-top:6px;font-size:12px"></div>' +
      '<div style="text-align:right;margin-top:6px">' +
        '<button id="dcf-cancel" style="padding:5px 14px">取消</button> ' +
        '<button id="dcf-ok" style="padding:5px 14px">保存</button>' +
      '</div>';
    mask.appendChild(box);
    document.body.appendChild(mask);

    function accept(src, name) {
      var data = extractData(src);
      if (!data.list || !data.list.length) throw new Error('文件里没有可用的包');
      store.set(STORE_KEY, JSON.stringify(data));
      store.set(SRC_NAME_KEY, name);
      mask.remove();
      refresh();
      log('已从 ' + name + ' 导入 ' + data.list.length + ' 个包，点「填入当前页」即可');
    }

    box.querySelector('#dcf-cancel').onclick = function () { mask.remove(); };
    box.querySelector('#dcf-ok').onclick = function () {
      try {
        accept(box.querySelector('#dcf-src').value, '粘贴内容');
      } catch (e) {
        box.querySelector('#dcf-err').textContent = e.message;
      }
    };
    box.querySelector('#dcf-file').onchange = function () {
      var f = this.files && this.files[0];
      if (!f) return;
      var reader = new FileReader();
      reader.onload = function () {
        var text = String(reader.result || '');
        box.querySelector('#dcf-src').value = text;
        try {
          accept(text, f.name);
        } catch (e) {
          box.querySelector('#dcf-err').textContent = e.message + '（也可手动粘贴内容后点「保存」）';
        }
      };
      reader.onerror = function () {
        box.querySelector('#dcf-err').textContent = '读取文件失败，请改用手动粘贴';
      };
      reader.readAsText(f, 'utf-8');
    };
  };

  refresh();
  if (store.get(AUTO_KEY, '0') === '1') setTimeout(function () { doFill(0); }, 1200);

  // DCloud 是 SPA（单页应用），切换应用可能不刷新页面，监听 URL 变化
  var lastUrl = location.href;
  setInterval(function () {
    if (location.href === lastUrl) return;
    lastUrl = location.href;
    setTimeout(function () {
      refresh();
      if (store.get(AUTO_KEY, '0') === '1') doFill(0);
    }, 900);
  }, 1000);
})();
