"""
Video-Distiller 图片理解模块
- 本地: Ollama 视觉模型 (minicpm-v, llava, qwen2-vl 等)
- 云端: OpenAI 兼容 Vision API (GLM-4V, Qwen-VL, GPT-4o 等)
- 三步调用 (本地小模型) / 单次调用 (云端高级模型)
- 输出 slides.json（增量写入）
"""

import base64
import json
import os
import re
from pathlib import Path
from typing import Optional, Callable


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _parse_timestamp(filename: str) -> str:
    """从 05_12_frame.jpg 提取 '05:12'"""
    m = re.match(r"(\d{2})_(\d{2})", Path(filename).stem)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    return "00:00"


def _call_ollama(model: str, prompt: str, image_b64: str, base_url: str,
                 context: Optional[list] = None) -> tuple:
    """返回 (text, tokens_dict, context)"""
    import requests

    url = base_url.rstrip("/") + "/api/generate"
    body = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "keep_alive": "5m",
    }
    if context is not None:
        body["context"] = context
    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    text = data.get("response", "").strip()
    new_ctx = data.get("context", [])
    prompt_tokens = data.get("prompt_eval_count", 0) or 0
    completion_tokens = data.get("eval_count", 0) or 0
    return text, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }, new_ctx


def _call_cloud(model: str, prompt: str, image_b64: str,
                base_url: str, api_key: str) -> tuple:
    """返回 (text, tokens_dict)"""
    import requests

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data_url = f"data:image/jpeg;base64,{image_b64}"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 1024,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    return text, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _analyze_single(model_type: str, model: str, prompt: str,
                    image_b64: str, base_url: str, api_key: str,
                    context: Optional[list] = None) -> tuple:
    """单次调用，返回 (text, tokens_dict, context_or_None)"""
    if model_type == "ollama":
        text, tokens, ctx = _call_ollama(model, prompt, image_b64, base_url, context)
        return text, tokens, ctx
    else:
        text, tokens = _call_cloud(model, prompt, image_b64, base_url, api_key)
        return text, tokens, None


def _find_transcript_context(timestamp_str: str, segments: list,
                             max_chars: int = 150) -> str:
    """找到该时间点对应的 transcript 段落，截取摘要"""
    parts = timestamp_str.split(":")
    ts_seconds = int(parts[0]) * 60 + int(parts[1])
    for seg in segments:
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        if start <= ts_seconds <= end:
            text = seg.get("text", "").strip()
            if not text:
                return ""
            if len(text) <= max_chars:
                return text
            # 截取到最近的句号
            cut = text[:max_chars]
            for punct in ("。", ".", "！", "!", "？", "?", "；", ";"):
                idx = cut.rfind(punct)
                if idx > 20:
                    return text[:idx + 1]
            return cut + "..."
    return ""


def _parse_json_response(text: str) -> dict:
    """从模型输出中提取 JSON，兼容 ```json...``` 包裹"""
    # 直接解析
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试提取 ```json...``` 代码块
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # 兜底：把原始文本放入 text 字段
    return {"type": "", "title": "", "text": text, "layout": "", "diagrams": ""}


