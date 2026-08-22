"""Crop 235 px from the left and right edges of every video in `videos/`."""

from __future__ import annotations

import subprocess
from pathlib import Path


# 脚本所在目录
SCRIPT_DIR = Path(__file__).resolve().parent
FFMPEG = "ffmpeg"
CROP_FILTER = "crop=iw-470:ih:235:0"


def crop_video(src: Path, dst: Path) -> None:
    cmd = [
        FFMPEG,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vf",
        CROP_FILTER,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "copy",
        "-map_metadata",
        "0",
        str(dst),
    ]
    result = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())


def crop_directory(src_dir: Path, dst_dir: Path) -> int:
    """批量裁剪目录中的所有视频"""
    dst_dir.mkdir(exist_ok=True)
    videos = sorted(src_dir.glob("*.mp4"))
    if not videos:
        print(f"No MP4 files found in {src_dir}")
        return 1

    for index, video in enumerate(videos, start=1):
        print(f"[{index}/{len(videos)}] {video.name}")
        crop_video(video, dst_dir / video.name)

    print(f"Done. {len(videos)} videos written to {dst_dir}")
    return 0


def main() -> int:
    src_dir = SCRIPT_DIR / "video"
    dst_dir = SCRIPT_DIR / "step01"
    return crop_directory(src_dir, dst_dir)


if __name__ == "__main__":
    raise SystemExit(main())