<div align="center">

<img src="icon.png" alt="Video-Distiller" width="128" height="128">

# Video-Distiller

### 把一小时的教程视频，蒸馏成一份可以对话的结构化笔记

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-Qt6-green.svg)](https://doc.qt.io/qtforpython-6/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](#-how-it-works) · [功能亮点](#-功能亮点) · [快速开始](#-快速开始) · [截图预览](#-截图预览)

</div>

---

## 2 小时的 GDC 技术演讲，你真的要逐字看完吗？

技术教程视频信息密度低、节奏不可控、关键知识点难以回溯。
**Video-Distiller** 把视频喂给 AI，自动提取语音转录和关键幻灯片，然后生成一份带时间戳的结构化 Markdown 笔记——完成后还能跟 AI 导师对话，随时追问细节。

**一句话：扔一个视频进来，拿走一份能读、能搜、能问的学习笔记。**

---

## ✨ 功能亮点

### 🎬 一键蒸馏管线

| 阶段 | 做什么 |
|------|--------|
| 媒体提取 | FFmpeg 抽取音频 + 采样帧 |
| 语音转录 | 本地 Whisper (GPU加速) / 云端 ASR |
| 智能选帧 | AI 根据转录语义挑选值得分析的帧，跳过冗余画面 |
| 图片理解 | Ollama 本地视觉模型 / 云端 Vision API 识别幻灯片内容 |
| AI 聚合 | 将幻灯片文字 + 转录文本蒸馏为结构化教育笔记 |

五步全自动，每步可单独重跑，中间产物全部保留。

### 💬 AI 导师对话

蒸馏完成后，所有笔记、幻灯片、转录文本自动注入对话上下文。

- 用自然语言追问教程中的任何细节
- "这个概念能不能再解释一下？"
- "第 30 分钟讲的内容和前面有什么关系？"
- 支持多 Provider：Gemini / OpenAI / Claude / Ollama

### 🏠 本地优先，隐私安全

- 语音转录：本地 faster-whisper + CUDA，数据不出机器
- 图片理解：Ollama 本地视觉模型，零上传
- 云端 AI 只接收纯文本（转录 + 幻灯片描述），不传图片
- 对话历史完全保存在本地

### 🎨 桌面级体验

- PySide6 原生 GUI，Light / Dark 主题
- 拖拽视频文件即可开始
- 实时进度反馈，每步耗时可见
- 可打包为 `.exe`，开箱即用

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) 已加入 PATH
- NVIDIA GPU（推荐，本地 ASR + 视觉模型用 CUDA 加速）

### 安装

```bash
git clone https://github.com/postgreenHuang/VideoDistiller.git
cd VideoDistiller
pip install -r requirements.txt
```

### 可选：本地 AI 加速

```bash
# 安装 Ollama，拉取视觉模型
ollama pull gemma3:12b

# faster-whisper 会自动使用 CUDA（如有）
```

### 运行

```bash
python main.py
```

### 打包为 exe

```bash
pyinstaller build.spec
```

---

## 📸 截图预览

> *蒸馏管线界面 — 五步状态一目了然*

> *AI 导师对话 — 基于蒸馏笔记随时追问*

---

## ⚙️ 支持的 AI 服务

| 功能 | 本地 | 云端 |
|------|------|------|
| 语音转录 | faster-whisper (CUDA) | DashScope (阿里云) |
| 图片理解 | Ollama (Gemma / LLaVA) | OpenAI Vision / Gemini |
| 文本生成 (笔记聚合/对话) | Ollama | OpenAI / Gemini / Claude |

所有 Provider 在设置中一键切换，Prompt 模板可自定义。

---

## 🏗️ 技术架构

```
视频 → FFmpeg(音频+帧) → Whisper(转录) → AI选帧 → 视觉模型(幻灯片)
                                                            ↓
                                              转录 + 幻灯片 → AI聚合 → 笔记.md
                                                                              ↓
                                                              对话系统(笔记+转录+幻灯片作为上下文)
```

核心技术栈：

- **PySide6** — Qt6 跨平台 GUI
- **FFmpeg** — 音频提取 + 视频抽帧
- **faster-whisper** — CTranslate2 加速的 Whisper，本地 GPU 转录
- **OpenCV** — 帧处理
- **Ollama** — 本地大语言模型 + 视觉模型
- **OpenAI / Google / Anthropic SDK** — 云端 AI 服务

---

## 📁 项目结构

```
VideoSteamer/
├── main.py                 # 入口
├── src/
│   ├── config.py           # 配置管理 (settings.json)
│   ├── pipeline.py         # 管线编排 (5 阶段 DAG 调度)
│   ├── media.py            # 音频提取 + 帧提取 (FFmpeg)
│   ├── frame_selector.py   # AI 智能选帧
│   ├── image_analysis.py   # 图片理解 (视觉模型)
│   ├── transcribe.py       # 语音转录
│   ├── chat.py             # 对话会话管理
│   └── gui/
│       ├── app.py          # 主窗口
│       ├── chat_widget.py  # 对话界面
│       ├── theme.py        # Light/Dark 主题
│       └── settings_dialog.py
└── output/{project}/       # 蒸馏产物
    ├── audio/ frames/ key_frames/
    ├── transcript/ notes/
    └── chat/
```

---

## 🤝 贡献

欢迎 Issue 和 PR！如果你有想法：

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交改动 (`git commit -m 'feat: add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

---

## 📄 License

MIT License — 自由使用、修改和分发。

---

<div align="center">

**把视频变成知识，而不是把时间变成进度条。**

Made with Python + PySide6

</div>
