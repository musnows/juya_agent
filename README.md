# Juya Agent

橘鸦视频监控 Agent，自动检测 B 站新视频并生成 AI 早报。

## 功能

- 🎥 检查橘鸦 B 站账号的最新视频
- 📝 从视频字幕/简介提取新闻，生成结构化 Markdown 文档
- 📧 自动发送邮件通知
- ⏰ 支持定时任务（通过自然语言创建，如"每天早上9点检查新视频"）
- 💬 交互式对话界面
- 🚀 命令行工具（单次运行、指定BV号、定时监控）
- 📚 前后端展示（支持静态前端和动态前端，<https://ai.daliy.musnow.top>）

## 技术栈

- OpenAI Agents SDK（仅chat.py使用）
- OpenAI API (可使用第三方服务商)
- schedule-task-mcp（定时任务，仅chat.py使用）
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

同时还需要初始化submodule的腾讯云语音SDK

```sh
git submodule update --init
```

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

B站 Cookies 用于请求B站API获取视频信息（标题、简介、字幕等）

创建 `config/cookies.json`：

```json
{
  "SESSDATA": "your-sessdata",
  "bili_jct": "your-bili-jct",
  "buvid3": "your-buvid3"
}
```

这里的三个字段都是B站Cookie的Key，打开B站后，F12进入开发者工具，点击`网络`选项窗，然后刷新页面，在`data.bilibili.com`的请求Cookie中，可以找到这三个字段，将对应字段的value拷贝到config中即可。

### 4. 配置腾讯云语音SDK转写能力

默认情况下，早报是依赖于视频字幕或视频简介（橘鸦的视频基本没有B站生成的AI字幕，大概率使用视频简介生成），交付AI总结生成。为进一步提高生成的早报内容的有效性，引入了腾讯云SDK对视频进行语音转文字，交付AI一并处理。

当配置了腾讯云SDK转写能力时，早报处理分为三种情况：
1. 有字幕：只使用字幕生成早报
2. 无字幕，有简介：使用简介+语音转写生成早报
3. 无字幕，无简介：只使用语音转写生成早报
4. 无字幕，无简介，未配置腾讯云SDK：无法生成，跳过处理

如需要使用腾讯云语音转写逻辑，则必须在环境变量中配置腾讯云SDK里面的appid、密钥id、密钥key（在腾讯云控制台获取），同时需要安装两个第三方命令行工具用于下载和处理B站视频

- you-get: 用于下载B站视频，项目链接：<https://github.com/soimort/you-get>。可以使用`pip3 install you-get`或者`brew install you-get`安装。
- ffmpeg: 将视频mp4转为mp3，以mp3请求腾讯云语音SDK。可以使用`brew install ffmpeg`或`sudo apt install -y ffmpeg`安装。

安装完毕you-get后，请先尝试在命令行使用you-get命令确认B站视频能够正常下载

```sh
you-get 'https://www.bilibili.com/video/BV1ufkzBvEug/'
```

若出现错误，请使用chrome/edge的[Cookies txt](https://microsoftedge.microsoft.com/addons/detail/dilbcaaegopfblcjdjikanigjbcbngbk)插件，导出B站的Cookies.txt文件，将该文件放入本项目的`config/cookies.txt`下，使用cookie重试（项目运行时会自动检测是否有该文件并使用）

```sh
you-get 'https://www.bilibili.com/video/BV1ufkzBvEug/' --cookies config/cookies.txt
```

若使用cookies，还是无法下载视频，请在you-get仓库提交issue/pr咨询问题原因。

----

视频下载成功后，请使用ffmpeg命令确认其能够正常转为mp3文件，且mp3文件能够播放，声音正常。
```sh
ffmpeg -i "下载的mp4视频文件路径" -codec:a libmp3lame -b:a 128k -y output.mp3
```

**当视频无法正常下载、处理时，腾讯云语音SDK逻辑会失效，但不影响原有依赖于视频简介生成早报的逻辑**。

### 5. 运行

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

# 运行生成静态前端页面
uv run python main.py --loop --web
```

#### 前端展示页面

如下是使用前后端实现的展示页面能力，更推荐使用`main.py`的`--web`参数生成静态前端。

```sh
uv run web.py
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
    ↓
如果指定了--web参数，生成静态前端到 dist/ 目录下
```

## License

MIT
