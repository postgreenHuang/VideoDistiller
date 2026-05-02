"""
Video-Distiller 语音转录模块
- 本地: faster-whisper (GPU float16 / CPU int8)
- 云端: OpenAI 兼容 API (/audio/transcriptions)
- 输出 transcript.json，时间戳与关键帧 MM:SS 对齐
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable


def _seconds_to_mmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def _mmss_to_seconds(mmss: str) -> float:
    parts = mmss.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _get_audio_duration(path: str) -> float:
    from src.media import find_ffmpeg
    ffprobe = find_ffmpeg().replace("ffmpeg", "ffprobe")
    if not os.path.exists(ffprobe):
        ffprobe = "ffprobe"
    try:
        r = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _split_audio_chunks(audio_path: str, chunk_seconds: int, tmp_dir: str) -> list[tuple[str, float]]:
    from src.media import find_ffmpeg
    ffmpeg = find_ffmpeg()
    duration = _get_audio_duration(audio_path)
    if duration <= 0:
        return [(audio_path, 0.0)]

    chunks = []
    offset = 0.0
    idx = 0
    while offset < duration:
        out_path = os.path.join(tmp_dir, f"chunk_{idx:04d}.mp3")
        cmd = [
            ffmpeg, "-i", audio_path,
            "-ss", str(offset), "-t", str(chunk_seconds),
            "-y", out_path,
        ]
        subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if os.path.exists(out_path):
            chunks.append((out_path, offset))
        offset += chunk_seconds
        idx += 1
    return chunks


def _merge_segments(raw_segments: list[dict], target_length: int) -> list[dict]:
    if not raw_segments:
        return []
    merged = []
    buf = dict(raw_segments[0])
    for seg in raw_segments[1:]:
        if buf["end"] - buf["start"] < target_length:
            buf["end"] = seg["end"]
            buf["text"] += " " + seg["text"]
        else:
            merged.append(buf)
            buf = dict(seg)
    merged.append(buf)
    return merged


def _enrich_segments(segments: list[dict]) -> list[dict]:
    for seg in segments:
        seg["start_mmss"] = _seconds_to_mmss(seg["start"])
        seg["end_mmss"] = _seconds_to_mmss(seg["end"])
    return segments


# ─── 本地 faster-whisper ───

def _transcribe_local(
    audio_path: str,
    model_name: str = "large-v3",
    language: Optional[str] = None,
    initial_prompt: Optional[str] = None,
    segment_length: int = 180,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> list[dict]:
    from faster_whisper import WhisperModel

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"
    compute = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_name, device=device, compute_type=compute)

    lang = language if language and language != "auto" else None
    prompt = initial_prompt if initial_prompt else None

    segments_iter, info = model.transcribe(
        audio_path, language=lang, initial_prompt=prompt,
        condition_on_previous_text=True, vad_filter=True,
    )

    raw_segments = []
    total_duration = info.duration
    for seg in segments_iter:
        raw_segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        if progress_cb and total_duration > 0:
            progress_cb(min(seg.end / total_duration, 1.0))

    merged = _merge_segments(raw_segments, segment_length)
    return _enrich_segments(merged)


# ─── 云端 OpenAI 兼容 API ───

def _transcribe_cloud(
    audio_path: str,
    api_url: str,
    api_key: str,
    cloud_model: str = "whisper-large-v3",
    language: Optional[str] = None,
    segment_length: int = 180,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> list[dict]:
    import requests

    if not api_url or not api_key:
        raise ValueError("请先在 Settings 中配置云端 ASR 的 API 地址和 Key")

    url = api_url.rstrip("/") + "/audio/transcriptions"
    lang = language if language and language != "auto" else None

    with tempfile.TemporaryDirectory() as tmp_dir:
        chunks = _split_audio_chunks(audio_path, segment_length, tmp_dir)
        all_raw = []

        for i, (chunk_path, offset) in enumerate(chunks):
            with open(chunk_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (os.path.basename(chunk_path), f, "audio/mp3")},
                    data={
                        "model": cloud_model,
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "segment",
                        **({"language": lang} if lang else {}),
                    },
                    timeout=300,
                )
            resp.raise_for_status()
            data = resp.json()

            segments = data.get("segments", [])
            if not segments:
                text = data.get("text", "").strip()
                if text:
                    duration = _get_audio_duration(chunk_path)
                    segments = [{"start": 0.0, "end": duration, "text": text}]

            for seg in segments:
                all_raw.append({
                    "start": round(seg["start"] + offset, 2),
                    "end": round(seg["end"] + offset, 2),
                    "text": seg["text"].strip(),
                })

            if progress_cb:
                progress_cb((i + 1) / len(chunks))

    merged = _merge_segments(all_raw, segment_length)
    return _enrich_segments(merged)


# ─── 统一入口 ───

def transcribe(
    audio_path: str,
    output_dir: str,
    asr_type: str = "local",
    model: str = "large-v3",
    language: Optional[str] = None,
    vocabulary: Optional[str] = None,
    segment_length: int = 180,
    asr_api_url: str = "",
    asr_api_key: str = "",
    asr_cloud_model: str = "whisper-large-v3",
    progress_cb: Optional[Callable[[float], None]] = None,
) -> dict:
    if asr_type == "cloud":
        segments = _transcribe_cloud(
            audio_path, asr_api_url, asr_api_key, asr_cloud_model,
            language, segment_length, progress_cb,
        )
        used_model = asr_cloud_model
    else:
        segments = _transcribe_local(
            audio_path, model, language, vocabulary, segment_length, progress_cb,
        )
        used_model = model

    transcript_dir = os.path.join(output_dir, "transcript")
    os.makedirs(transcript_dir, exist_ok=True)

    total_duration = segments[-1]["end"] if segments else 0.0
    result = {
        "segments": segments,
        "metadata": {
            "asr_type": asr_type,
            "model": used_model,
            "language": language or "auto",
            "initial_prompt": vocabulary or "",
            "segment_length": segment_length,
            "total_duration": round(total_duration, 2),
            "total_segments": len(segments),
            "total_chars": sum(len(s["text"]) for s in segments),
        },
    }

    out_path = os.path.join(transcript_dir, "transcript.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    result["output"] = out_path
    return result


def build_preview_text(segments: list[dict]) -> str:
    return "\n\n".join(f"[{s['start_mmss']}] {s['text']}" for s in segments)
