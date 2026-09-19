# 781 个 Kali 工具装进一个 20MB 的 exe：我做了一个离线极客版 Kali ToolKit

## 写在前面的废话

用 Kali 的人都懂一个痛点：工具实在太多了。

Kali 官方收录了七百多个工具，装完系统面对一长串名字——nmap、metasploit 这些熟面孔之外，还有大量你听都没听过的东西。每次想找个趁手的工具，要么去官网翻工具列表，要么现搜博客，网上搜出来的答案质量参差不齐，很多还是好几年前的旧文。

我就想：能不能把这些工具整理成一个可以本地查的"百科全书"？不要联网，不要装依赖，双击就能用，中文说明，连命令示例都给你准备好。

于是就有了这个项目——**Kali ToolKit**，一个把 781 个 Kali 工具、2053 条命令示例打包进单个 exe 的离线查询工具。

GitHub 地址：`https://github.com/sheyunyang/kali-toolkit`，欢迎 Star。

![主界面](screenshot.png)

## 它长什么样

打开程序，先是一段约 25 秒的开机动画——黑底、青色终端风字体、跑马灯进度条，算是给极客的一点仪式感（嫌长可以等 23 秒后它会自己关掉）。

主界面左侧是工具列表和搜索框，右侧是工具详情：中英文描述、所属分类、官方地址、man 手册页、关联工具，以及可以直接复制的命令示例。点一下复制按钮，命令就进剪贴板了。

支持暗色和亮色双主题，右上角一键切换。整个程序不联网也能跑，数据全在本地。

## 技术选型：怎么简单怎么来

这个项目我想控制复杂度，所以没有上 Electron 那种重方案。最终的技术栈是这样：

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | Vue 3 + 原生 CSS | 单文件 HTML 就能跑，Vue 通过 CDN 引入，不构建不打包 |
| 后端 | FastAPI + SQLite | Python 一把梭，SQLite 单文件数据库，免安装免配置 |
| 桌面壳 | pywebview | 用系统自带 WebView 渲染页面，比 Electron 轻量一个数量级 |
| 打包 | PyInstaller | 打成单 exe，用户拿到直接双击 |
| 数据 | Kali 官网爬取 + DeepSeek 翻译 | 官网工具列表是权威来源，AI 负责批量翻译 |

前后端通信就是最朴素的 HTTP：pywebview 启动一个 uvicorn 线程跑 FastAPI，前端 fetch `127.0.0.1:8000` 的接口。没有 WebSocket，没有鉴权，本地工具不搞那些花活。

### 后端：两个接口就够了

FastAPI 部分不到 150 行，核心就是搜索。数据库设计成五张表：

```sql
CREATE TABLE IF NOT EXISTS tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    subcategory TEXT,
    description_en TEXT NOT NULL,
    description_zh TEXT NOT NULL,
    official_url TEXT,
    manual_page TEXT,
    icon_emoji TEXT DEFAULT '🔧'
);
CREATE TABLE IF NOT EXISTS commands (...);
CREATE TABLE IF NOT EXISTS tags (...);
CREATE TABLE IF NOT EXISTS tool_tags (...);
CREATE TABLE IF NOT EXISTS relations (...);
```

`tools` 存工具本体，`commands` 存命令示例，`tags` / `tool_tags` 做多对多标签，`relations` 存"常与某工具配合使用"的关联关系。Schema 里其实还建了一张 FTS5 虚拟表加三个触发器，用来同步全文索引——这个后面说踩坑时再提。

暴露的接口只有两个：

```python
@app.get("/api/search")
def search(q: str = "", tag: str = None, limit: int = 2000):
    results = search_tools(q, tag, limit)
    return SearchResult(tools=results, total=len(results))

@app.get("/api/tags")
def get_all_tags():
    ...
```

`/api/search` 支持关键词 + 标签过滤，关键词同时匹配工具名、中文描述、英文描述。返回结果里把标签、关联工具、命令示例一次性带出来，前端不用发第二次请求。

### 前端：一个 HTML 文件

`frontend/index.html` 不到 700 行，Vue 3 走 CDN 引入，CSS 全部手写。暗色主题用 CSS 变量定义，亮色模式加一个 `body.light-mode` 类覆盖变量就完事：

```css
:root {
    --bg-primary: #0a0e17;
    --accent-cyan: #00f0ff;
    --border-glow: rgba(0, 240, 255, 0.15);
}
body.light-mode {
    --bg-primary: #f1f5f9;
    --border-glow: rgba(124, 58, 237, 0.2);
}
```

搜索框做了 300 毫秒防抖，输入停止后才发请求，避免每敲一个字母就打一次后端：

```javascript
async onSearch() {
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.doSearch(), 300);
},
```

