#!/usr/bin/env python3
"""Remove green backgrounds from step01 videos into transparent WebM files in step02/.
使用 OpenCV 逐帧处理，实现精确的边缘收缩和透明度优化。
新增羽化参数，可控制边缘过渡宽度。
"""

from __future__ import annotations

import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
FFMPEG = "ffmpeg"

# ---------- 去绿幕参数 ----------
GREEN_HUE_MIN = 40
GREEN_HUE_MAX = 80
SATURATION_MIN = 30
VALUE_MIN = 30

# ---------- 边缘收缩参数 ----------
ERODE_PIXELS = 2

# ---------- 羽化参数 ----------
FEATHER_RADIUS = 3          # 羽化半径（像素），数值越大边缘渐变越宽，设为0则保持原始小羽化

# ---------- 采样参数 ----------
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

# ---------- 后处理：强制删除颜色列表 (RGB) ----------
FORCE_REMOVE_COLORS = [
    (150, 167, 141),
    (163, 176, 195),
    (160, 172, 152),
]
FORCE_REMOVE_THRESHOLD = 50

# ---------- 白色描边参数 ----------
STROKE_WIDTH = 8                # 描边宽度（像素），设为0则关闭描边
STROKE_FEATHER_RADIUS = 5   # 描边羽化半径，可独立调节


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
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


def sample_background_color(video: Path) -> tuple[int, int, int]:
    """采样视频边缘的绿色背景色（返回 BGR）"""
    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-an",
        "-vf",
        f"fps=1,scale={WIDTH}:{HEIGHT}",
        "-frames:v",
        str(FRAMES_PER_VIDEO),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_size = WIDTH * HEIGHT * 3
    counter: Counter = Counter()

    for offset in range(0, len(result.stdout) - frame_size + 1, frame_size):
        frame = result.stdout[offset : offset + frame_size]
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if MARGIN_X <= x < WIDTH - MARGIN_X and MARGIN_Y <= y < HEIGHT - MARGIN_Y:
                    continue
                index = (y * WIDTH + x) * 3
                r, g, b = frame[index], frame[index + 1], frame[index + 2]
                hue, sat, val = rgb_to_hsv(r, g, b)
                if SAMPLE_GREEN_HUE_MIN <= hue <= SAMPLE_GREEN_HUE_MAX and sat >= SAMPLE_SATURATION_MIN and val >= SAMPLE_VALUE_MIN:
                    q = (r // QUANTIZE * QUANTIZE, g // QUANTIZE * QUANTIZE, b // QUANTIZE * QUANTIZE)
                    counter[q] += 1

    if not counter:
        raise RuntimeError(f"No green pixels found in border of {video.name}")
    (r, g, b), _ = counter.most_common(1)[0]
    return (b, g, r)  # 返回 BGR


def refine_dark_green_removal(rgba: np.ndarray, green_bgr: tuple,
                              mask_frame: np.ndarray = None,
                              dist_threshold: float = 40.0,
                              brightness_max: int = 100,
                              binary: bool = False) -> np.ndarray:
    """
    去除暗绿色残留（绿色与黑色的混合）。
    rgba: HxWx4 (RGBA, 0-255)
    green_bgr: 背景绿色 (B,G,R)
    mask_frame: 蒙版二值图，0=绿幕，255=前景（用于限制处理区域）
    binary: True 时处理所有 alpha>0 的像素（用于羽化前）；False 只处理边缘半透明区域（用于羽化后）
    """
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3].copy()

    if binary:
        edge_mask = alpha > 0
    else:
        edge_mask = (alpha > 20) & (alpha < 200)

    if mask_frame is not None:
        if mask_frame.shape[:2] != rgba.shape[:2]:
            mask_frame = cv2.resize(mask_frame, (rgba.shape[1], rgba.shape[0]), interpolation=cv2.INTER_NEAREST)
        # 只处理绿幕区域（mask_frame == 0）
        edge_mask = edge_mask & (mask_frame == 0)

    if not np.any(edge_mask):
        return rgba

    green_rgb = (green_bgr[2], green_bgr[1], green_bgr[0])  # BGR->RGB
    green_vec = np.array(green_rgb, dtype=np.float32)
    black_vec = np.array([0, 0, 0], dtype=np.float32)
    direction = black_vec - green_vec
    len_direction = np.linalg.norm(direction)
    if len_direction == 0:
        return rgba
    direction_unit = direction / len_direction

    pixels = rgb[edge_mask]
    diff = pixels - green_vec
    t = np.dot(diff, direction_unit)
    proj = green_vec + np.outer(t, direction_unit)
    perp_dist = np.linalg.norm(pixels - proj, axis=1)
    brightness = np.mean(pixels, axis=1)

    dark_green_mask = (perp_dist < dist_threshold) & (brightness < brightness_max) & (t >= 0) & (t <= 1)

    if np.any(dark_green_mask):
        mask_2d = np.zeros_like(alpha, dtype=bool)
        mask_2d[edge_mask] = dark_green_mask
        alpha[mask_2d] = 0

    rgba[:, :, 3] = alpha
    return rgba


