# agent.md — 给 AI Agent 的约束

本文件只供接手本项目的 AI Agent 阅读。给人看的说明、操作流程、排错一律在 `README.md`。
**修改代码前先读本文件**；改完代码若影响下面任一条，同步更新本文件与 `README.md` 对应章节。

> 命名说明：本文件按项目约定叫 `agent.md`。部分工具默认自动加载大写 `AGENTS.md`，
> 若需要自动加载，直接改文件名即可，内容不用改。

## 1. 部署拓扑（硬约束）

- **项目整个文件夹拷到打包机、在打包机上单机运行，不需要本机与打包机之间传数据、不需要后台服务、不需要两台机器协作。**
- 因此不得引入：消息队列、HTTP 服务、共享目录同步、文件传输脚本、跨机剪贴板、常驻守护进程，也不得把「从另一台电脑取 txt」写进设计。
- txt 数据源与 DCloud 浏览器页面都在**同一台打包机**。`config/apps.yaml` 的 `scan.root` 是打包机本地路径（`F:/生成证书/output`）。**注意 `数据 (F:)` 是 F 盘卷标、不是路径中的一级目录**，真实结构为 `F:\生成证书\output\<包名>\`，不要写成 `F:\数据\生成证书\output`（曾因此多写一层导致扫描到 0 个包）。
- 打包机环境极简：Python **3.9+**（打包机当前为 `3.9.0rc2` 预发布版）、`PyYAML`、`playwright`（`pytest` 仅单测用）。主通道 CDP（Chrome DevTools Protocol，Chrome 调试协议）挂接系统 Chrome，**不需要** `playwright install chromium`；只有 `--driver persistent`（持久化上下文）才需要。

## 2. 机器与用户

- 打包机 Windows 用户名是 **Administrator**；开发机是另一台机器，用户名与工作区路径都不相同。不要把开发机的路径、用户名、盘符假设写进代码或配置。
- 项目拷到打包机任意位置都要能跑。代码必须路径无关：用 `Path(__file__)`、`Path.home()`、`%LOCALAPPDATA%`；**禁止硬编码 `C:\Users\...`**。
- Chrome 专用 profile（用户数据目录）统一由 `%LOCALAPPDATA%` 解析，`dcf/cli.py` 与 `scripts/start_chrome_debug.bat` 必须一致，否则登录态找不到。Chrome 136+ 拒绝在默认 profile 上开远程调试，独立 profile 是必需的，不是可选优化。
- 盘符或目录名变化只应改 `config/apps.yaml`，不改代码。

## 3. 执行边界（最重要）

- **不要在开发机擅自执行 `pip install`、`pytest`、构建、部署、浏览器自动化等验证类命令。** 写交付文件、读文件、回答问题是允许的；运行与验证交给用户在打包机上做。
- 开发机没有 F 盘，在这里跑 `python -m dcf scan` 会打印「扫描根目录不存在」，**属预期行为**，不要为此改代码、改默认路径或造假的测试数据文件。
- 咨询类问题先给方案对比 + 推荐 + 待澄清点，再动手，不要直接开干。

## 4. 功能边界（不得突破）

- **只填、不提交**：任何通道都不得点击保存按钮。DCloud 页面红字提示正式版改动影响广告 / uni-push / 微信打Key / 一键登录，必须保留人工核对与确认环节。
- 不自动登录、不保存 Cookie 快照、不写任何账号密码。登录态复用人工已登录的浏览器。
- 不做截图 OCR（光学字符识别），只认原始 txt；截图里的签名被记事本自动换行折断，不可作为数据源。
- 不猜 `appid`。未绑定 appid 只能走 Console 通道的选包交互，或提示用户补，不得静默跳过或按名称推测。
- `密码`、`别名`、`证书文件`、`keystore` 及其续行在 `dcf/parser.py` 解析阶段丢弃，不得进入结果、日志、报告或 `dist/` 产物。
- 签名校验不通过必须停手，不得把半截值填进表单。

## 5. 代码约定

- 分层：`parser`（纯标准库、纯函数、可单测）→ `config`（清单 + 目录自动发现）→ `filler` / `console_gen`（填表通道）→ `cli`（编排 + 人工确认）→ `report`（留痕）。
- `scan` / `check` / `console` 三条命令**不得在模块导入期加载 Playwright**，以便最小环境也能跑解析。
- 配置外置：appid 映射、扫描规则、表单选择器都在 `config/*.yaml`，改配置不改代码。
- 扩展方式：新增包 = 在 `bindings` 加一行。txt 靠**内容**（含 `SHA256` 标记）发现，不靠文件名或扩展名；目录里有、清单里没有的包必须被 `scan` 报出且**不参与填写**；同目录多候选取修改时间最新的。
- 防串号三道不可删：`appid` / `package` 去重 → txt 里的包名必须等于清单包名 → 落地页 URL 的 `appid` 二次比对。
- 签名规范化：剔除所有非十六进制字符后按 MD5 16 组 / SHA1 20 组 / SHA256 32 组校验。记事本自动换行会从**字节中间**折断 SHA256，且折行行本身含冒号、易被误判成「字段行」——改解析器必须重跑 `tests/`。
- **通道 B（Playwright）** 的定位规则外置在 `config/selectors.yaml`，用 CSS selector（CSS 选择器）按 placeholder（占位提示文本）定位，可写多个候选，改版只改配置。
- **通道 A（Console）** 的定位正则目前硬编码在 `dcf/console_gen.py` 的 `FIELDS`，与 `selectors.yaml` **尚未共用**。这是已知不一致（见第 7 节），改版时两处都要考虑；若要统一，应让 `build_payload()` 接收 `settings.fields` 并把选择器内嵌进生成的 JS，同时保留 placeholder 正则作为兜底，不要只改一处。
- Windows 路径在 YAML 里统一正斜杠 `/`。Python **3.9+ 即可**——所有含类型注解的模块都启用了 `from __future__ import annotations`，`str | None` 等注解在 3.9 下不求值；不要在代码里新增未延迟求值的 3.10+ 语法。`.bat` 内只用 ASCII 文本，避免中文在非 UTF-8 控制台乱码。
- `3.9.0rc2` 是预发布版，部分包的 `Requires-Python >=3.9` 可能因 rc 版本号被拒；PyYAML 要求 `>=3.8` 不受影响。通道 A 只依赖 PyYAML，playwright/pytest 装不上不阻塞。
- 面向用户的文字里，技术英文术语首次出现要括号汉化。

## 6. 文档分工（不要复制粘贴大段重复内容）

- `README.md`：**给人看**。开头是文字介绍，紧接着是操作流程（运行者流程 / 维护者流程，每步要有文字说明与「看到什么算成功」），**最后**才写项目目录、分层、安全边界、排错。目标是「谁来运行代码、谁来维护这个项目都行」。
- `agent.md`：本文件，写约束、设计理由、执行边界、当前状态。
- 改代码影响流程 → 更新 `README.md`；改代码影响约束 → 更新本文件。两处只保留各自受众需要的信息。

## 7. 当前状态与未验证项

- 5 个包：`com.beikeyanshou.www`、`com.ritaiyanshou.www`、`com.test.demo`、`com.xingquangceshi.www`、`com.yanshou.www`。只有第 1 个已绑 `__UNI__1000B17`，其余 4 个 appid 待用户补。
- `config/selectors.yaml` 的 placeholder **按截图推断，未在真实 DCloud 页面验证**，须由用户在打包机跑 `python -m dcf probe` 校准；`dcf/console_gen.py` 的通道 A 正则同样未经真实页面验证，首次使用最可能卡在这里。
- 15:50 真实页面实测：Console 通道 4 个字段全部返回「未找到输入框」，解析层正常（4 个签名值都已输出），失败点只在 DOM（文档对象模型）定位。已给生成脚本内嵌失败诊断（输入框清单 / iframe / 页面文字），`findInput` 增加 `aria-label`，并修掉「已填入」在全部失败时仍无条件打印的误报；JS 语法用 `node --check` 校验过。根因待用户回传诊断，候选：只读态需点编辑、SPA 未渲染完、Console 上下文选到 iframe、DCloud 改版导致正则不匹配。
- 日志显示页面 appid 为 `__UNI__1D0D817`，与 `config/apps.yaml` 里绑定的 `__UNI__1000B17` **不一致**（后者是按截图抄的，可能抄错）。补 appid 前必须让用户从真实地址栏复制核对，不要沿用旧值。
- 16:02 真实 DOM（文档对象模型）诊断结果：`URL=https://dev.dcloud.net.cn/pages/app/detail/info?appid=__UNI__1D0D817`，**是 `detail/info` 不是 `list/info`**，已修 `config/selectors.yaml` 与 `dcf/config.py` 默认值。`INPUTS=7`、`IFRAMES=0`，且 7 个 input 的 placeholder / name / id / aria-label **全部为空**。
  - 结论：通道 A 按 placeholder 正则定位在这套页面上必然全失败，与网络、依赖、Python 版本无关。**不要继续在 placeholder 上调优**，改为按 label 文本、父容器结构或 input 顺序定位；需先拿到每个 input 的 `type` / 可见性 / `outerHTML` 片段，以及字段名标签的父元素结构。
  - 更要紧的是确认页面是否处于**编辑态**：若 `document.body.innerText` 里没有「包名 / SHA1」等字样，说明表单根本没渲染，要先点页面上的「修改 / 编辑」按钮。
- 通道 A / C 共用 `dcf/console_gen.py` 的定位逻辑；通道 B 仍单独用 `config/selectors.yaml`（基于 placeholder，对 uni-app 页面无效），**是待统一项，不是已实现能力**。
- 离线依赖发布在 GitHub Release **tag `offline-v1`**，两个资产：精简包 `dcloud-cert-filler-lite-bundle.zip`（761 KB，仅 PyYAML，**主推**）与完整包 `dcloud-cert-filler-offline-bundle.zip`（77 MB，含 Playwright/pytest）。77 MB 的包**不进 Git 历史**（>50 MB 会拖慢 clone）；精简包另复制一份在仓库 `offline/` 目录作为备用下载入口。README 步骤 1 有两个直链与 SHA-256。
- **通道 A（`scan` / `check` / `console`）唯一第三方依赖是 PyYAML**：`dcf/cli.py` 顶层只导入 `config` / `console_gen` / `parser`，`filler` 与 `report` 在 `probe` / `run` 里才延迟导入。不要给这三条命令新增第三方依赖，否则精简包失效。
- 若 `requirements.txt` 或支持的 Python 版本变更：重新生成两个包、用 `gh release upload offline-v1 ... --clobber` 覆盖资产，并同步更新 README 与 `offline/` 里的文件、链接和校验值。
- `tests/` 的解析层与目录发现单测已写，但**从未在开发机执行过**（见第 3 条）。
- `README.md` 与 `config/apps.yaml` 里的用户名、盘符描述以打包机 Administrator 为准。
- **16:30 新增通道 C：Tampermonkey（油猴用户脚本）**。模板 `userscript/dcloud-filler.user.js`；`python -m dcf console` 额外生成 `dist/dcloud-filler.user.js`（把模板里的 `var EMBEDDED_DATA = null;` 占位行替换成真实 DATA）。通用版靠页面「导入数据」粘 `console_payload.js` 全文并存 `GM_setValue`，内嵌版无需导入。
  - 约束：`console_gen.py` 的 `EMBED_PLACEHOLDER` 字符串必须与模板里的那一行完全一致，否则生成器失效（已用 try/except 容错，不影响 Console 脚本生成）。
  - 通道 A 与 C **共用 `findInput` 定位逻辑**（uni-app 标签文本三级策略），改定位必须同步两处并都用 `node --check` 校验 JS 语法。
  - 用户脚本不点保存、不联网、不上传数据；自动填入默认关闭，监听 SPA（单页应用）URL 变化自动重新识别 appid；数据只存本机 `GM_setValue` / localStorage。
  - 16:43 导入面板新增「选择文件」（File API，文件接口）：用户主动选 `dist/console_payload.js` 或内嵌版 `dcloud-filler.user.js` 即自动导入，不需要 `file://` 权限、不需要复制粘贴全文；`extractData` 同时识别 `var DATA =` 与 `var EMBEDDED_DATA =`，并用括号计数截取完整对象。面板状态显示数据来源文件名。
  - **浏览器沙箱禁止油猴脚本自动读取任意本地路径**（如 `D:\wcx\...\dist`）。`file://` + `@resource` + 「允许访问文件网址」理论可行但 Chrome 经常拦截，**不要作为默认方案**；把人工操作压到「数据变化时点一次选文件」即可。日常填写零命令。
- **17:00 新增 `scripts/refresh-dcloud-data.bat`**（用户要求「放桌面双击就刷新」）：自动 `pushd` 项目目录 → `python -m dcf console` → 覆盖生成 dist 两个文件 → 显示新文件大小/时间 → 把 `console_payload.js` 路径写进剪贴板（`<nul set /p | clip`，无尾随换行）→ `pause` 停留。失败时保留旧文件、不静默覆盖。
  - 顶部 `set "PROJ=D:\wcx\dcloud-cert-filler-main"` 是**唯一机器相关项**，路径变了改这一行；bat 内容全 ASCII 避免 CMD 编码问题，不依赖自身所在位置（可放桌面、可改名）。同一份文件也放在工作区根目录供直接交付。
