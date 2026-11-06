# dcloud-cert-filler

## 这是什么

打包工具每打一个包，会在 `F:\数据\生成证书\output\` 下建一个以包名命名的文件夹，里面放一份 txt，记录包名、MD5、SHA1、SHA256 等证书信息。这些值需要人工填进 DCloud 开发者中心「应用信息」页的四个输入框。签名是几十组冒号分隔的十六进制串，记事本还会自动换行把它折断，手工复制既慢又容易填错；而页面红字明确提示，正式版的改动会影响广告、uni-push、微信打Key、一键登录等能力，填错的代价不低。

这个脚本做的事很克制：**读取原始 txt、还原被折行的签名、校验长度，然后自动填进表单，到此为止。它不点保存。** 填完由人核对一遍，自己点提交。同时支持多个包，逐个填写、逐个确认。

项目是**单机**的：整个文件夹拷到打包机，所有命令都在打包机上执行，不需要和别的电脑传数据，不需要后台服务，不需要常驻进程，跑完即退。打包机的 Windows 用户名是 Administrator。

### 该看哪一段

| 你是谁 | 从这里开始 |
| --- | --- |
| 第一次拿到项目、要在打包机上跑起来 | [一、运行者：从零到填完](#一运行者从零到填完) |
| 已经配好、只是今天要填几个包 | [二、日常填写的两条通道](#二日常填写的两条通道) |
| 要加新包、补 appid、DCloud 改版后修脚本 | [三、维护者：常见改动怎么做](#三维护者常见改动怎么做) |
| 想了解每个配置项的含义 | [四、两个配置文件](#四两个配置文件) |
| 想看目录结构、分层、排错 | [五](#五项目目录与分层) 及之后 |
| AI 助手接手改代码 | 先读 [`agent.md`](agent.md)，再读本文件 |

---

## 一、运行者：从零到填完

下面五步按顺序做一遍即可。每一步都写了「做到什么算成功」，不用猜。

### 步骤 1：给打包机配环境

这是唯一需要安装的东西，约两分钟。

| 项 | 要不要 | 说明 |
| --- | --- | --- |
| Python **3.10 或更高** | 要 | 代码用了 3.10 起支持的类型注解语法。去 python.org 下 64 位安装包，安装时**勾选 Add Python to PATH**（添加到环境变量） |
| `PyYAML` | 要 | 读两个 yaml 配置文件 |
| `playwright` | 要 | 挂接浏览器、填表（浏览器自动化框架） |
| `pytest` | 可选 | 只跑解析层单测才需要 |
| `playwright install chromium` | **不需要** | 主通道是 CDP（Chrome DevTools Protocol，Chrome 调试协议）挂接打包机上已有的 Chrome，不下载浏览器 |
| Node.js / 数据库 / 浏览器扩展 / 管理员权限 | 不需要 | 除安装 Python 那一步外都不需要 |

打开 PowerShell 或 CMD，进入项目目录：

```bat
python --version
python -m pip install -r requirements.txt
```

**如果 pip 报 `SSLEOFError` / `Could not fetch URL https://pypi.org/...`**：这表示打包机直连 PyPI 时 TLS（传输层安全协议）握手被网络中间设备切断，不是包不存在；末尾跟着的 `No matching distribution found` 也是连不上源的次生报错。换国内镜像即可：

```bat
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

仍报证书错误就再加 `--trusted-host pypi.tuna.tsinghua.edu.cn`；机器上开着 VPN（虚拟专用网络）或系统代理时，先关掉再试。想一次配好，执行 `python -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`，之后所有 `pip install` 自动走镜像。

打包机**完全不能联网**时：在有网的机器上执行 `pip download -r requirements.txt -d wheels -i https://pypi.tuna.tsinghua.edu.cn/simple`，把 `wheels` 文件夹拷过去，再执行 `python -m pip install --no-index --find-links=wheels -r requirements.txt`（两台机器的 Python 大版本尽量一致，PyYAML 有平台相关 wheel）。

