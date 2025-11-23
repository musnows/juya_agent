# Juya Agent

橘鸦视频监控 Agent，自动检测 B 站新视频并生成 AI 早报。

## 🎯 新功能：AI早报展示系统

我们新增了一个现代化的Web界面来展示AI早报内容！

### ✨ 特色功能
- 🎨 **科技杂志风格**：深色主题配合霓虹蓝色调
- 📱 **响应式设计**：完美适配桌面、平板和手机
- 🔄 **分页浏览**：每页显示10条早报，支持翻页查看
- 🔍 **详情查看**：点击早报卡片查看完整内容和相关链接
- 📊 **实时统计**：显示早报总数和资讯条数
- 🎬 **视频链接**：直接跳转到B站观看对应视频

### 🚀 快速启动
```bash
# 一键启动AI早报服务（包含前后端）
python run.py
```

访问 http://localhost:15000 即可查看精美的早报展示页面。

### 📁 新增文件结构
```
├── frontend/           # Web前端界面
│   ├── index.html     # 主页面
│   ├── styles.css     # 现代化样式
│   ├── script.js      # 交互逻辑
│   └── README.md      # 前端详细文档
├── backend/           # Python后端服务
│   ├── app.py         # Flask应用（集成前后端）
│   ├── requirements.txt # 依赖包
│   └── start_server.py # 启动脚本
└── run.py             # 一键启动脚本
```

### 🔧 API接口
访问 http://localhost:15000/api 可用接口：
- `GET /api/reports` - 获取所有早报
- `GET /api/reports/<id>` - 获取特定早报详情
- `GET /api/search?q=关键词` - 搜索早报
- `GET /api/stats` - 获取统计信息
- `GET /api/health` - 健康检查

详细说明请查看 [frontend/README.md](frontend/README.md)

---

## 功能

- 🎥 检查橘鸦 B 站账号的最新视频
- 📝 从视频字幕/简介提取新闻，生成结构化 Markdown 文档
- 📧 自动发送邮件通知
- ⏰ 支持定时任务（通过自然语言创建，如"每天早上9点检查新视频"）
- 💬 交互式对话界面
- 🚀 命令行工具（单次运行、指定BV号、定时监控）

## 技术栈

- OpenAI Agents SDK
- OpenAI API (gpt-4o-mini)
- schedule-task-mcp（定时任务）
- Python 3.13+

## 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install openai openai-agents python-dotenv requests
npm install -g schedule-task-mcp
```

同时还需要配置submodule的腾讯云语音SDK（必须初始化）

```sh
git submodule update --init
```

如需要使用腾讯云兜底逻辑，则必须配置腾讯云SDK里面的appid、密钥等环境变量，同时需要安装两个第三方工具用于下载和处理视频

- you-get: 用于下载B站视频，项目链接：<https://github.com/soimort/you-get>。可以使用`pip3 install you-get`或者`brew install you-get`安装。
- ffmpeg: 将视频转为mp3，用于请求腾讯云语音SDK。可以使用`brew install ffmpeg`或`sudo apt install -y ffmpeg`安装。

请先尝试使用you-get命令确认视频能够正常下载

```sh
you-get 'https://www.bilibili.com/video/BV1ufkzBvEug/'
```

若出现错误，请尝试使用chrome/edge的`Cookies txt`插件，导出B站的Cookies.txt文件，将该文件放入本项目的`config/cookies.txt`下，使用cookie重试

```sh
you-get 'https://www.bilibili.com/video/BV1ufkzBvEug/' --cookies config/cookies.txt
```

若使用cookies，还是无法下载视频，请在you-get仓库提交issue/pr咨询问题原因。

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# OpenAI API
OPENAI_API_KEY="your-api-key"
OPENAI_BASE_URL="https://ai.devtool.tech/proxy/v1"
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=8192 # 设置模型最大输出token，建议直接设置成模型可支持的输出token最大值，默认8192

# 邮件配置
EMAIL_FROM="your-email@163.com"
SMTP_PASSWORD="your-smtp-password"
SMTP_SERVER="smtp.163.com"
SMTP_PORT="465"
SMTP_USE_SSL="true"
EMAIL_TO="receiver@example.com"

# 定时任务配置
SCHEDULE_TASK_TIMEZONE="Asia/Shanghai"
SCHEDULE_TASK_DB_PATH="./data/schedule_tasks.db"
SCHEDULE_TASK_SAMPLING_TIMEOUT="300000"

# 腾讯云语言sdk
TX_APPID=xxx
TX_SECRET_ID=xxx
TX_SECRET_KEY=xxx
```

### 3. 配置 B 站 Cookies

创建 `config/cookies.json`：

