"""
Video-Distiller 图片去重模块
- SSIM 相似度去重
- pHash 感知哈希去重
- 非破坏性迭代: key_frames/, key_frames_v2/, ...
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Callable

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


def _list_frames(frames_dir: str) -> list[str]:
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    return sorted(
        os.path.join(frames_dir, f)
        for f in os.listdir(frames_dir)
        if f.lower().endswith(exts)
    )


def _next_output_dir(parent_dir: str) -> str:
    base = Path(parent_dir)
    if not (base / "key_frames").exists():
        return str(base / "key_frames")
    i = 2
    while (base / f"key_frames_v{i}").exists():
        i += 1
    return str(base / f"key_frames_v{i}")


# ─── SSIM 去重 ───

def _ssim_compare(img_a: np.ndarray, img_b: np.ndarray) -> float:
    gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
    h, w = gray_a.shape
    min_dim = min(h, w)
    win = 7 if min_dim >= 7 else min_dim if min_dim % 2 == 1 else min_dim - 1
    score, _ = ssim(gray_a, gray_b, win_size=win, full=True)
    return score


def dedup_ssim(
    frames_dir: str,
    output_dir: str,
    threshold: float = 0.95,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> dict:
    frames = _list_frames(frames_dir)
    if not frames:
        return {"total": 0, "kept": 0, "output": ""}

    out_dir = _next_output_dir(output_dir)
    os.makedirs(out_dir, exist_ok=True)

    kept: list[str] = [frames[0]]
    prev = cv2.imread(frames[0])

    total = len(frames)
    for i in range(1, total):
        curr = cv2.imread(frames[i])
        if curr is None:
            continue
        score = _ssim_compare(prev, curr)
        if score < threshold:
            kept.append(frames[i])
            prev = curr
        if progress_cb:
            progress_cb(i / total)

    # 复制保留的帧到输出目录
    for src in kept:
        shutil.copy2(src, os.path.join(out_dir, os.path.basename(src)))

    if progress_cb:
        progress_cb(1.0)

    return {"total": total, "kept": len(kept), "output": out_dir}


# ─── pHash 去重 ───

def _phash(img: np.ndarray, hash_size: int = 16) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size))
    diff = resized[:, 1:] > resized[:, :-1]
    return diff.flatten()


def _hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def dedup_phash(
    frames_dir: str,
    output_dir: str,
    threshold: float = 0.95,
    progress_cb: Optional[Callable[[float], None]] = None,
):
    """threshold 0.95 → hamming distance < (1-0.95)*256 ≈ 12"""
    frames = _list_frames(frames_dir)
    if not frames:
        return {"total": 0, "kept": 0, "output": ""}

    out_dir = _next_output_dir(output_dir)
    os.makedirs(out_dir, exist_ok=True)

    max_dist = int((1.0 - threshold) * 256)

    kept: list[str] = [frames[0]]
    prev_img = cv2.imread(frames[0])
    prev_hash = _phash(prev_img)

    total = len(frames)
    for i in range(1, total):
        curr_img = cv2.imread(frames[i])
        if curr_img is None:
            continue
        curr_hash = _phash(curr_img)
        dist = _hamming(prev_hash, curr_hash)
        if dist > max_dist:
            kept.append(frames[i])
            prev_hash = curr_hash
        if progress_cb:
            progress_cb(i / total)

    for src in kept:
        shutil.copy2(src, os.path.join(out_dir, os.path.basename(src)))

    if progress_cb:
        progress_cb(1.0)

    return {"total": total, "kept": len(kept), "output": out_dir}


# ─── 统一入口 ───

def deduplicate(
    frames_dir: str,
    output_dir: str,
    method: str = "ssim",
    threshold: float = 0.95,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> dict:
    if method == "phash":
        return dedup_phash(frames_dir, output_dir, threshold, progress_cb)
    return dedup_ssim(frames_dir, output_dir, threshold, progress_cb)