**成功标志**：`python --version` 显示 3.10 及以上；pip 安装没有红色报错。如果提示「python 不是内部或外部命令」，说明装 Python 时没勾 Add Python to PATH，重装并勾上即可。

> 只有改用 `--driver persistent`（让脚本自己启动浏览器）时，才需要额外执行 `python -m playwright install chromium`。默认 `--driver cdp` 不需要。

### 步骤 2：把项目放到打包机

把 `dcloud-cert-filler` **整个文件夹**拷过去，建议放 `D:\dcloud-cert-filler`（避免中文或空格路径在命令行里要加引号）。项目里没有任何写死的用户名或安装路径，放哪都能跑；专用 Chrome 的 profile（用户数据目录）会按当前用户自动解析为 `C:\Users\Administrator\AppData\Local\DCloudFillerChromeProfile`。

**成功标志**：在项目目录下执行 `python -m dcf scan` 能打印出内容（哪怕提示目录不存在，也说明 Python 和依赖装好了）。

### 步骤 3：确认 5 个包都被认出来

```bat
python -m dcf scan
```

这个命令只扫目录、不解析签名、不开浏览器。它会列出每个包文件夹里找到的打包信息 txt、清单里各条的 appid 绑定状态；如果目录里出现了清单里没有的新包，还会把可直接复制的配置模板打印出来。

**成功标志**：5 个包都出现在「发现 N 个含打包信息的包」里，且各自有对应的 txt 路径。

如果提示「扫描根目录不存在」，先确认打包机上证书输出目录是不是 `F:\数据\生成证书\output`；盘符或目录名不同，改 `config/apps.yaml` 里 `scan.root` 这一行即可，不用改代码。

### 步骤 4：验收解析结果

```bat
python -m dcf check
python -m pytest tests -q
```

`check` 会把每个包解析出来的包名和三个签名打印出来，同时报告编码、折行、缺字段。`pytest` 跑的是解析层与目录发现的单测（纯逻辑，不碰浏览器）。

**成功标志**：每个包都打印出包名、SHA1、SHA256，且没有 `[校验失败]`；单测全绿。

这一步很重要：签名折行还原是本项目最容易出错的地方，先用 `check` 肉眼核对一遍再让它碰表单。任何一个包解析失败，后面的填写命令都会整体停手。

### 步骤 5：选一条通道填表

接着看第二节。**第一次建议先用通道 A**，它不需要补 appid、不需要启动调试浏览器，最快看到效果。

---

## 二、日常填写的两条通道

两条通道填的是同一份解析结果，安全边界也完全一致：只填、不保存，填完打印对照表让你核对。区别在于谁来切换应用页面。

### 通道 A：Console 通道（推荐先用，零配置）

适用：包还没补齐 appid、只想填一两个应用、或不想动浏览器启动方式。

1. 生成脚本：

   ```bat
   python -m dcf console
   ```

   会生成 `dist/console_payload.js`，里面内嵌了所有已解析的包。

2. 在打包机的 Chrome 里打开某个应用的「应用信息」页，按 F12 打开开发者工具，切到 Console（控制台）。

3. 把 `console_payload.js` 的内容全选复制、粘贴进去、回车。

4. 如果当前页面的 appid 已经绑定，脚本自动选中对应包；如果没绑定，会弹窗列出所有包的序号，**输入序号**选择要填的那个。

5. 脚本填入 4 个字段，用 `console.table` 打印「字段 / 结果 / 值」对照表。**看到「回读一致」才算填进去了。**

6. 回到页面人工核对，确认无误后**自己点保存**。切到下一个应用页，重复第 3 步即可。

> 它用原生 setter（属性赋值器）派发 `input` / `change` 事件（输入/变更事件），适配 SPA（单页应用）的受控输入框——直接改 `value` 在这种页面上是不生效的。

**如果表里出现「未找到输入框」**：说明 DCloud 页面真实的 placeholder 和脚本里的匹配规则对不上（现有规则是按截图推断的，还没在真实页面验证过）。不用装调试 Chrome，就在当前 Console 里粘这一行，能看到页面上所有输入框的真实属性：