```json
{
  "SESSDATA": "your-sessdata",
  "bili_jct": "your-bili-jct",
  "buvid3": "your-buvid3"
}
```

这里的三个字段都是B站Cookie的字段，打开B站后，F12进入开发者工具，点击`网络`选项窗，然后刷新页面，在data.bilibili.com的请求Cookie中，可以找到这三个字段，将对应字段的value拷贝到config中即可。

### 4. 运行

#### 交互式对话模式（推荐）
```bash
python chat.py
# 或者使用uv
uv run chat.py
```

#### 命令行模式
```bash
# 单次运行（获取最新AI早报）
uv run python main.py

# 显式指定单次运行
uv run python main.py --single

# 处理指定BV号视频
uv run python main.py --bv BV1234567890

# 定时运行（每10分钟检测一次）
uv run python main.py --loop

# 单次运行并发送邮件
uv run python main.py --single --send-email

# 定时运行并发送邮件
uv run python main.py --loop --send-email
```

## 使用示例

### 交互式对话模式
#### 基础功能
```
💬 你: 检查新视频
💬 你: 处理 BV1234567890
💬 你: 处理最新视频并发送邮件
```

#### 定时任务
```
💬 你: 每天早上9点检查新视频
💬 你: 查看我的定时任务
💬 你: 删除任务 task-xxx
```

### 命令行模式
#### 单次运行
```bash
# 获取最新AI早报并生成文档
uv run python main.py

# 获取最新AI早报并发送邮件
uv run python main.py --send-email
```

#### 指定视频处理
```bash
# 处理指定BV号视频
uv run python main.py --bv BV1S9yKB1Ekb

# 处理指定BV号视频并发送邮件
uv run python main.py --bv BV1S9yKB1Ekb --send-email
```

#### 定时监控
```bash
# 定时运行（每10分钟检测一次）
uv run python main.py --loop

# 定时运行并发送邮件通知
uv run python main.py --loop --send-email
```

#### 获取帮助
```bash
# 查看所有可用参数
uv run python main.py --help
```

## 项目结构

```
juya_agent/
├── main.py                  # 命令行入口（单次/BV号/定时模式）
├── chat.py                  # 交互式对话入口
├── pyproject.toml           # 项目配置和依赖
├── utils/                   # 工具和Agent定义
│   ├── juya_agents.py       # Agent 定义
│   ├── tools.py             # 工具函数
│   └── modules/             # 业务模块
│       ├── bilibili_api.py   # B站API封装
│       ├── subtitle_processor_ai.py  # AI字幕处理
│       └── email_sender.py   # 邮件发送
├── config/
│   └── cookies.json         # B站 cookies（需自行配置）
├── data/                    # 数据文件（已处理视频、定时任务数据库）
│   ├── processed_videos.json # 已处理视频记录
│   └── schedule_tasks.db    # 定时任务数据库
├── docs/                    # 生成的 Markdown 文档
├── .ai-docs/                # 说明文档
└── .env                     # 环境变量配置（需自行配置）
```

## 工作流程

### 交互式对话模式
```
用户输入 → orchestrator_agent
    ↓
1. check_new_videos（检查新视频）
    ↓
2. process_video（生成 AI 早报）
    ↓
3. send_email_report（发送邮件）
    ↓
返回结果
```

### 命令行模式
```
命令行参数 → JuyaProcessor
    ↓
根据模式执行：
- 单次运行：获取最新AI早报 → 处理视频 → 可选邮件
- BV号模式：处理指定视频 → 可选邮件  
- 定时模式：循环检测 → 处理新视频 → 可选邮件
    ↓
生成文档到 docs/ 目录
    ↓
记录处理状态到 data/processed_videos.json
```

## 开发

### 添加新工具

在 `utils/tools.py` 中定义：

```python
@function_tool
def your_tool(param: Annotated[str, "参数说明"]) -> YourResultModel:
    """工具描述"""
    return YourResultModel(...)
```

在 `utils/juya_agents.py` 中注册：

```python
orchestrator_agent = Agent(
    name="juya_orchestrator",
    model="gpt-4o-mini",
    tools=[check_new_videos, process_video, send_email_report, your_tool]
)
```

### 添加新的命令行功能

1. 在 `main.py` 的 `JuyaProcessor` 类中添加新方法
2. 在 `argparse` 配置中添加新的命令行参数
3. 在 `main()` 函数中处理新的运行模式

```python
def your_new_mode(processor: JuyaProcessor, args):
    """新的运行模式"""
    print("🚀 新运行模式")
    # 实现你的逻辑
    pass

# 在 main() 中添加
parser.add_argument('--your-flag', help='你的新参数')
```

## License

MIT
