# Video-Distiller (VDC-Vault Edition)

将长技术演讲视频（如 GDC Vault）蒸馏为带时间戳、关键图表和核心干货的 Markdown 技术笔记。

## 目标用户

面向小白用户，本地桌面 GUI 应用，可打包为 .exe 双击运行。

## 架构：本地 vs 云端

```
完全本地（零 Token 消耗）:
  ① MP3 提取                → FFmpeg
  ② 帧提取 (可配置间隔/分辨率) → FFmpeg
  ③ 图片去重 (SSIM/pHash)    → OpenCV
  ④ 本地图片理解             → Ollama 视觉模型 (minicpm-v:8b)
  ⑤ 语音转录                 → faster-whisper (本地)

可选云端 AI（唯一需要 API 的步骤）:
  ⑥ AI 聚合推理 → 可配置 provider:
     - Gemini API (需要 API Key)
     - OpenAI API (需要 API Key)
     - Claude API (需要 API Key)
     - Ollama 本地模型 (零成本)
     - 手动模式 (导出中间结果，用户粘贴到 Gemini 网页版，再粘贴回来)
     → 输入为纯文本 (slides.json + transcript.json)，不含图片，token 消耗极低
```

## 技术栈

- **语言**: Python 3.10+
- **CLI**: argparse
- **GUI**: PySide6（Qt6 桌面原生界面）
- **打包**: PyInstaller（生成 .exe）
- **配置**: settings.json 持久化（含主题、AI Provider、术语词表、视觉模型 Prompt）
- **多媒体处理**: FFmpeg（subprocess 调用）
- **视觉去重**: OpenCV + scikit-image (SSIM) / pHash
- **语音转文字**: faster-whisper（本地 GPU）
- **AI 推理**: Provider 抽象层，支持多后端

## 项目结构

```
VideoSteamer/
├── src/
│   ├── __init__.py
│   ├── config.py           # 配置管理 (settings.json 持久化)
│   ├── theme.py            # 主题管理 (Light/Dark)
│   ├── media.py            # ① MP3 提取 + ② 帧提取 (FFmpeg)
│   ├── visual.py           # ③ 图片去重 (OpenCV SSIM/pHash)
│   ├── image_analysis.py   # ④ 本地图片理解 (Ollama 视觉模型)
│   ├── transcribe.py       # ⑤ 语音转录 (faster-whisper)
│   ├── ai_provider.py      # ⑥ AI Provider 抽象层
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── gemini.py       # Gemini API
│   │   ├── openai.py       # OpenAI API
│   │   ├── ollama.py       # Ollama 本地
│   │   └── manual.py       # 手动模式 (导出/导入)
│   └── gui/
│       ├── __init__.py
│       ├── app.py          # PySide6 主窗口 (4 Step Tabs)
│       ├── theme.py        # Light/Dark 主题 QSS 生成
│       ├── settings_dialog.py  # Settings 对话框 (通用/Provider/词表)
│       └── resources/      # 图标、样式表等资源
├── output/                  # 运行时输出 (gitignored)
│   └── {project_name}/
│       ├── audio/           # 提取的 MP3
│       ├── frames/          # 初始抽帧 (全部保留，永不删除)
│       ├── key_frames/      # 去重后的关键帧
│       ├── key_frames_v2/   # 第二轮去重结果 (非破坏性迭代)
│       ├── transcript/      # Whisper JSON 文稿
│       └── notes/           # 最终 Markdown 笔记
├── .env                     # API Keys (gitignored)
├── .env.example             # 示例配置
├── .gitignore
├── main.py                  # 入口 (启动 GUI)
├── build.spec               # PyInstaller 打包配置
├── requirements.txt
├── CLAUDE.md
└── run.bat                  # Windows 开发用启动脚本
```

## 工作流（4 个阶段）

### Phase 1: 媒体解耦 (media.py)

```
extract_audio(video_path, output_dir, sample_rate=16000) -> mp3_path
extract_frames(video_path, output_dir, fps=1, resolution="1920x1080") -> frames_dir
```

