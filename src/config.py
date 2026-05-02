"""
Video-Distiller 配置管理
- 用户配置持久化到 settings.json
- 支持多 AI Provider、自定义术语词表
"""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
SETTINGS_FILE = PROJECT_ROOT / "settings.json"

RESOLUTION_SCALES = ["1/2", "1/4", "1/6", "1/8", "1/10", "1/12"]
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

VISION_MODELS_OLLAMA = [
    "minicpm-v:8b", "llava:7b-v1.6", "llava-llama3:8b",
    "qwen2-vl:7b", "moondream:1.8b",
]
VISION_MODELS_CLOUD = [
    "glm-4v-plus", "glm-4v-flash",
    "qwen-vl-max", "qwen-vl-plus",
    "gpt-4o", "claude-sonnet-4-6",
]

CLOUD_API_PRESETS = {
    "glm-4v-plus": "https://open.bigmodel.cn/api/paas/v4",
    "glm-4v-flash": "https://open.bigmodel.cn/api/paas/v4",
    "qwen-vl-max": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "qwen-vl-plus": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "gpt-4o": "https://api.openai.com/v1",
    "claude-sonnet-4-6": "https://api.anthropic.com/v1",
}


@dataclass
class ProviderConfig:
    name: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@dataclass
class VocabConfig:
    name: str = ""
    terms: str = ""  # 逗号分隔的术语字符串


@dataclass
class Settings:
    theme: str = "dark"
    resolution_scale: str = "1/2"
    sample_rate: int = 16000
    fps: float = 1.0
    ssim_threshold: float = 0.95
    whisper_model: str = "large-v3"
    whisper_language: str = ""
    segment_length: int = 180
    ollama_url: str = "http://localhost:11434"
    vision_type: str = "ollama"  # "ollama" | "cloud"
    vision_model: str = "minicpm-v:8b"
    vision_api_url: str = ""
    vision_api_key: str = ""
    providers: list = field(default_factory=lambda: [
        {"name": "Gemini", "base_url": "", "api_key": "", "model": "gemini-1.5-pro"},
        {"name": "OpenAI", "base_url": "", "api_key": "", "model": "gpt-4o"},
        {"name": "Claude", "base_url": "", "api_key": "", "model": "claude-sonnet-4-6"},
        {"name": "Ollama", "base_url": "http://localhost:11434", "api_key": "", "model": "llama3"},
    ])
    vocabularies: list = field(default_factory=lambda: [
        {"name": "GDC 通用", "terms": "GDC, shader, rendering, rasterization, ray tracing, path tracing, global illumination, PBR, LOD, culling, GPU, CPU, ECS, data oriented design, compute shader"},
        {"name": "Unreal Engine", "terms": "Unreal, UE5, Nanite, Lumen, MetaHuman, Niagara, Chaos, Blueprint, World Partition, Gameplay Ability System, GAS, Enhanced Input, Lyra, Verse"},
        {"name": "Unity", "terms": "Unity, GameObject, MonoBehaviour, Prefab, ScriptableObject, NavMesh, Animator, URP, HDRP, Shader Graph, VFX Graph, DOTS, ECS, Burst, Job System"},
    ])
    default_distill_prompt: str = (
        "你是一个技术专家。我会给你提供一系列演讲幻灯片的文字描述和对应的语音转录。\n"
        "请执行以下任务：\n"
        "1. 根据内容变化划分章节\n"
        "2. 结合幻灯片中的数据说明技术细节\n"
        "3. 提取讲者提到的核心数值、性能指标或经验教训\n"
        "4. 根据幻灯片文字修正转录文本中的术语错误\n"
        "5. 输出格式为 Markdown，包含 [时间戳][章节名][核心干货][截图引用]"
    )
    vision_prompt_ocr: str = (
        "请仔细提取这张幻灯片中的所有文字内容，按原文逐字提取，不要遗漏。\n"
        "如果是代码，保持代码格式。\n"
        "如果是表格，用 Markdown 表格格式还原。\n"
        "只输出提取的文字，不要添加任何解释。"
    )
    vision_prompt_diagram: str = (
        "这张幻灯片中是否有图表、架构图或流程图？\n"
        "如果有，请用一段话描述：图中包含哪些元素、元素之间的关系、标注的文字。\n"
        "如果没有图表，输出：无图表。\n"
        "只输出描述，不要添加其他内容。"
    )
    vision_prompt_title: str = (
        "请用一句话概括这张幻灯片的主题。不超过 20 个字。\n"
        "只输出标题，不要输出其他内容。"
    )


def load_settings() -> Settings:
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return Settings(**{k: v for k, v in data.items() if k in Settings.__dataclass_fields__})
        except Exception:
            pass
    return Settings()


def save_settings(s: Settings):
    SETTINGS_FILE.write_text(
        json.dumps(asdict(s), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_project_dir(output_dir: str, video_path: str) -> Path:
    name = Path(video_path).stem
    project_dir = Path(output_dir) / name
    project_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("audio", "frames", "key_frames", "transcript", "notes"):
        (project_dir / sub).mkdir(exist_ok=True)
    return project_dir


def load_vocab_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""