```js
$$('input,textarea').map((e,i)=>i+': '+(e.placeholder||'(无)')+' | name='+(e.name||'')+' | id='+(e.id||'')).join('\n')
```

拿到真实值后二选一：

- 继续用通道 A：改 `dcf/console_gen.py` 里 `FIELDS` 的正则，重跑 `python -m dcf console` 生成新脚本；
- 换通道 B：改 `config/selectors.yaml` 即可，**不用改代码**，按下面通道 B 的步骤跑一次 `probe` 确认后就能用。

> 已知的不一致：通道 B 的定位规则外置在 `config/selectors.yaml`，通道 A 的定位正则目前写在 `dcf/console_gen.py`，两处还没共用同一份配置。只改版一次影响不大；如果 DCloud 频繁改版，建议把两者统一。

### 通道 B：Playwright 通道（自动切页，需要 appid）

适用：appid 已补齐、要一次性把多个应用挨个填完、需要截图和报告留痕。

前置：每个要填的包在 `config/apps.yaml` 里都有 appid（从 DCloud 应用信息页地址栏 `?appid=` 复制）。

1. 双击 `scripts/start_chrome_debug.bat`。它会启动一个**独立的专用 Chrome 窗口**（调试端口 9222）。第一次请在这个窗口里手工登录一次 DCloud，之后登录态会一直复用，**保持窗口不关**。

   > Chrome 136 及以上版本拒绝在默认用户数据目录上开启远程调试，所以必须用这个独立 profile。它不影响你日常的浏览器窗口。

2. 首次使用或 DCloud 改版后，先校准一次表单定位：

   ```bat
   python -m dcf probe --driver cdp
   ```

   命令会挂到那个专用 Chrome 上，打印当前页所有输入框的 placeholder（占位提示文本）。拿它和 `config/selectors.yaml` 对照，不一致就改 yaml，**不要改代码**。

3. 正式填写：

   ```bat
   python -m dcf run --driver cdp --screenshot
   ```

   脚本按清单逐个打开 `?appid=...` 页面 → 填 4 个字段 → 逐个回读确认 → 在终端打印对照表 → **暂停等你核对并手动点保存** → 按回车进入下一个应用。全部跑完在 `dist/` 生成 `report-*.md`、`report-*.json`，加了 `--screenshot` 还会存每个应用的页面截图。

   `--no-pause` 可以取消应用之间的回车确认，**仍然不会点保存**。`--driver persistent` 可让脚本自己启动同一个专用 profile，不必提前开 bat。

### 两条通道怎么选

| | 通道 A（Console） | 通道 B（Playwright） |
| --- | --- | --- |
| 需要 appid | 不需要，弹窗选包 | 需要 |
| 需要启动调试 Chrome | 不需要 | 需要 |
| 自动切换多个应用页 | 手动切，每页粘贴一次 | 自动 |
| 截图 / 报告留痕 | 无 | 有 |
| 适合 | 首次验证、临时填一两个 | 批量、需要留痕 |

---

## 三、维护者：常见改动怎么做

这一节给要维护项目的人。所有日常改动都只动 `config/*.yaml`，不需要碰 Python 代码。

### 新增一个包

打包工具新出一个包时，`output` 下会多一个文件夹。脚本按**文件内容**识别打包信息 txt（含 `SHA256` 标记），不看文件名也不看扩展名，所以文件名叫「变更信息」「证书信息」或别的都无所谓。

1. 先跑 `python -m dcf scan`。目录里有、清单里没有的包会被单独列出，并打印好可复制的模板。
2. 把模板粘进 `config/apps.yaml` 的 `bindings`，填 `package`（必须和文件夹名一致），`appid` 可以先留空。
3. 再跑一次 `scan` 确认状态变成「已列出」，跑 `check` 确认签名解析正确。

**注意**：没写进清单的包不会被静默填写，这是刻意设计，防止新包的签名填到错误的应用上。

### 补 appid

