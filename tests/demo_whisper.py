"""
Demo: faster-whisper 转录测试
运行: py -3.12 tests/demo_whisper.py

注意: 首次运行会下载 whisper 模型 (约 1GB for large-v3, ~75MB for tiny)
      如果没有 GPU，会使用 CPU，速度较慢。
      建议先用 tiny 模型测试，确认环境后再用 large-v3。
"""

import os
import sys
import json


def test_whisper():
    # 查找测试音频
    audio_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "VideoDemo", "tutorial_output", "env_test", "audio", "tutorial.mp3"),
        os.path.join(os.path.dirname(__file__), "..", "VideoDemo", "tutorial_output", "audio", "tutorial.mp3"),
    ]
    audio_candidates = [os.path.normpath(p) for p in audio_candidates]

    audio_path = None
    for p in audio_candidates:
        if os.path.exists(p):
            audio_path = p
            break

    if not audio_path:
        print("[FAIL] 未找到测试音频文件")
        print("       请先运行 demo_ffmpeg.py 生成 MP3")
        return False

    print(f"音频文件: {audio_path}")
    size_mb = os.path.getsize(audio_path) / 1024 / 1024
    print(f"文件大小: {size_mb:.1f} MB")

    # 导入
    print("\n导入 faster_whisper...")
    from faster_whisper import WhisperModel

    # 选择模型
    model_name = "tiny"  # 用 tiny 快速验证，正式使用 large-v3
    print(f"\n加载模型: {model_name} (首次运行会自动下载)")

    # 检测设备
    device = "cpu"
    compute_type = "int8"
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
            gpu_name = torch.cuda.get_device_name(0)
            print(f"检测到 GPU: {gpu_name}，使用 CUDA 加速")
        else:
            print("未检测到 CUDA，使用 CPU (速度较慢)")
    except ImportError:
        print("未安装 PyTorch，使用 CPU")

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    print("模型加载完成!")

    # 只转录前 30 秒用于测试
    print(f"\n转录前 30 秒...")
    segments, info = model.transcribe(
        audio_path,
        language=None,  # 自动检测
        condition_on_previous_text=True,
    )

    print(f"检测语言: {info.language} (概率: {info.language_probability:.2f})")

    results = []
    for i, seg in enumerate(segments):
        if seg.start > 30:
            break
        results.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        print(f"  [{seg.start:.1f}s - {seg.end:.1f}s] {seg.text.strip()}")

    if results:
        print(f"\n  [OK] 转录成功，获取 {len(results)} 段文本")

        # 保存测试结果
        out_dir = os.path.join(os.path.dirname(__file__), "..", "VideoDemo", "tutorial_output", "env_test")
        out_dir = os.path.normpath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, "test_transcript.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({"segments": results, "language": info.language}, f, ensure_ascii=False, indent=2)
        print(f"  测试结果已保存: {out_file}")
        return True
    else:
        print("  [WARN] 转录完成但未获取到文本 (可能音频太短或为纯音乐)")
        return True


if __name__ == "__main__":
    print("=== faster-whisper 转录测试 ===")
    print("提示: 使用 tiny 模型快速验证，正式开发用 large-v3\n")

    try:
        ok = test_whisper()
    except ImportError as e:
        print(f"[FAIL] 导入失败: {e}")
        print("       运行: py -3.12 -m pip install faster-whisper")
        ok = False
    except Exception as e:
        print(f"[FAIL] 运行错误: {e}")
        ok = False

    print("\n" + "=" * 50)
    if ok:
        print("[PASS] faster-whisper 环境正常!")
    print("=" * 50)
