# agent.md — 给 AI Agent 的约束

本文件只供接手本项目的 AI Agent 阅读。给人看的说明、操作流程、排错一律在 `README.md`。
**修改代码前先读本文件**；改完代码若影响下面任一条，同步更新本文件与 `README.md` 对应章节。

> 命名说明：本文件按项目约定叫 `agent.md`。部分工具默认自动加载大写 `AGENTS.md`，
> 若需要自动加载，直接改文件名即可，内容不用改。

## 1. 部署拓扑（硬约束）

- **项目整个文件夹拷到打包机、在打包机上单机运行，不需要本机与打包机之间传数据、不需要后台服务、不需要两台机器协作。**
- 因此不得引入：消息队列、HTTP 服务、共享目录同步、文件传输脚本、跨机剪贴板、常驻守护进程，也不得把「从另一台电脑取 txt」写进设计。
- txt 数据源与 DCloud 浏览器页面都在**同一台打包机**。`config/apps.yaml` 的 `scan.root` 是打包机本地路径（`F:/数据/生成证书/output`）。
- 打包机环境极简：Python 3.10+、`PyYAML`、`playwright`（`pytest` 仅单测用）。主通道 CDP（Chrome DevTools Protocol，Chrome 调试协议）挂接系统 Chrome，**不需要** `playwright install chromium`；只有 `--driver persistent`（持久化上下文）才需要。

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
- Windows 路径在 YAML 里统一正斜杠 `/`。Python 3.10+。`.bat` 内只用 ASCII 文本，避免中文在非 UTF-8 控制台乱码。
- 面向用户的文字里，技术英文术语首次出现要括号汉化。

## 6. 文档分工（不要复制粘贴大段重复内容）

- `README.md`：**给人看**。开头是文字介绍，紧接着是操作流程（运行者流程 / 维护者流程，每步要有文字说明与「看到什么算成功」），**最后**才写项目目录、分层、安全边界、排错。目标是「谁来运行代码、谁来维护这个项目都行」。
- `agent.md`：本文件，写约束、设计理由、执行边界、当前状态。
- 改代码影响流程 → 更新 `README.md`；改代码影响约束 → 更新本文件。两处只保留各自受众需要的信息。

## 7. 当前状态与未验证项

- 5 个包：`com.beikeyanshou.www`、`com.ritaiyanshou.www`、`com.test.demo`、`com.xingquangceshi.www`、`com.yanshou.www`。只有第 1 个已绑 `__UNI__1000B17`，其余 4 个 appid 待用户补。
- `config/selectors.yaml` 的 placeholder **按截图推断，未在真实 DCloud 页面验证**，须由用户在打包机跑 `python -m dcf probe` 校准；`dcf/console_gen.py` 的通道 A 正则同样未经真实页面验证，首次使用最可能卡在这里。
- 两条填表通道的定位规则未共用一份配置（详见第 5 节），是待统一项，不是已实现能力。
- `tests/` 的解析层与目录发现单测已写，但**从未在开发机执行过**（见第 3 条）。
- `README.md` 与 `config/apps.yaml` 里的用户名、盘符描述以打包机 Administrator 为准。