def _write_slides(output_dir: str, slides: list, model: str, tokens: dict) -> str:
    """将当前 slides 列表写入 slides.json，返回文件路径"""
    out_path = os.path.join(output_dir, "slides.json")
    data = {
        "slides": slides,
        "model": model,
        "total_slides": len(slides),
        "tokens": tokens,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path


def analyze_images(
    key_frames_dir: str,
    output_dir: str,
    vision_config: dict,
    prompts: dict,
    progress_cb: Optional[Callable[[float], None]] = None,
    cancel_flag: Optional[dict] = None,
    token_cb: Optional[Callable[[dict], None]] = None,
    transcript_segments: Optional[list] = None,
) -> dict:
    """
    分析关键帧图片，生成 slides.json（增量写入）

    Args:
        key_frames_dir: key_frames/ 目录路径
        output_dir: 项目目录 (slides.json 写到此处)
        vision_config: {"type", "model", "url", "api_key", "prompt_strategy"}
        prompts: {"ocr", "diagram", "title", "single"}
        progress_cb: 进度回调 (0.0 ~ 1.0)
        cancel_flag: {"cancel": False} — 设为 True 可中途取消
        token_cb: token 消耗回调
        transcript_segments: transcript.json 的 segments 列表，用于提供上下文

    Returns:
        {"slides", "model", "total_slides", "output", "cancelled", "tokens"}
    """
    frames = sorted(Path(key_frames_dir).glob("*.jpg"))
    if not frames:
        raise ValueError(f"关键帧目录为空: {key_frames_dir}")

    vtype = vision_config.get("type", "ollama")
    model = vision_config.get("model", "minicpm-v:8b")
    base_url = vision_config.get("url", "http://localhost:11434")
    api_key = vision_config.get("api_key", "")
    strategy = vision_config.get("prompt_strategy", "triple")

    slides = []
    total = len(frames)
    cancelled = False
    accumulated_tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def _accumulate(tokens: dict, call_count: int = 1):
        accumulated_tokens["prompt"] += tokens.get("prompt_tokens", 0)
        accumulated_tokens["completion"] += tokens.get("completion_tokens", 0)
        accumulated_tokens["total"] += tokens.get("total_tokens", 0)
        accumulated_tokens["calls"] += call_count
        if token_cb:
            token_cb(dict(accumulated_tokens))

    for i, frame_path in enumerate(frames):
        if cancel_flag and cancel_flag.get("cancel"):
            cancelled = True
            break

        image_b64 = _encode_image(str(frame_path))
        timestamp = _parse_timestamp(frame_path.name)

        # 从 transcript 获取当前时间点的讲者内容作为上下文
        ctx = ""
        if transcript_segments:
            ctx = _find_transcript_context(timestamp, transcript_segments)
        context_prefix = f'当前讲者正在说："{ctx}"\n\n' if ctx else ""

        if strategy == "single":
            prompt_single = context_prefix + prompts.get("single", "")
            raw, tokens, _ = _analyze_single(
                vtype, model, prompt_single, image_b64, base_url, api_key,
            )
            _accumulate(tokens, 1)
            parsed = _parse_json_response(raw)
            slides.append({
                "timestamp": timestamp,
                "file": frame_path.name,
                "type": parsed.get("type", ""),
                "title": parsed.get("title", ""),
                "text": parsed.get("text", raw),
                "layout": parsed.get("layout", ""),
                "diagrams": parsed.get("diagrams", ""),
            })
        else:
            # 三步调用 — 复用 Ollama context，图片只编码一次
            ollama_ctx = None
            text, t1, ollama_ctx = _analyze_single(
                vtype, model, context_prefix + prompts["ocr"],
                image_b64, base_url, api_key, ollama_ctx,
            )
            diagrams, t2, ollama_ctx = _analyze_single(
                vtype, model, context_prefix + prompts["diagram"],
                image_b64, base_url, api_key, ollama_ctx,
            )
            title, t3, _ = _analyze_single(
                vtype, model, context_prefix + prompts["title"],
                image_b64, base_url, api_key, ollama_ctx,
            )
            _accumulate(t1)
            _accumulate(t2)
            _accumulate(t3)
            slides.append({
                "timestamp": timestamp,
                "file": frame_path.name,
                "type": "",
                "title": title,
                "text": text,
                "layout": diagrams,
                "diagrams": diagrams,
            })

        # 释放当前帧的内存
        del image_b64
        if i % 5 == 4:
            import gc
            gc.collect()

        _write_slides(output_dir, slides, model, accumulated_tokens)

        if progress_cb:
            progress_cb((i + 1) / total)

    out_path = os.path.join(output_dir, "slides.json")
    return {
        "slides": slides,
        "model": model,
        "total_slides": len(slides),
        "output": out_path,
        "cancelled": cancelled,
        "tokens": accumulated_tokens,
    }
