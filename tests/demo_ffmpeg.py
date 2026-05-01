"""
Demo: FFmpeg MP3 提取 + 抽帧测试
运行: py -3.12 tests/demo_ffmpeg.py
"""

import os
import sys
import subprocess
import shutil

VIDEO = os.path.join(os.path.dirname(__file__), "..", "VideoDemo", "tutorial.mp4")
VIDEO = os.path.normpath(VIDEO)
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "VideoDemo", "tutorial_output", "env_test")
OUT_DIR = os.path.normpath(OUT_DIR)

AUDIO_DIR = os.path.join(OUT_DIR, "audio")
FRAMES_DIR = os.path.join(OUT_DIR, "frames")


def find_ffmpeg():
    for cmd in ["ffmpeg", "ffmpeg.exe"]:
        try:
            r = subprocess.run([cmd, "-version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return cmd
        except Exception:
            continue
    # 尝试常见路径
    for p in [r"C:\ffmpeg\bin\ffmpeg.exe"]:
        if os.path.exists(p):
            return p
    return None


def test_extract_audio():
    print("\n--- 测试: 提取 MP3 ---")
    os.makedirs(AUDIO_DIR, exist_ok=True)
    out_mp3 = os.path.join(AUDIO_DIR, "tutorial.mp3")

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("  [FAIL] 未找到 FFmpeg")
        return False

    cmd = [ffmpeg, "-i", VIDEO, "-vn", "-ar", "16000", "-ac", "1", "-y", out_mp3]
    print(f"  运行: {' '.join(cmd)}")

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [FAIL] FFmpeg 错误:\n{r.stderr[-500:]}")
        return False

    if os.path.exists(out_mp3):
        size_kb = os.path.getsize(out_mp3) / 1024
        print(f"  [OK] MP3 已生成: {out_mp3} ({size_kb:.0f} KB)")
        return True
    else:
        print("  [FAIL] MP3 文件未生成")
        return False


def test_extract_frames():
    print("\n--- 测试: 1fps 抽帧 (仅前 5 秒) ---")
    os.makedirs(FRAMES_DIR, exist_ok=True)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("  [FAIL] 未找到 FFmpeg")
        return False

    # 只抽前 5 秒的帧用于测试
    out_pattern = os.path.join(FRAMES_DIR, "%02d_%02d_frame.jpg")
    cmd = [ffmpeg, "-i", VIDEO, "-t", "5", "-vf", "fps=1", "-y", out_pattern]
    print(f"  运行: {' '.join(cmd)}")

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [FAIL] FFmpeg 错误:\n{r.stderr[-500:]}")
        return False

    frames = [f for f in os.listdir(FRAMES_DIR) if f.endswith(".jpg")]
    if frames:
        print(f"  [OK] 生成 {len(frames)} 帧:")
        for f in sorted(frames):
            path = os.path.join(FRAMES_DIR, f)
            size_kb = os.path.getsize(path) / 1024
            print(f"       {f} ({size_kb:.0f} KB)")
        return True
    else:
        print("  [FAIL] 未生成帧图片")
        return False


def cleanup():
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
        print(f"\n清理测试目录: {OUT_DIR}")


if __name__ == "__main__":
    if not os.path.exists(VIDEO):
        print(f"[FAIL] 测试视频不存在: {VIDEO}")
        sys.exit(1)

    print(f"测试视频: {VIDEO}")
    print(f"输出目录: {OUT_DIR}")

    ok1 = test_extract_audio()
    ok2 = test_extract_frames()

    print("\n" + "=" * 50)
    if ok1 and ok2:
        print("[PASS] FFmpeg MP3 提取和抽帧均正常!")
    else:
        print("[FAIL] 部分测试未通过，请检查上方错误信息。")
    print("=" * 50)
