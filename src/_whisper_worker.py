"""
Whisper 子进程入口 — 隔离 CUDA 上下文，防止主 GUI 进程崩溃

用法: py -3.12 _whisper_worker.py --audio X --model large-v3 --result out.json --progress prog.json [--language zh] [--prompt "..."]
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--result", required=True)
    parser.add_argument("--progress", required=True)
    parser.add_argument("--language", default=None)
    parser.add_argument("--prompt", default=None)
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"
    compute = "float16" if device == "cuda" else "int8"

    model = WhisperModel(args.model, device=device, compute_type=compute)

    lang = args.language if args.language and args.language != "auto" else None
    prompt = args.prompt if args.prompt else None

    segments_iter, info = model.transcribe(
        args.audio, language=lang, initial_prompt=prompt,
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
        if total_duration > 0:
            try:
                with open(args.progress, "w") as f:
                    f.write(str(min(seg.end / total_duration, 1.0)))
            except Exception:
                pass

    with open(args.result, "w", encoding="utf-8") as f:
        json.dump(raw_segments, f, ensure_ascii=False)

    # 清理 GPU 显存
    del model
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


if __name__ == "__main__":
    main()