def force_remove_colors(rgba: np.ndarray, color_list: list, threshold: float = 30.0, mask_frame: np.ndarray = None) -> np.ndarray:
    """
    强制删除颜色列表中匹配的像素。
    如果提供 mask_frame，则仅在 mask_frame == 0 的区域（绿幕区域）执行操作。
    rgba: HxWx4 (RGBA)
    color_list: 列表，元素为 (R, G, B)
    threshold: 欧氏距离阈值
    mask_frame: 单通道二值图，0=绿幕，255=前景
    """
    if not color_list:
        return rgba

    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3].copy()

    valid_mask = alpha > 0

    if mask_frame is not None:
        if mask_frame.shape[:2] != rgba.shape[:2]:
            mask_frame = cv2.resize(mask_frame, (rgba.shape[1], rgba.shape[0]), interpolation=cv2.INTER_NEAREST)
        green_region = (mask_frame == 0)
        valid_mask = valid_mask & green_region

    if not np.any(valid_mask):
        return rgba

    pixels = rgb[valid_mask]
    matched = np.zeros(pixels.shape[0], dtype=bool)

    for target_rgb in color_list:
        target = np.array(target_rgb, dtype=np.float32)
        dist = np.linalg.norm(pixels - target, axis=1)
        matched |= (dist < threshold)

    if np.any(matched):
        mask_2d = np.zeros_like(alpha, dtype=bool)
        flat_valid = valid_mask.flatten()
        flat_matched = np.zeros_like(flat_valid, dtype=bool)
        idx_valid = np.where(flat_valid)[0]
        flat_matched[idx_valid] = matched
        mask_2d = flat_matched.reshape(alpha.shape)
        alpha[mask_2d] = 0

    rgba[:, :, 3] = alpha
    return rgba


def remove_green_background_opencv(frame: np.ndarray, green_bgr: tuple[int, int, int],
                                   erode_pixels: int = 3, mask_frame: np.ndarray = None) -> np.ndarray:
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    green_bgr_np = np.uint8([[green_bgr]])
    green_hsv = cv2.cvtColor(green_bgr_np, cv2.COLOR_BGR2HSV)[0][0]
    lower_green = np.array([max(0, green_hsv[0] - 15), 30, 30])
    upper_green = np.array([min(180, green_hsv[0] + 15), 255, 255])

    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((3, 3), np.uint8)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    # 二值 alpha（前景为255，背景为0）
    alpha = cv2.bitwise_not(green_mask)

    # 边缘收缩（侵蚀）
    if erode_pixels > 0:
        erode_kernel = np.ones((erode_pixels * 2 + 1, erode_pixels * 2 + 1), np.uint8)
        alpha = cv2.erode(alpha, erode_kernel, iterations=1)

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgba = np.dstack((rgb_frame, alpha))

    # 后处理（暗绿去除、强制删除颜色）—— 在羽化前执行
    rgba = refine_dark_green_removal(rgba, green_bgr, mask_frame,
                                     dist_threshold=30.0, brightness_max=80, binary=True)
    rgba = force_remove_colors(rgba, FORCE_REMOVE_COLORS, FORCE_REMOVE_THRESHOLD, mask_frame)

    # 提取处理后的 alpha（仍为二值）
    alpha = rgba[:, :, 3].copy()

    # ---------- 保存二值掩码（用于描边） ----------
    binary_mask = alpha.copy()  # uint8, 0/255

    # ---------- 角色羽化 ----------
    if FEATHER_RADIUS > 0:
        ksize = (FEATHER_RADIUS * 2 + 1, FEATHER_RADIUS * 2 + 1)
        sigma = FEATHER_RADIUS / 3.0
        alpha_blurred = cv2.GaussianBlur(alpha.astype(np.float32), ksize, sigma)
    else:
        alpha_blurred = cv2.GaussianBlur(alpha.astype(np.float32), (3, 3), 0.5)

    # 归一化角色 alpha（0~1）
    alpha_f = alpha_blurred / 255.0

    # ---------- 白色描边生成 ----------
    if STROKE_WIDTH > 0:
        # 膨胀得到外部区域
        stroke_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (STROKE_WIDTH * 2 + 1, STROKE_WIDTH * 2 + 1))
        dilated = cv2.dilate(binary_mask, stroke_kernel)
        stroke_mask = cv2.subtract(dilated, binary_mask)  # 仅外部区域（0/255）

        # 描边羽化
        if STROKE_FEATHER_RADIUS > 0:
            ksize_stroke = (STROKE_FEATHER_RADIUS * 2 + 1, STROKE_FEATHER_RADIUS * 2 + 1)
            sigma_stroke = STROKE_FEATHER_RADIUS / 3.0
            stroke_alpha = cv2.GaussianBlur(stroke_mask.astype(np.float32), ksize_stroke, sigma_stroke)
        else:
            stroke_alpha = stroke_mask.astype(np.float32)
        stroke_f = stroke_alpha / 255.0

        # 合成：最终透明度 = 角色透明度 + 描边透明度*(1-角色透明度)
        final_alpha_f = alpha_f + stroke_f * (1 - alpha_f)
        final_alpha = (final_alpha_f * 255).astype(np.uint8)

        # 合成颜色：角色颜色 + 白色描边
        result_rgb = rgb_frame.astype(np.float32) * alpha_f[..., np.newaxis] + \
                     255.0 * stroke_f[..., np.newaxis] * (1 - alpha_f[..., np.newaxis])
        result_rgb = np.clip(result_rgb, 0, 255).astype(np.uint8)

        rgba = np.dstack((result_rgb, final_alpha))
    else:
        # 无描边，直接使用羽化后的 alpha
        rgba = np.dstack((rgb_frame, alpha_blurred.astype(np.uint8)))

    return rgba