- subprocess 调用 FFmpeg，解析进度通过回调传递给 GUI
- 帧命名格式: `{minutes:02d}_{seconds:02d}_frame.jpg`
- GUI 提供: 视频路径选择、采样率下拉、抽帧间隔、目标分辨率

### Phase 2: 视觉蒸馏 (visual.py)

```
deduplicate(frames_dir, output_dir, method="ssim", threshold=0.95) -> key_frames_dir
```

- SSIM: 逐帧比较，相邻帧 SSIM > threshold 则跳过
- pHash: 备选方案，汉明距离 < threshold 则跳过
- **非破坏性**: 每次去重输出到新文件夹 (key_frames/, key_frames_v2/, ...)
- 支持多次迭代: 用户调阈值后重新运行，旧结果保留
- 用户可从原始 frames/ 手动复制遗漏的帧到 key_frames/
- 目标: 1h 视频 → 30-50 张核心 PPT 截图

### Phase 2.5: 本地图片理解 (image_analysis.py)

> 目的：用本地视觉模型提取关键帧中的文字和图表描述，生成纯文本 JSON，
> 避免将图片发送到云端 AI，大幅降低 token 消耗。

```
analyze_images(key_frames_dir, output_dir, model="minicpm-v") -> slides.json
```

- **调用方式**: Ollama REST API `POST http://localhost:11434/api/generate`（本地推理，零云端 token）
- **三步 Prompt 策略**: 每张关键帧调用 3 次 Ollama，每次只做一个任务（本地 7B-8B 模型一次只能做好一件事）:

| 调用 | Prompt 目的 | 默认 Prompt | 输出 |
|------|------------|-------------|------|
| 第1次 | 文字提取 (OCR) | "请仔细提取这张幻灯片中的所有文字内容，按原文逐字提取，不要遗漏。如果是代码保持格式，表格用 Markdown 还原。" | 原始文字 |
| 第2次 | 图表描述 | "这张幻灯片中是否有图表、架构图或流程图？描述元素和关系。如果没有输出：无图表。" | 图表描述 或 "无图表" |
| 第3次 | 标题概括 | "用一句话概括这张幻灯片的主题。不超过20个字。" | 简短标题 |

- **所有 Prompt 均在 Settings > 通用 中可编辑**，用户可按视频类型自定义
- **为什么不用单个 Prompt**: 7B-8B 模型同时做 OCR+图表描述+概括，三个都做不好；拆成三步每步质量都高
- **输出 slides.json**:
```json
{
  "slides": [
    {
      "timestamp": "05:12",
      "file": "05_12_frame.jpg",
      "title": "Nanite 虚拟几何管线",
      "text": "Virtual Geometry Pipeline\nLOD 0 → LOD 5\nCluster Size: 128 triangles\n...",
      "diagrams": "左侧: LOD 渐进示意图，5级 LOD 从高到低; 右侧表格: 128/256/512 triangle cluster 性能对比"
    }
  ],
  "model": "minicpm-v",
  "total_slides": 42
}
```

**硬件与模型推荐:**

当前硬件: i9-11代 / 64GB RAM / **RTX 3090 24GB VRAM**

24GB VRAM 可跑更大的模型，支持全流程 100% 本地化（包括 Phase 4 最终聚合）。

| 模型 | 拉取命令 | VRAM 占用 | 单帧耗时 | 特点 |
|------|---------|----------|---------|------|
| **minicpm-v** (首选) | `ollama pull minicpm-v` | ~5GB | ~30s | 中文 OCR 最强 |
| llava-llama3 | `ollama pull llava-llama3` | ~5GB | ~35s | 英文场景稳定，基于 Llama3 |
| qwen2-vl:7b | `ollama pull qwen2-vl` | ~5GB | ~30s | 原生中英双语 |
| **qwen2.5-vl:32b** (3090推荐) | `ollama pull qwen2.5-vl:32b` | ~18GB | ~60s | 图片理解质量最高 |
| **internvl2:26b** (3090可选) | `ollama pull internvl2:26b` | ~15GB | ~50s | 多模态推理强 |

