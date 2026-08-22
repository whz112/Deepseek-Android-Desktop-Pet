"""Transcode step03 masters into 360x360 playback thumbnails (step04).

现在支持通过命令行参数指定目标尺寸和帧率。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FFMPEG = "ffmpeg"
CRF = 40       # VP9 质量参数


def convert_video(src: Path, dst: Path, target: int, fps: int) -> None:
    cmd = [
        FFMPEG,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-c:v", "libvpx-vp9",   # 必须指定解码器才能保留 alpha
        "-i", str(src),
        "-vf", f"scale={target}:{target},format=yuva420p",
        "-c:v", "libvpx-vp9",
        "-crf", str(CRF),
        "-b:v", "0",
        "-row-mt", "1",
        "-r", str(fps),
        "-an",
        str(dst),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())


def transcode_thumbnails(src_dir: Path, dst_dir: Path, size: int = 400, fps: int = 24) -> int:
    """转码为播放缩略图

    Args:
        src_dir: 源视频目录
        dst_dir: 输出目录
        size: 输出正方形边长（像素）
        fps: 输出帧率
    """
    dst_dir.mkdir(exist_ok=True)
    videos = sorted(src_dir.glob("*.webm"))
    if not videos:
        print(f"No WebM masters found in {src_dir}")
        return 1

    total_src = total_dst = 0
    for idx, video in enumerate(videos, 1):
        src_size = video.stat().st_size
        total_src += src_size
        dst = dst_dir / video.name
        convert_video(video, dst, size, fps)
        dst_size = dst.stat().st_size
        total_dst += dst_size
        print(f"[{idx}/{len(videos)}] {video.name}  {src_size/1e6:.1f}MB -> {dst_size/1e6:.1f}MB")

    print(f"\n=== summary ===")
    print(f"输出分辨率: {size}x{size}")
    print(f"输出帧率: {fps} fps")
    print(f"源总大小: {total_src/1e6:.1f}MB")
    print(f"缩略图总大小: {total_dst/1e6:.1f}MB")
    return 0


def main() -> int:
    src_dir = SCRIPT_DIR / "step02"
    dst_dir = SCRIPT_DIR / "step04"
    return transcode_thumbnails(src_dir, dst_dir)


if __name__ == "__main__":
    raise SystemExit(main())