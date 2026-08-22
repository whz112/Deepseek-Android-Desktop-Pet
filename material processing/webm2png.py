#!/usr/bin/env python3
"""提取 WebM 透明 PNG 序列（保留 Alpha 通道）"""

import subprocess
from pathlib import Path


def webm_to_png_sequence(webm_path, output_dir=None, start_frame=0, end_frame=None):
    webm_path = Path(webm_path)
    if not webm_path.exists():
        print(f"错误：文件 {webm_path} 不存在")
        return

    if output_dir is None:
        output_dir = webm_path.stem + "_frames"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建 ffmpeg 命令
    cmd = [
        "ffmpeg",
        "-c:v", "libvpx-vp9",  # 必须放在 -i 前
        "-i", str(webm_path),
        "-c:v", "png",
        "-pix_fmt", "rgba",
        "-start_number", str(start_frame),
    ]

    # 帧范围限制
    if end_frame is not None:
        cmd += ["-frames:v", str(end_frame - start_frame)]

    cmd.append(str(output_dir / "frame_%06d.png"))

    print(f"转换中... 输出到 {output_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"错误：{result.stderr}")
        return

    # 统计输出文件数
    pngs = list(output_dir.glob("*.png"))
    print(f"完成！共 {len(pngs)} 帧 -> {output_dir}")


if __name__ == "__main__":
    webm_to_png_sequence("searching.webm")