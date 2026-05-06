"""
管线状态检测 — 判断每个步骤是否已完成
"""

import json
from pathlib import Path


def get_completed_steps(project_dir: str) -> list[bool]:
    """返回 [step1_ok, step2_ok, step3_ok, step4_ok, step5_ok]"""
    p = Path(project_dir)
    steps = [False] * 5

    # Step 1: audio/*.mp3 + frames/*.jpg
    audio_ok = bool((p / "audio").is_dir() and list((p / "audio").glob("*.mp3")))
    frames_ok = (p / "frames").is_dir() and len(list((p / "frames").glob("*.jpg"))) > 0
    steps[0] = audio_ok and frames_ok

    # Step 2-4: unified JSON
    uj = _load_unified_json(p)
    steps[1] = uj is not None and bool(uj.get("segments"))

    # Step 3: key_frames/*.jpg
    steps[2] = (p / "key_frames").is_dir() and len(list((p / "key_frames").glob("*.jpg"))) > 0

    # Step 4: unified JSON has slides
    steps[3] = uj is not None and bool(uj.get("slides"))

    # Step 5: notes/*.md
    steps[4] = (p / "notes").is_dir() and len(list((p / "notes").glob("*.md"))) > 0

    return steps


def get_first_failed_step(project_dir: str) -> int:
    """返回第一个未完成步骤的索引 (0-4)，全完成返回 -1"""
    steps = get_completed_steps(project_dir)
    for i, ok in enumerate(steps):
        if not ok:
            return i
    return -1


def _load_unified_json(project_dir: Path) -> dict | None:
    for jp in project_dir.glob("*.json"):
        if jp.name.startswith("."):
            continue
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            if "segments" in data or "slides" in data:
                return data
        except Exception:
            continue
    return None
