# am-living

> 一个由 AI 驱动的个人状态页，自动从对话记录中提取活动摘要，部署到 GitHub Pages / Cloudflare Pages。

**am-living** 不是传统的服务监控状态页。它连接你的 AI 助手，自动从日常对话中提取你在做什么，生成活动时间线，展示在简洁优雅的页面上。

## 特性

- 🤖 **AI 自动摘要** — 从对话记录中提取活动，不需要手动更新
- ⏱️ **定时自动更新** — cron 驱动，每 10 分钟推送最新状态
- 🩺 **Agent 心跳** — 监控 AI Agent 的在线状态
- ✅ **待办任务** — 自动读取待办清单
- 💬 **Agent 评价** — AI 给你的每日一句话
- 🎨 **简洁设计** — 暗色主题，移动端适配
- 🔧 **零服务端** — 纯静态页面，GitHub Pages 即可部署

## 快速开始

### 1. Fork 或 Clone

```bash
git clone https://github.com/yourname/am-living.git
cd am-living
```

### 2. 配置

```bash
cp config.env.example config.env
vim config.env
```

需要填写的最小配置：
```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxx    # GitHub Personal Access Token
GITHUB_REPO=yourname/your-repo   # 部署仓库
DISPLAY_NAME=YourName             # 页面显示名称
SESSIONS_DIR=/path/to/sessions    # OpenClaw session 目录
```

### 3. 部署前端

把仓库连接到 Cloudflare Pages 或 GitHub Pages，根目录指向仓库根目录即可。

### 4. 配置定时任务

```bash
crontab -e
```

```bash
# 每 10 分钟组装 status.json 并推送到 GitHub
*/10 * * * * /path/to/update-status.sh >> /path/to/update.log 2>&1

# 每 30 分钟用 AI 提取活动摘要
*/30 * * * * /usr/bin/python3 /path/to/gen-activity.py >> /path/to/gen-activity.log 2>&1
```

### 5. 添加头像（可选）

在仓库根目录放一张 `avatar.jpg` 作为你的头像。

## 项目结构

```
am-living/
├── index.html            # 前端页面
├── update-status.sh      # 组装 status.json + 推送 GitHub
├── gen-activity.py       # AI 活动摘要生成器
├── config.env.example    # 配置模板
├── .gitignore
├── README.md
└── data/
    ├── activity.json     # 活动摘要（gen-activity.py 自动生成）
    └── status.json       # 最终数据（update-status.sh 组装）
```

## 数据流

```
┌─────────────────────────────────────────────────────┐
│  gen-activity.py (每 30 分钟)                        │
│  读取 session transcripts → AI API → activity.json   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  update-status.sh (每 10 分钟)                       │
│  读取: activity.json + 心跳 + 待办 + 评价             │
│  组装: status.json → GitHub API 推送                  │
└──────────────────────┬──────────────────────────────┘
                       ↓
           Cloudflare Pages / GitHub Pages
                       ↓
                   浏览器访问
```

## 配置说明

### 基本信息

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `DISPLAY_NAME` | 页面标题和名称 | `User` |
| `DISPLAY_HANDLE` | @handle 显示 | `@user` |
| `FOOTER_TEXT` | 页脚文字 | `powered by am-living` |
| `COMMENT_AUTHOR` | Agent 评价署名 | `Agent` |

### Agent 配置

在 `config.env` 中，每行一个 Agent：

```env
AGENT_1=key|名称|头像文件|心跳文件路径
AGENT_2=key|名称|头像文件|心跳文件路径
```

- 留空则不显示 Agent 区块
- 心跳文件格式：`{"ts": "2026-05-25T12:00:00+08:00"}`
- 可以添加任意数量的 Agent

示例：
```env
AGENT_1=main|勘隙|kaltsit.png|/path/to/heartbeat.json
AGENT_2=sub|承隙|chengxi.png|/path/to/heartbeat2.json
```

### AI 配置

支持两个 AI 后端（优先 MiMo，DeepSeek 作为回退）：

```env
# MiMo（小米）
MIMO_KEY=your_mimo_key
MIMO_MODEL=mimo-v2.5-pro

# DeepSeek
DEEPSEEK_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-chat
```

### 可选数据源

```env
# 心跳文件路径
HEARTBEAT_KALTSIT=/path/to/heartbeat.json
HEARTBEAT_CHENGXI=/path/to/heartbeat2.json

# 待办文件（表格格式）
TODO_FILE=/path/to/TODO.md

# Agent 评价文件（一行文本）
COMMENT_FILE=/path/to/comment.txt
```

## 页面自定义

页面上的所有文字都从 `status.json` 的 `config` 字段读取，无需修改 HTML。只需在 `config.env` 中修改对应配置即可。

如果需要更深度的自定义，直接编辑 `index.html`，它是纯 HTML + CSS + JS，没有构建步骤。

## 技术栈

- **前端**: 纯 HTML/CSS/JS，无框架依赖
- **后端**: Bash + Python 脚本
- **AI**: MiMo / DeepSeek API
- **部署**: GitHub Pages / Cloudflare Pages
- **定时**: 系统 crontab

## 许可

MIT
