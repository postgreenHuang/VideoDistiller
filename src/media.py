"""
Video-Distiller 媒体处理模块
- ① MP3 音频提取
- ② 视频帧提取 (可配置间隔 / 分辨率缩放)
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Callable


def find_ffmpeg() -> str:
    for cmd in ("ffmpeg", "ffmpeg.exe"):
        try:
            r = subprocess.run(
                [cmd, "-version"], capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                return cmd
        except Exception:
            continue
    # 平台常见的非 PATH 安装路径
    candidates = []
    if os.name == "nt":
        candidates.append(r"C:\ffmpeg\bin\ffmpeg.exe")
    else:
        candidates.extend([
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
        ])
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "未找到 FFmpeg。请安装 FFmpeg 并添加到 PATH"
        + ("，或放置到 C:\\ffmpeg\\bin\\" if os.name == "nt" else " (brew install ffmpeg)")
    )


def _parse_duration(stderr_text: str) -> float:
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", stderr_text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 100
    return 0.0


def _parse_progress(stderr_line: str, duration: float) -> float:
    m = re.search(r"time=\s*(\d+):(\d+):(\d+)\.(\d+)", stderr_line)
    if m and duration > 0:
        current = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 100
        return min(current / duration, 1.0)
    return -1.0


def _run_ffmpeg(
    cmd: list[str],
    progress_cb: Optional[Callable[[float], None]] = None,
):
    proc = subprocess.Popen(
        cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    duration = 0.0
    for line in proc.stderr:
        if duration == 0.0:
            duration = _parse_duration(line)
        if progress_cb and duration > 0:
            pct = _parse_progress(line, duration)
            if pct >= 0:
                progress_cb(pct)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg 退出码 {proc.returncode}")


# ─── ① 音频提取 ───

def extract_audio(
    video_path: str,
    output_dir: str,
    sample_rate: int = 16000,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> str:
    ffmpeg = find_ffmpeg()
    os.makedirs(output_dir, exist_ok=True)
    out_mp3 = str(Path(output_dir) / f"{Path(video_path).stem}.mp3")

    cmd = [
        ffmpeg, "-i", video_path,
        "-vn", "-ar", str(sample_rate), "-ac", "1",
        "-y", out_mp3,
    ]
    _run_ffmpeg(cmd, progress_cb)
    return out_mp3


# ─── ② 帧提取 ───

RESOLUTION_FILTERS = {
    "3/4": "scale=iw*0.75:ih*0.75",
    "1/2": "scale=iw*0.5:ih*0.5",
    "1/4": "scale=iw*0.25:ih*0.25",
    "1/6": "scale=iw/6:ih/6",
    "1/8": "scale=iw*0.125:ih*0.125",
    "1/10": "scale=iw*0.1:ih*0.1",
    "1/12": "scale=iw/12:ih/12",
}


def extract_frames(
    video_path: str,
    output_dir: str,
    fps: float = 1.0,
    resolution_scale: str = "1/2",
    progress_cb: Optional[Callable[[float], None]] = None,
) -> str:
    ffmpeg = find_ffmpeg()
    frames_dir = str(Path(output_dir) / "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 构建 filter chain: fps=xx[, scale=xx]
    vf_parts = [f"fps={fps}"]
    if resolution_scale in RESOLUTION_FILTERS:
        vf_parts.append(RESOLUTION_FILTERS[resolution_scale])
    vf = ",".join(vf_parts)

    # FFmpeg 只支持一个 %d 序号，先输出临时名，再重命名为 {MM}_{SS}_frame.jpg
    tmp_pattern = str(Path(frames_dir) / "_tmp_%06d.jpg")

    cmd = [
        ffmpeg, "-i", video_path,
        "-vf", vf,
        "-q:v", "2",
        "-y", tmp_pattern,
    ]
    _run_ffmpeg(cmd, progress_cb)

    # 重命名: _tmp_NNNNNN.jpg → {MM}_{SS}_frame.jpg  (第N帧 → 时间 = N/fps)
    _rename_frames(frames_dir, fps)
    return frames_dir


def _rename_frames(frames_dir: str, fps: float):
    tmp_files = sorted(
        f for f in os.listdir(frames_dir) if f.startswith("_tmp_") and f.endswith(".jpg")
    )
    for idx, fname in enumerate(tmp_files):
        seconds = idx / fps
        m, s = int(seconds) // 60, int(seconds) % 60
        new_name = f"{m:02d}_{s:02d}_frame.jpg"
        src = os.path.join(frames_dir, fname)
        dst = os.path.join(frames_dir, new_name)
        if not os.path.exists(dst):
            os.rename(src, dst)
        else:
            os.remove(src)
