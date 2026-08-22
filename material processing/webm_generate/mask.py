#!/usr/bin/env python3
"""
Generate a binary mask video from green-screen MP4 files.
Non-green areas become white (255), green areas become black (0).
"""

import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

# ========== 配置 ==========
SCRIPT_DIR = Path(__file__).resolve().parent
FFMPEG = "ffmpeg"

# 蒙版颜色（非绿幕区域颜色，绿幕区域为相反）
FOREGROUND_COLOR = 255   # 白色
BACKGROUND_COLOR = 0     # 黑色

# 采样参数（与 chroma_step02.py 一致）
WIDTH = 320
HEIGHT = 180
MARGIN_X = WIDTH // 10
MARGIN_Y = HEIGHT // 10
FRAMES_PER_VIDEO = 10
QUANTIZE = 8

SAMPLE_GREEN_HUE_MIN = 70.0
SAMPLE_GREEN_HUE_MAX = 170.0
SAMPLE_SATURATION_MIN = 0.15
SAMPLE_VALUE_MIN = 0.15

# HSV 容差（围绕采样绿色）
HUE_TOLERANCE = 15
SATURATION_MIN = 5
VALUE_MIN = 5

# 形态学参数
MORPH_OPEN_ITER = 1
MORPH_CLOSE_ITER = 1
KERNEL_SIZE = 3

# ========== 辅助函数 ==========
def rgb_to_hsv(r, g, b):
    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
    mx = max(rn, gn, bn)
    mn = min(rn, gn, bn)
    delta = mx - mn
    if delta == 0:
        return 0.0, 0.0, mx
    if mx == rn:
        hue = 60.0 * (((gn - bn) / delta) % 6.0)
    elif mx == gn:
        hue = 60.0 * (((bn - rn) / delta) + 2.0)
    else:
        hue = 60.0 * (((rn - gn) / delta) + 4.0)
    saturation = delta / mx if mx else 0.0
    return hue, saturation, mx

def sample_background_color(video_path):
    """采样视频边缘的绿色（返回 BGR）"""
    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error",
        "-i", str(video_path), "-an",
        "-vf", f"fps=1,scale={WIDTH}:{HEIGHT}",
        "-frames:v", str(FRAMES_PER_VIDEO),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size = WIDTH * HEIGHT * 3
    counter = Counter()
    for offset in range(0, len(result.stdout) - frame_size + 1, frame_size):
        frame = result.stdout[offset:offset + frame_size]
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if MARGIN_X <= x < WIDTH - MARGIN_X and MARGIN_Y <= y < HEIGHT - MARGIN_Y:
                    continue
                idx = (y * WIDTH + x) * 3
                r, g, b = frame[idx], frame[idx+1], frame[idx+2]
                hue, sat, val = rgb_to_hsv(r, g, b)
                if (SAMPLE_GREEN_HUE_MIN <= hue <= SAMPLE_GREEN_HUE_MAX and
                    sat >= SAMPLE_SATURATION_MIN and val >= SAMPLE_VALUE_MIN):
                    q = (r//QUANTIZE*QUANTIZE, g//QUANTIZE*QUANTIZE, b//QUANTIZE*QUANTIZE)
                    counter[q] += 1
    if not counter:
        raise RuntimeError(f"No green pixels found in border of {video_path.name}")
    (r, g, b), _ = counter.most_common(1)[0]
    return (b, g, r)   # BGR

def generate_mask_frame(frame, green_bgr):
    """生成单帧蒙版（前景=255，背景=0）"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    green_bgr_np = np.uint8([[green_bgr]])
    green_hsv = cv2.cvtColor(green_bgr_np, cv2.COLOR_BGR2HSV)[0][0]
    lower = np.array([max(0, green_hsv[0] - HUE_TOLERANCE), SATURATION_MIN, VALUE_MIN])
    upper = np.array([min(180, green_hsv[0] + HUE_TOLERANCE), 255, 255])
    mask = cv2.inRange(hsv, lower, upper)   # 绿幕区域为255

    # 形态学清理
    kernel = np.ones((KERNEL_SIZE, KERNEL_SIZE), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=MORPH_OPEN_ITER)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=MORPH_CLOSE_ITER)

    # 反转：前景为255，背景为0
    mask = cv2.bitwise_not(mask)
    return mask

def process_video(src_path, dst_path):
    """处理单个视频，生成蒙版视频"""
    cap = cv2.VideoCapture(str(src_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {src_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  📹 {width}x{height}, {fps:.1f} fps, {total_frames} frames")

    # 采样背景色
    green_bgr = sample_background_color(src_path)
    print(f"  🎨 采样绿色: BGR{green_bgr}")

    # 使用临时文件夹存储 PNG 序列（便于高质量编码）
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        saved = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            mask = generate_mask_frame(frame, green_bgr)
            # 保存为灰度 PNG
            out_png = tmp_path / f"frame_{saved:05d}.png"
            cv2.imwrite(str(out_png), mask)   # mask 是单通道 uint8
            saved += 1
            if saved % 50 == 0:
                print(f"    已处理 {saved}/{total_frames} 帧")
        cap.release()
        print(f"    共保存 {saved} 帧")

        # 用 ffmpeg 编码为 MP4（灰度）
        cmd = [
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(fps),
            "-i", str(tmp_path / "frame_%05d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "gray",
            "-crf", "18",
            str(dst_path)
        ]
        subprocess.run(cmd, check=True)

def generate_masks(src_dir: Path, dst_dir: Path) -> int:
    """批量生成蒙版视频"""
    dst_dir.mkdir(exist_ok=True)
    videos = sorted(src_dir.glob("*.mp4"))
    if not videos:
        print(f"No MP4 files found in {src_dir}")
        return 1

    for idx, video in enumerate(videos, 1):
        print(f"[{idx}/{len(videos)}] {video.name}")
        dst = dst_dir / (video.stem + "_mask.mp4")
        process_video(video, dst)
        print(f"  ✅ 蒙版生成 -> {dst.name}")

    print(f"Done. All masks saved to {dst_dir}")
    return 0

def main() -> int:
    src_dir = SCRIPT_DIR / "step01"
    dst_dir = SCRIPT_DIR / "masks"
    return generate_masks(src_dir, dst_dir)

if __name__ == "__main__":
    raise SystemExit(main())