细节上有几个我觉得做得还不错的地方：搜索结果变化时如果当前选中的工具已经不在列表里，会自动选中第一个结果，保证右侧详情区永远有内容；后端连不上时顶部状态灯会显示离线，每 10 秒自动重连检测一次。

### 桌面壳与打包

`app.py` 用 pywebview 创建窗口，同时在后台线程起 uvicorn。打包成 exe 时有个经典问题：PyInstaller 解压后资源在 `sys._MEIPASS` 临时目录，不是脚本所在目录，所以要这样处理：

```python
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))
```

最终产物是一个约 20MB 的 `KaliToolKit.exe`，首次启动需要十几秒解压，之后就是个绿色软件，拷到 U 盘里带走都行。

## 数据从哪来：爬虫 + AI 翻译的流水线

这是整个项目最重的部分，数据质量直接决定工具的可用性。

Kali 官网的工具页面是权威来源，但它的结构不太规整——有些工具有独立详情页，有些只有列表里的一行简介。我写的爬虫分两步走：先抓 sitemap 拿到全部工具列表，再逐个抓详情页。中间产物是好几份 JSON，命名从 `raw`、`cleaned`、`enriched` 到 `final`，一看就知道是反复清洗过的。

原始数据拿到后有两个大问题：

**一是描述全是英文。** 七百多个工具的简介靠人肉翻译不现实，我接了 DeepSeek API 做批量翻译，每批 20 条、间隔 1.5 秒，支持断点续传——跑到一半中断也不用从头再来。翻译质量比想象中好，术语基本不用人工改，只给了它一条 system prompt 约束："保留 SQL注入、XSS、Payload、C2、ARP 这类专业术语，不要过度意译。"

**二是数据脏。** 抓下来的 HTML 里混着标签、多余的空白、重复条目，还有些工具的详情页根本不存在。清洗脚本（`clean_data.py`、`clean_all.py`）前后跑了好多轮，中间甚至用上了 check 脚本抽查数据完整性。

最后写进 SQLite 前，又用 `gen_cmd_desc.py` 给常见工具补充了命令模板的中文说明，最终每个工具平均挂 2~3 条命令示例，全库 2053 条。

整套流水线跑下来，scripts 目录里堆了二十多个脚本。说实话看着乱，但每一步都留有中间产物，哪一环出问题都能单独重跑，这种"笨办法"在数据处理上反而是最稳的。

## 踩过的坑

### 1. FTS5 建了但没用上

Schema 里建了 FTS5 全文索引表，还配了三个触发器自动同步，结果 `search_tools()` 里用的还是 `LIKE`：

```python
sql += " AND (t.name LIKE ? OR t.description_zh LIKE ? OR t.description_en LIKE ?)"
```

原因很实际：781 条数据用 `LIKE` 毫秒级就返回了，FTS5 的分词对中英混合内容还要额外调，为了这点数据量引入复杂度不值得。**性能优化要对着真实数据量做**，这是我这次最深刻的体会。FTS5 的表先留着，等数据量上来或者要做命令全文检索时再切过去。

### 2. PyInstaller 打包后路径全崩

开发时一切正常，打成 exe 就找不到数据库了。排查半天才发现 frozen 状态下的资源路径问题，就是前面 `get_base_dir()` 那一段。打包类项目第一次发布前一定要做完整的"clean environment 测试"，别在自己开发机上测完就发。

### 3. pywebview 的启动体验

后端没起来之前前端打开就是白屏或者报错，体验很差。我的解法是加了一个纯前端的过渡页：窗口先显示一段终端风的开机动画，uvicorn 在后台线程悄悄启动，动画放完正好切到主界面。过渡页本身是个写死的 HTML 字符串，不依赖任何资源，稳。

### 4. 杀软误报

单文件 exe 加 PyInstaller 几乎是杀软误报的"标配组合"。这个没有技术解，只能在 README 里老实写明："如被杀软误杀请添加信任"。

## 目前的状态和后续计划

当前 v0.1.0，基础功能完整：781 个工具、8 大分类、中英文搜索、2053 条带中文说明的命令示例。

路线图里排着的：

- **v0.2.0** — 检查更新 + 分类优化
- **v0.3.0** — 工具收藏 + 搜索历史
- **v1.0.0** — 全平台支持 + 自动更新

最后照例放免责声明：本项目仅供授权的网络安全测试和教育使用，请遵守当地法律法规，别拿它干坏事。代码是 MIT 协议，随便用。

如果你在找一款离线的 Kali 工具速查手册，不妨下载试试。有 bug 或者想加功能，GitHub Issues 见。

## 相关链接

- GitHub 仓库：https://github.com/sheyunyang/kali-toolkit
- 下载地址：https://github.com/sheyunyang/kali-toolkit/releases
- Kali 官方工具列表：https://www.kali.org/tools/

---

*项目代码：MIT License · 作者：黑盒实验室*
