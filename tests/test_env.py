"""
Video-Distiller 环境检测脚本
运行: py -3.12 tests/test_env.py
"""

import sys
import subprocess
import importlib

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    icon = "OK" if condition else "XX"
    print(f"  [{icon}] {name}: {detail}" if detail else f"  [{icon}] {name}")


def get_py():
    return sys.executable


# === 1. Python 版本 ===
print("\n=== 1. Python ===")
ver = sys.version_info
check("Python 版本", ver >= (3, 10), f"{ver.major}.{ver.minor}.{ver.micro}")

# === 2. PySide6 ===
print("\n=== 2. PySide6 ===")
try:
    import PySide6
    check("PySide6 导入", True, PySide6.__version__)
except ImportError:
    check("PySide6 导入", False, "未安装，运行: py -3.12 -m pip install PySide6")

# === 3. FFmpeg ===
print("\n=== 3. FFmpeg ===")
ffmpeg_found = False
for cmd in ["ffmpeg", "ffmpeg.exe"]:
    try:
        r = subprocess.run([cmd, "-version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            line = r.stdout.split("\n")[0]
            check("FFmpeg", True, line[:60])
            ffmpeg_found = True
            break
    except Exception:
        continue
if not ffmpeg_found:
    try:
        r = subprocess.run(
            ["py", "-3.12", "-c", "import shutil; print(shutil.which('ffmpeg'))"],
            capture_output=True, text=True, timeout=5,
            env={**__import__("os").environ, "PATH": __import__("os").environ.get("PATH", "") + ";C:\\ffmpeg\\bin"},
        )
    except Exception:
        pass
    check("FFmpeg", False, "未找到。安装后加入 PATH，参考 CLAUDE.md")

# === 4. OpenCV ===
print("\n=== 4. OpenCV ===")
try:
    import cv2
    check("OpenCV 导入", True, cv2.__version__)
except ImportError:
    check("OpenCV 导入", False, "未安装，运行: py -3.12 -m pip install opencv-python")

# === 5. scikit-image (SSIM) ===
print("\n=== 5. scikit-image ===")
try:
    import skimage
    check("scikit-image 导入", True, skimage.__version__)
except ImportError:
    check("scikit-image 导入", False, "未安装，运行: py -3.12 -m pip install scikit-image")

# === 6. faster-whisper ===
print("\n=== 6. faster-whisper ===")
try:
    from faster_whisper import WhisperModel
    check("faster-whisper 导入", True, "可用")
except ImportError:
    check("faster-whisper 导入", False, "未安装，运行: py -3.12 -m pip install faster-whisper")

# === 7. python-dotenv ===
print("\n=== 7. python-dotenv ===")
try:
    import dotenv
    check("python-dotenv 导入", True, dotenv.__version__)
except ImportError:
    check("python-dotenv 导入", False, "未安装，运行: py -3.12 -m pip install python-dotenv")

# === 8. Pillow ===
print("\n=== 8. Pillow ===")
try:
    from PIL import Image
    check("Pillow 导入", True, Image.__version__)
except ImportError:
    check("Pillow 导入", False, "未安装，运行: py -3.12 -m pip install Pillow")

# === 9. CUDA (可选) ===
print("\n=== 9. CUDA (可选) ===")
try:
    r = subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=5,
    )
    if r.returncode == 0:
        gpu = r.stdout.strip().split("\n")[0]
        check("GPU 检测", True, gpu)
    else:
        check("GPU 检测", False, "nvidia-smi 执行失败")
except Exception:
    check("GPU 检测", False, "未检测到 NVIDIA GPU (不影响使用，Whisper 会用 CPU)")

# === 10. 测试视频 ===
print("\n=== 10. 测试视频 ===")
import os
video_path = os.path.join(os.path.dirname(__file__), "..", "VideoDemo", "tutorial.mp4")
video_path = os.path.normpath(video_path)
if os.path.exists(video_path):
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    check("tutorial.mp4", True, f"{size_mb:.1f} MB")
else:
    check("tutorial.mp4", False, f"未找到: {video_path}")

# === 汇总 ===
print("\n" + "=" * 50)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
total = len(results)
print(f"结果: {passed}/{total} 通过, {failed} 失败")
if failed == 0:
    print("所有环境检测通过! 可以开始开发。")
else:
    print("有检测项未通过，请根据上方提示安装缺失的依赖。")
print("=" * 50)