**性能估算**: 40 张帧 × 3 次调用 × ~10s ≈ 20 分钟（纯本地，可后台运行）

**Token 节省**: 40 张图直接发云端 (~400k tokens) → 纯文本 slides.json (~10k tokens)，节省 97%

**Ollama 安装步骤**:
1. 下载安装 [ollama.com](https://ollama.com) (Windows 版)
2. `ollama pull minicpm-v`
3. 验证: `ollama run minicpm-v` 进入对话，发图片测试
4. REST API 默认地址: `http://localhost:11434`
5. 在 Settings > 通用 中配置地址和模型名

### Phase 3: 文本转录 (transcribe.py)

```
transcribe(audio_path, output_dir, model="large-v3", language=None, vocabulary=None) -> transcript.json
```

- faster-whisper 本地运行，CPU 用 int8，GPU 用 float16
- **自定义术语词表 (initial_prompt)**:
  - Whisper 原生支持 `initial_prompt` 参数，注入技术术语列表
  - 显著提升技术术语准确率（如 "Nanite"、"Lumen"、"PBR"、"ECS"）
  - 用户可在 GUI 中编辑术语词表，或从预设模板选择（GDC/Unreal/Unity 等）
  - 流程: 用户输入术语 → 拼接为 initial_prompt → 传给 Whisper
- **AI 上下文修正** (与 Phase 4 联动):
  - Phase 4 AI 聚合时，结合 PPT 截图中的视觉信息自动纠正转录错误
  - 例如: 转录写 "nanight"，PPT 上有 "Nanite"，AI 自动对齐
  - 蒸馏 Prompt 中已包含"根据图片修正转录文本中的技术术语"指令
- 输出 JSON 格式:
```json
{
  "segments": [
    {"start": 0.0, "end": 180.5, "text": "..."},
    {"start": 180.5, "end": 360.2, "text": "..."}
  ],
  "metadata": {
    "model": "large-v3",
    "language": "en",
    "initial_prompt": "Nanite, Lumen, MetaHuman, PBR, ECS..."
  }
}
```
- 按配置的切片长度（默认 3 分钟）自动分段
- GUI 提供: 模型选择、语言选择、切片长度、术语词表编辑器

### Phase 4: AI 聚合推理 (ai_provider.py + providers/)

```
class AIProvider(ABC):
    def generate_notes(slides_json, transcript_json, prompt) -> str
```

- **输入**: slides.json（Phase 2.5 图片理解结果，纯文本）+ transcript.json（Phase 3 转录，纯文本）
- 不再发送图片到云端 AI，全部为纯文本输入，大幅降低 token 消耗
- **手动模式** (无 API Key 时的默认方案):
  1. 工具导出 slides.json + transcript.json 合并后的结构化 Markdown
  2. 用户复制到 Gemini Pro 网页版
  3. 用户将 AI 返回的结果粘贴回工具的文本框
  4. 工具保存为最终 Markdown 笔记 (.md)

- **API 模式** (有 API Key 时):
  - 自动将 slides.json + transcript.json 发送给选定的 Provider
  - Prompt 策略: 结合图片文字描述和语音解释，输出结构化笔记

## GUI 界面设计

```
Video-Distiller v1.0

📹 视频路径: [____________]  [浏览...]
📁 输出目录: [____________]  [浏览...]

━━━ Step 1: 媒体提取 ━━━
音频采样率: [16000 ▼]       提取MP3:  [开始提取]
抽帧间隔:   [1 秒/帧 ▼]     分辨率:   [1920x1080 ▼]
                                      抽取帧:   [开始提取]
状态: ✅ MP3已提取 | ⏳ 帧提取中... 1200/3600

━━━ Step 2: 图片去重 ━━━
源文件夹:   [frames ▼]
算法:       [SSIM ▼]        阈值:     [0.95] ━━○━━  [开始去重]
结果: 从 3600 帧中筛选出 47 张关键帧
[查看关键帧画廊]  [重新去重(保留之前结果)]

━━━ Step 3: 语音转录 ━━━
模型:       [large-v3 ▼]    语言:     [自动检测 ▼]
切片长度:   [3分钟 ▼]                  [开始转录]
状态: ✅ 转录完成 (23 段, 15234 字)

━━━ Step 4: AI 聚合 ━━━
AI Provider: [手动模式 ▼]
  → Gemini API / OpenAI / Claude / Ollama / 手动
[生成笔记] / [导出中间数据供手动使用]

━━━ 输出 ━━━
📄 [下载 Markdown 笔记]  📊 [查看处理报告]
```

## 蒸馏 Prompt（技术演讲专用）

Phase 4 AI 聚合时使用。输入为纯文本（slides.json + transcript.json），不含图片。

```
你是一个技术专家。我会给你提供一系列演讲幻灯片的文字描述和对应的语音转录。
请执行以下任务：
1. 根据内容变化划分章节
2. 结合幻灯片中的数据说明技术细节
3. 提取讲者提到的核心数值、性能指标或经验教训
4. 根据幻灯片文字修正转录文本中的术语错误
5. 输出格式为 Markdown，包含 [时间戳][章节名][核心干货][截图引用]
```

所有 Prompt（视觉分析 Prompt + 蒸馏 Prompt）均可在 Settings > 通用 中自定义。

## 语音识别准确率策略

采用**双层修正**策略，在不增加 API 成本的前提下最大化转录准确率：

**第一层：转录时注入术语 (initial_prompt)**
- faster-whisper 支持 `initial_prompt`，传入术语列表后 Whisper 倾向输出这些词
- 效果: "nanight" → "Nanite"，"meta human" → "MetaHuman"
- 成本: 零，纯本地处理
- GUI 提供: 预设术语模板 (GDC/Unreal/Unity) + 自定义编辑器

**第二层：AI 聚合时上下文修正**
- AI 同时看到转录文本 + PPT 截图，自动对齐术语
- 效果: 即使转录有误，AI 根据图片上下文推断正确术语
- 成本: 已包含在 Phase 4 的 AI 调用中，无额外开销

**ASR 方案对比（参考）:**

| 方案 | 准确率 | 成本 | 备注 |
|------|--------|------|------|
| faster-whisper large-v3 (本地) | 良好 | 免费 | 配合 initial_prompt 可显著提升 |
| Google Speech-to-Text | 优秀 | ~$0.024/min | 技术术语更好 |
| Deepgram | 优秀 | ~$0.012/min | 最快，支持自定义词汇 |
| OpenAI Whisper API | 优秀 | ~$0.036/min | 同源但云端更强 |

当前选择 faster-whisper + 双层修正，未来可扩展为可切换的 ASR Provider。

## Token 节省分析

| 方案 | Token 消耗 | 成本 | 说明 |
|------|-----------|------|------|
| 直接发视频到云端 AI | ~1M tokens | 极高 | 不可行 |
| 发 40 张图片 + 文稿到云端 | ~400k tokens | 高 | 图片占大头 |
| **当前方案**: slides.json (文字) + transcript.json (文字) | **~30k tokens** | **极低** | 纯文本输入 |
| 完全本地 (Ollama 聚合) | 0 | 免费 | 质量稍低 |

当前方案节省 97% tokens，且因提供了清晰的文字描述降低 AI 幻觉。

## 依赖 (requirements.txt)

```
PySide6
python-dotenv
opencv-python
scikit-image
faster-whisper
google-generativeai
openai
anthropic
requests
Pillow
pyinstaller
```

## 打包为 .exe

```bash
pyinstaller --onefile --windowed --name Video-Distiller --icon=src/gui/resources/icon.ico main.py
```

## 开发约定

- 每个模块通过文件系统解耦，输入输出均为文件路径
- 配置: settings.json 管理所有用户配置（持久化），启动时自动加载
- GUI: PySide6 + Apple 风格 QSS，支持 Light/Dark 主题切换
- Settings 对话框三个 Tab: 通用 (含 Ollama 视觉模型 + 所有 Prompt) / AI Provider / 术语词表
- 输出文件按时间戳命名（如 `05_12_frame.jpg` 表示 5分12秒）
- 非破坏性流水线: 所有中间结果保留，支持多次迭代优化
- 本地优先: 图片理解用 Ollama 视觉模型本地处理，云端 AI 只接收纯文本
- 目标: 1h 视频 → 30-50 张关键帧 → slides.json + transcript.json → ~30k tokens → Markdown 笔记

## 扩展方向

- OCR 增强: Phase 2 加入 Tesseract OCR 提取 PPT 标题，辅助目录生成
- 本地 RAG: 处理结果存入向量数据库，构建私人 GDC 知识库
- 批量处理: 支持一次投入多个视频，排队处理

## 实施顺序

| 步骤 | 模块 | 预计代码量 |
|------|------|-----------|
| 1 | config.py + .env + .gitignore | ~50 行 |
| 2 | media.py (MP3 + 抽帧) | ~100 行 |
| 3 | visual.py (SSIM 去重) | ~120 行 |
| 4 | transcribe.py | ~80 行 |
| 5 | ai_provider.py + providers/ | ~200 行 |
| 6 | gui/app.py + widgets.py (PySide6) | ~400 行 |
| 7 | main.py + run.bat + build.spec | ~30 行 |

---

## 版本开发计划

### v0.0 — 环境验证（开发前置）

> 目的：确保所有依赖正确安装，提前排除环境问题，避免后续开发踩坑。
> 需要用户辅助测试。

**验证项 & 测试 Demo：**

| # | 验证项 | 测试方法 | 通过标准 |
|---|--------|----------|----------|
| 1 | Python 3.10+ | `python --version` | 版本 >= 3.10 |
| 2 | PySide6 | 运行 demo: 弹出空白窗口，标题 "Video-Distiller" | 窗口正常显示，可关闭 |
| 3 | FFmpeg | `ffmpeg -version` + demo: 用一段 10s 测试视频提取 MP3 | MP3 文件生成，可播放 |
| 4 | FFmpeg 抽帧 | demo: 对同一测试视频 1fps 抽帧 | 生成 10 张 jpg，命名格式正确 |
| 5 | OpenCV + SSIM | demo: 读取两张测试图片，计算 SSIM 值 | 输出 0.0~1.0 之间的浮点数 |
| 6 | faster-whisper | demo: 对提取的 MP3 进行转录，输出前 3 段文本 | 输出带时间戳的文本，中文/英文均可 |
| 7 | python-dotenv | demo: 读取 .env 中的测试变量 | 正确打印变量值 |
| 8 | PyInstaller | demo: `pyinstaller --onefile` 打包一个 hello world | 生成 .exe，双击可运行 |

**测试 Demo 文件结构：**

```
tests/
├── test_env.py            # 一键运行所有环境检测
├── demo_pyside6.py        # PySide6 空窗口
├── demo_ffmpeg.py         # FFmpeg MP3 提取 + 抽帧
├── demo_opencv.py         # OpenCV SSIM 计算
├── demo_whisper.py        # faster-whisper 转录
└── demo_pyinstaller.py    # PyInstaller 打包测试
```

**用户需要提前安装的软件：**
- Python 3.10+ (https://python.org)
- FFmpeg (加入系统 PATH)
- CUDA (可选，用于 faster-whisper GPU 加速)

**完成标准：** `python tests/test_env.py` 全部 PASS 后进入正式开发。

---

### v0.1 — 项目骨架 + 配置模块

> 最小可运行框架，能启动 GUI 窗口但功能为空壳。

**交付内容：**
- 完整项目目录结构（src/, tests/, output/ 等）
- `config.py`：数据类配置管理，加载 .env
- `.env.example` + `.gitignore`
- `requirements.txt`（含版本锁定）
- `gui/app.py`：PySide6 主窗口骨架，4 个 Step 的 Tab 页（内容为空）
- `main.py`：入口文件

**验收标准：**
- `pip install -r requirements.txt` 无报错
- `python main.py` 弹出主窗口，显示 4 个 Tab 页
- `.env` 配置正确加载

---

### v0.2 — 媒体提取功能 (Phase 1)

> 核心功能：FFmpeg 提取 MP3 + 可配置抽帧。

**交付内容：**
- `media.py`：FFmpeg 封装，支持进度回调
- GUI Step 1 Tab 填充完整控件：
  - 视频路径选择（文件对话框）
  - 输出目录选择（文件夹对话框）
  - 音频采样率下拉（8k/16k/44.1k）
  - 抽帧间隔输入（默认 1fps）
  - 目标分辨率下拉（原始/1080p/720p/480p）
  - 进度条 + 状态标签
  - "开始提取" 按钮

**验收标准：**
- 选择一个真实视频文件，点击提取 MP3 → 输出目录出现 MP3 文件
- 点击抽帧 → 输出目录出现按时间戳命名的帧图片
- 进度条实时更新
- 异常处理：文件不存在、FFmpeg 未安装等给出友好提示

---

### v0.3 — 图片去重功能 (Phase 2)

> 核心功能：SSIM/pHash 去重，非破坏性迭代。

**交付内容：**
- `visual.py`：SSIM + pHash 双算法去重
- GUI Step 2 Tab 填充：
  - 源文件夹选择（下拉，自动检测 output 下的 frames 目录）
  - 算法选择（SSIM / pHash）
  - 阈值滑块（0.80 ~ 0.99，默认 0.95）
  - "开始去重" 按钮
  - 去重结果统计（原始帧数 → 保留帧数）
  - 关键帧画廊预览（缩略图网格，可点击放大）
  - "重新去重" 按钮（输出到 key_frames_v2/，旧结果不删除）
- 支持用户从原始 frames/ 拖拽图片到 key_frames/

**验收标准：**
- 用一段 PPT 演讲视频测试：3000+ 帧 → 筛选到 30-50 张
- 调低阈值重新去重，旧文件夹保留不变
- 画廊能浏览所有关键帧缩略图
- 帧数统计数字正确

---

### v0.4 — 本地图片理解 (Phase 2.5) — 新增

> 核心功能：用 Ollama 本地视觉模型提取关键帧文字，生成 slides.json。

**交付内容：**
- `image_analysis.py`：Ollama 视觉模型调用封装
  - 遍历 key_frames/ 中的图片，逐张发送给 Ollama
  - Prompt: 提取幻灯片文字、描述图表/架构图
  - 图片 base64 编码 → Ollama REST API → 解析返回 → 附加时间戳
- GUI: 在 Step 2 Tab 的去重区下方增加"图片理解"区域：
  - 视觉模型选择（从 Settings 加载 Ollama 模型列表）
  - "开始分析" 按钮 + 进度条（显示 X/42 张）
  - 分析结果预览（表格形式: 时间戳 | 标题 | 摘要）
  - "导出 slides.json" 按钮
- Settings 中新增"本地视觉模型"配置：
  - Ollama 服务地址（默认 http://localhost:11434）
  - 模型名称（minicpm-v:8b / llava:7b / qwen2-vl:7b）

**验收标准：**
- 安装 Ollama + 拉取 minicpm-v:8b 模型
- 对去重后的关键帧执行分析，生成 slides.json
- slides.json 包含每张帧的 title、text、diagrams 字段
- 进度条逐张更新
- 无 Ollama 服务时给出友好提示（引导安装）

---

### v0.5 — 语音转录功能 (Phase 3)

> 核心功能：faster-whisper 本地转录，带时间戳 JSON 输出 + 术语词表提升准确率。

**交付内容：**
- `transcribe.py`：faster-whisper 封装，支持分段切片 + initial_prompt 术语注入
- 术语词表预设模板：
  - `vocab/gdc.txt` — GDC 通用术语
  - `vocab/unreal.txt` — Unreal Engine 术语
  - `vocab/unity.txt` — Unity 术语
  - 用户可在 GUI 中编辑自定义术语
- GUI Step 3 Tab 填充：
  - 音频文件选择（自动检测 output 下的 MP3）
  - 模型选择下拉（tiny/base/small/medium/large-v3）
  - 语言选择（自动检测 / 中文 / 英文 / 日文）
  - 切片长度下拉（1/2/3/5 分钟）
  - 术语词表区域：
    - 预设模板下拉选择
    - 文本编辑框（可手动添加/修改术语，逗号或换行分隔）
    - "保存词表" 按钮（保存为项目专属词表）
  - "开始转录" 按钮 + 进度条
  - 转录结果预览（带时间戳的文本框）
  - "导出 JSON" 按钮

**验收标准：**
- 对提取的 MP3 执行转录，生成 transcript.json
- JSON 格式正确，segments 包含 start/end/text，metadata 包含 initial_prompt
- 带术语词表 vs 不带术语词表对比，技术术语准确率有明显提升
- 中文和英文视频均可正确转录
- 进度条正常更新
- CPU/GPU 自动检测降级

---

### v0.6 — AI 聚合功能 (Phase 4)

> 核心功能：AI Provider 抽象层 + 手动模式。输入为纯文本（slides.json + transcript.json）。

**交付内容：**
- `ai_provider.py`：Provider 抽象基类
- `providers/manual.py`：手动模式（导出/导入）
  - 导出: 合并 slides.json + transcript.json 为一份 Markdown 中间文件
  - 用户复制到 Gemini 网页版 → 粘贴返回结果 → 保存为 .md
- `providers/gemini.py`：Gemini API（可选）
- `providers/openai.py`：OpenAI API（可选）
- `providers/ollama.py`：Ollama 本地文本模型（可选）
- GUI Step 4 Tab：
  - 数据源选择: slides.json 路径 + transcript.json 路径
  - Provider 选择下拉（从 Settings 加载）
  - 手动模式：导出数据 → 粘贴结果 → 保存 .md
  - API 模式：蒸馏 Prompt 编辑 + "生成笔记" 按钮
  - 底部："保存 Markdown (.md)" 按钮
- 蒸馏 Prompt 默认模板内置

**验收标准：**
- 手动模式：导出 → 用户粘贴 → 保存 .md，完整流程走通
- API 模式（有 Key 时）：自动生成 Markdown 笔记
- 导出的中间数据包含 slides.json（图片描述）+ transcript.json（转录文本）
- 生成的 .md 包含 [时间戳][章节名][核心干货][截图引用]

---

### v0.7 — 集成测试 + 体验优化

> 完整流水线联调 + UI 打磨。

**交付内容：**
- 全流程串联：视频 → MP3 + 帧 → 去重 → 图片理解 → 转录 → AI → Markdown
- Step 之间自动检测前置步骤是否完成
- 每步完成后自动填充下一步的输入路径
- 整体进度指示（侧边栏或顶部步骤条）
- 错误汇总面板：记录每个步骤的警告和错误
- 输出 Tab：最终 Markdown 预览 + "打开输出目录" + "导出笔记" 按钮
- 处理报告：自动生成 pipeline_report.json（记录每步耗时、参数、结果统计）

**验收标准：**
- 用一段 30 分钟的真实技术演讲视频走完全流程
- 每步自动衔接，无需手动配置中间路径
- 处理报告记录完整
- 无 Python 异常弹窗

---

### v1.0 — 打包发布

> 打包为 .exe，小白用户可直接使用。

**交付内容：**
- `build.spec`：PyInstaller 打包配置
- FFmpeg 打包方案（内嵌 or 引导安装）
- 应用图标 + 窗口标题
- README.md：使用说明（面向非技术用户）
- 首次启动引导：检测 FFmpeg 是否安装，未安装则提示安装方法

**验收标准：**
- `pyinstaller build.spec` 生成单个 .exe
- 双击 .exe 启动，无需 Python 环境
- 在干净的 Windows 10/11 机器上测试可用
- 首次启动 FFmpeg 检测正常工作