打开对应 DCloud 应用信息页，从地址栏复制 `?appid=` 后面的值（形如 `__UNI__1000B17`），填进该包 `bindings` 条目的 `appid`。补完后通道 B 就能自动切到这个应用页了；通道 A 本来就不要求 appid。

当前 5 个包里只有 `com.beikeyanshou.www` 已绑，其余 4 个待补。

### DCloud 改版、提示「未找到输入框」

跑 `python -m dcf probe --driver cdp`，把打印出来的真实 placeholder 对照 `config/selectors.yaml` 修改。每个字段可以写多个 CSS selector（CSS 选择器）候选，脚本按顺序尝试第一个命中的。

### 改字段映射或校验规则

- 页面字段、必填性、定位选择器 → `config/selectors.yaml`
- 要新增一个填写字段 → `selectors.yaml` 加一项，并同步 `dcf/parser.py` 的 `CertInfo` 与 `dcf/filler.py` 的取值字典、`dcf/console_gen.py` 的 `FIELDS`（这是少数需要改代码的改动）
- 签名分组数、字段别名、折行规则 → `dcf/parser.py`

### 改完怎么验证

```bat
python -m pytest tests -q
python -m dcf check
```

单测覆盖解析层（折行、截断、编码、敏感字段）和目录发现（内容识别、多候选取最新、未列出包、重复 appid）。改了填表逻辑，还要在打包机上用通道 A 做一次真实页面的回读验证。

---

## 四、两个配置文件

### `config/apps.yaml`

当前已按打包机情况填好，唯一的机器相关项是最上面的 `scan.root`。

```yaml
version: 2

scan:
  root: "F:/数据/生成证书/output"   # 证书输出根目录，每个包一个同名子文件夹
  txt_glob: "*"                     # 不挑扩展名，纯靠内容识别
  content_marker: "SHA256"          # 文件里含这个标记才算打包信息 txt

bindings:
  - appid: "__UNI__1000B17"         # DCloud 地址栏 ?appid= 的值；留空则只走通道 A
    package: "com.beikeyanshou.www" # 必须等于 output 下的文件夹名，也是要填进表单的包名
    name: "测试星泉"                 # 仅用于日志与报告，可留空
    enabled: true                   # 临时停用某个包改 false
```

现有 5 个包：

| 包名 | appid |
| --- | --- |
| `com.beikeyanshou.www` | `__UNI__1000B17` |
| `com.ritaiyanshou.www` | 待补 |
| `com.test.demo` | 待补 |
| `com.xingquangceshi.www` | 待补 |
| `com.yanshou.www` | 待补 |

`config/apps.example.yaml` 是带注释的模板，改乱了可以对照它恢复。这个文件不含密码，随项目一起拷到打包机。

### `config/selectors.yaml`

`base_url` 是应用信息页地址模板（`{appid}` 占位），`wait_ms` 是打开页面后等待 SPA（单页应用）渲染的毫秒数，页面慢可以调大。`fields` 下每项的 `required` 控制缺值时是报错还是跳过：MD5 设为可选，因为 DCloud 页面已标注「最新安卓平台已经不支持 MD5」。

字段固定映射：`包名 → *包名`、`SHA1 → *Android 应用签名SHA1`、`SHA256 → *Android 应用签名SHA256`。

---

## 五、项目目录与分层

```
dcloud-cert-filler/
├── agent.md                      给 AI Agent 的约束与设计边界
├── README.md                     本文件，给人看
├── requirements.txt
├── config/
│   ├── apps.yaml                 应用清单 + 扫描规则（机器相关，只改这里）
│   ├── apps.example.yaml         带注释的模板
│   └── selectors.yaml            表单定位（改版只改这里）
├── dcf/
│   ├── parser.py                 解析 + 签名校验：纯标准库、纯函数、可单测
│   ├── config.py                 配置加载 + 目录自动发现 discover()
│   ├── filler.py                 Playwright 填表通道
│   ├── console_gen.py            Console 通道脚本生成
│   ├── report.py                 Markdown 对照表 + JSON 留痕
│   ├── cli.py                    编排：扫描 → 解析 → 校验 → 填写 → 人工确认 → 报告
│   └── __main__.py               支持 python -m dcf
├── scripts/start_chrome_debug.bat 启动带调试端口的专用 Chrome
├── tests/                        解析层与目录发现单测 + 脱敏样例
└── dist/                         运行产物（脚本、报告、截图），可随时删除
```

