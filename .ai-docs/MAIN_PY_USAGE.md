# Juya AI早报生成器使用说明
## 📖 概述

这是一个重构后的Juya AI早报生成器，将原本基于Agent的复杂架构改为直接的Python脚本，提供更简洁、高效的运行方式。

## 🚀 主要特性

- ✅ **无需Agent依赖**：直接业务逻辑实现，无需复杂的Agent框架
- ✅ **三种运行模式**：支持单次运行、指定BV号、定时运行
- ✅ **智能识别**：自动识别AI早报视频
- ✅ **重复检测**：避免重复处理已存在的文档
- ✅ **邮件支持**：可选的邮件发送功能
- ✅ **详细日志**：清晰的运行状态提示

## 📋 运行模式

### 1. 单次运行模式（默认）

获取最新的AI早报视频并生成报告。

```bash
# 直接运行（默认模式）
uv run python main.py

# 或显式指定
uv run python main.py --single

# 带邮件发送
uv run python main.py --single --send-email
```

### 2. 指定BV号运行模式

处理指定的BV号视频。

```bash
# 处理指定BV号
uv run python main.py --bv BV1PSCZB7EST

# 处理并发送邮件
uv run python main.py --bv BV1PSCZB7EST --send-email
```

### 3. 定时运行模式

每10分钟检测一次当日AI早报，如果发现新的早报且文档不存在则自动生成。

```bash
# 定时运行
uv run python main.py --loop

# 定时运行并发送邮件
uv run python main.py --loop --send-email
```

定时运行逻辑：
- 每10分钟检测一次
- 检查`docs/`目录下是否已存在包含当日日期的`YYYY-MM-DD`格式的md文件
- 如果已存在，跳过本次检测
- 如果不存在，搜索最新的AI早报视频并生成报告

## 🔧 命令行参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `--single` | 标志 | 单次运行模式（默认） |
| `--bv BV号` | 字符串 | 指定BV号运行模式 |
| `--loop` | 标志 | 定时运行模式 |
| `--send-email` | 标志 | 处理完成后发送邮件 |
| `--help` | 标志 | 显示帮助信息 |

## 📁 项目结构

```
juya_agent/
├── main.py                 # 主程序入口
├── modules/                # 业务模块
│   ├── bilibili_api.py      # B站API封装
│   ├── subtitle_processor_ai.py  # AI字幕处理
│   └── email_sender.py      # 邮件发送
├── config/
│   └── cookies.json         # B站cookies配置
├── data/                   # 数据文件
│   └── processed_videos.json # 已处理视频记录
├── docs/                   # 生成的Markdown文档
├── .env                    # 环境变量配置
└── .ai-docs/              # 说明文档
```

## ⚙️ 环境配置

确保以下配置文件存在且正确：

### 1. `.env` 文件
```env
# OpenAI API
OPENAI_API_KEY="your-api-key"
OPENAI_BASE_URL="https://ai.devtool.tech/proxy/v1"
OPENAI_MODEL=gpt-4o-mini

# 邮件配置（可选）
EMAIL_FROM="your-email@163.com"
SMTP_PASSWORD="your-smtp-password"
SMTP_SERVER="smtp.163.com"
SMTP_PORT="465"
SMTP_USE_SSL="true"
EMAIL_TO="receiver@example.com"
```

### 2. `config/cookies.json` 文件
```json
{
  "SESSDATA": "your-sessdata",
  "bili_jct": "your-bili-jct",
  "buvid3": "your-buvid3"
}
```

## 🤖 AI早报识别逻辑

系统通过以下规则识别AI早报视频：

1. **关键词匹配**：标题或描述中包含以下任一关键词
   - `ai`
   - `人工智能`
   - `早报`
   - `资讯`
   - `科技`
   - `技术`

2. **日期检查**：视频发布时间为当日

3. **文件名模式**：生成的文档格式为 `{BV号}_{日期}_AI早报.md`

## 📧 邮件功能

当使用 `--send-email` 参数时，系统会在处理完成后发送邮件：

- 邮件主题：`📺 橘鸦新视频：{视频标题}`
- 邮件内容：HTML格式的早报内容
- 附件提示：显示本地文档路径

## 🔄 与原Agent版本对比

| 特性 | Agent版本 | main.py版本 |
|------|-----------|-------------|
| 复杂度 | 高（Agent框架） | 低（直接逻辑） |
| 依赖 | OpenAI Agents SDK | 标准Python库 |
| 性能 | 较高开销 | 较低开销 |
| 调试 | 困难 | 简单 |
| 维护 | 复杂 | 简单 |
| 功能完整性 | ✅ | ✅ |

## 🚨 注意事项

1. **Cookies配置**：确保B站cookies正确且未过期
2. **网络环境**：需要稳定的网络连接访问B站和OpenAI API
3. **定时运行**：`--loop`模式会持续运行，使用`Ctrl+C`停止
4. **文件覆盖**：默认不会覆盖已存在的文档，如需强制重新生成请删除现有文档
5. **API限制**：注意B站API调用频率限制

## 🐛 故障排除

### 常见问题

1. **未找到AI早报视频**
   - 检查网络连接
   - 验证cookies是否有效
   - 确认当日是否发布了AI早报

2. **邮件发送失败**
   - 检查`.env`中的邮件配置
   - 验证SMTP服务器设置
   - 确认邮箱授权码正确

3. **权限错误**
   - 确保有写入`docs/`和`data/`目录的权限
   - 检查cookies文件是否存在

### 调试建议

- 观察控制台输出的详细日志
- 检查`data/processed_videos.json`中的处理记录
- 验证`docs/`目录中生成的文档文件

## 🎯 使用建议

- **日常使用**：建议使用`--loop`模式进行定时监控
- **测试验证**：先用`--bv`参数测试特定视频
- **自动化部署**：可以配合cron等工具实现更复杂的调度策略

这个重构版本保持了原有的所有功能，但大大简化了架构，提高了可维护性和运行效率。