def process_video_with_opencv(src: Path, dst: Path, masks_dir: Path, green_bgr: tuple[int, int, int]) -> None:
    """处理单个视频，同步读取蒙版视频"""
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {src}")

    mask_video_path = masks_dir / (src.stem + "_mask.mp4")
    if not mask_video_path.exists():
        raise FileNotFoundError(f"Mask video not found: {mask_video_path}")
    cap_mask = cv2.VideoCapture(str(mask_video_path))
    if not cap_mask.isOpened():
        raise RuntimeError(f"Cannot open mask video: {mask_video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"  📹 {width}x{height}, {fps:.1f} fps, {total_frames} frames")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        saved_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            ret_mask, mask_frame = cap_mask.read()
            if not ret_mask:
                raise RuntimeError(f"Mask video ended early at frame {saved_count}")

            if len(mask_frame.shape) == 3:
                mask_frame = cv2.cvtColor(mask_frame, cv2.COLOR_BGR2GRAY)
            # 确保蒙版为严格的二值图
            _, mask_frame = cv2.threshold(mask_frame, 127, 255, cv2.THRESH_BINARY)

            rgba = remove_green_background_opencv(frame, green_bgr, ERODE_PIXELS, mask_frame)

            output_path = tmp_path / f"frame_{saved_count:05d}.png"
            pil_img = Image.fromarray(rgba, 'RGBA')
            pil_img.save(output_path, "PNG")

            saved_count += 1
            if saved_count % 50 == 0:
                print(f"    已处理 {saved_count}/{total_frames} 帧")

        cap.release()
        cap_mask.release()

        print(f"    共保存 {saved_count} 帧")

        # 使用 FFmpeg 编码为 WebM
        cmd = [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            str(tmp_path / "frame_%05d.png"),
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "30",
            "-b:v",
            "0",
            "-auto-alt-ref",
            "0",
            "-deadline",
            "good",
            "-cpu-used",
            "4",
            "-pix_fmt",
            "yuva420p",
            str(dst),
        ]
        result = subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg encoding failed: {result.stderr.strip()}")


def remove_green_screen(src_dir: Path, dst_dir: Path, masks_dir: Path) -> int:
    """批量去绿幕处理"""
    dst_dir.mkdir(exist_ok=True)
    videos = sorted(src_dir.glob("*.mp4"))
    if not videos:
        print(f"No MP4 files found in {src_dir}")
        return 1

    print(f"🔧 边缘收缩像素数: {ERODE_PIXELS}")
    print(f"🪶 羽化半径: {FEATHER_RADIUS} 像素")
    print(f"📐 处理方式: OpenCV 逐帧处理（后处理在羽化前）")

    for index, video in enumerate(videos, start=1):
        print(f"[{index}/{len(videos)}] {video.name}", flush=True)

        green_bgr = sample_background_color(video)
        print(f"  🎨 采样绿色: BGR{green_bgr}")

        dst = dst_dir / (video.stem + ".webm")
        process_video_with_opencv(video, dst, masks_dir, green_bgr)
        print(f"  ✅ 完成 -> {dst.name}")

    print(f"Done. {len(videos)} videos written to {dst_dir}")
    return 0


def main() -> int:
    src_dir = SCRIPT_DIR / "step01"
    dst_dir = SCRIPT_DIR / "step02"
    masks_dir = SCRIPT_DIR / "masks"
    return remove_green_screen(src_dir, dst_dir, masks_dir)


if __name__ == "__main__":
    raise SystemExit(main())