分层原则：**解析层与填表层完全解耦**。`parser.py` 不依赖浏览器，只做「文本进、结构化数据出」；两条填表通道共享同一份解析结果，避免同样的折行规则维护两遍。`scan` / `check` / `console` 三条命令不加载 Playwright，最小环境也能跑解析。

| 命令 | 作用 | 是否需要浏览器 |
| --- | --- | --- |
| `python -m dcf scan` | 扫描目录、列出包与绑定状态 | 不需要 |
| `python -m dcf check` | 解析与签名校验 | 不需要 |
| `python -m dcf console` | 生成 F12 粘贴脚本 | 不需要 |
| `python -m dcf probe --driver cdp` | 打印页面真实输入框 | 需要 |
| `python -m dcf run --driver cdp` | 逐应用填写（不提交） | 需要 |

---

## 六、安全边界

| 约束 | 实现 |
| --- | --- |
| 不提交表单 | 两条通道都没有保存按钮的点击逻辑 |
| 不落敏感信息 | txt 里的 `密码`、`别名`、`证书文件`、`keystore` 及其续行在解析阶段直接丢弃，不进结果、日志或报告 |
| 防止填错应用 | 清单 appid / package 去重 → txt 包名必须等于清单包名 → 落地页 URL 的 appid 二次比对；未列进清单的包不参与填写 |
| 防止半截签名 | MD5 16 组 / SHA1 20 组 / SHA256 32 组，长度或字符不合就报错停手 |
| 可回溯 | `dist/report-*.md`、`report-*.json`、可选页面截图 |
| 正式版风险 | 页面红字提示改动影响广告 / uni-push / 微信打Key / 一键登录，因此保留人工确认 |

更多「不做什么」和给 AI 助手的执行边界写在 [`agent.md`](agent.md)。

---

## 七、排错

| 现象 | 处理 |
| --- | --- |
| `python 不是内部或外部命令` | 装 Python 时没勾 Add Python to PATH，重装并勾选 |
| pip 报 `SSLEOFError` / `Could not fetch URL https://pypi.org` / `No matching distribution found` | TLS 握手被切断，不是包缺失。换镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`；关掉 VPN / 系统代理再试；或用离线 wheel 安装（见步骤 1） |
| `扫描根目录不存在` | 改 `config/apps.yaml` 的 `scan.root`，确认打包机 F 盘路径 |
| `未找到含 SHA256 的打包信息 txt` | txt 不在包文件夹第一层，或内容不含 `SHA256` 标记；检查 `scan.root` / `scan.txt_glob` / `content_marker` |
| `SHA256 长度异常` | 记事本自动换行或复制不全。取原始 txt，不要从截图或 WPS 复制 |
| `包名格式不合法` / 包名不一致 | 文件夹名与 txt 里的包名不同，统一其中一处 |
| 通道 A 提示 `未找到输入框` | 用上面那行 Console 诊断命令看真实 placeholder，改 `dcf/console_gen.py` 的正则后重新生成脚本；或改用通道 B |
| 通道 B 提示 `未找到输入框` | 跑 `probe`，按真实 placeholder 修 `config/selectors.yaml`，不用改代码 |
| `回读不一致` | 页面组件未响应事件；优先改用 `run --driver cdp`（Playwright 的 `fill()` 已封装事件派发） |
| `没有绑定 appid 的包` | 补 appid，或改用 `python -m dcf console` |
| 调试端口连不上 | 确认 bat 启动的专用 Chrome 还开着，端口 9222 未被占用 |
| 登录态丢失 | 在专用 Chrome 里重新手工登录一次，脚本不负责登录 |
| 本机跑 `scan` 提示目录不存在 | 正常。项目是给打包机用的，本机没有 F 盘 |
