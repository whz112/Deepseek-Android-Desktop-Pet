#!/usr/bin/env python3
"""
去除 WebM 视频左右边缘的水印（将指定宽度的像素变为透明），
并可选地将图像内容水平偏移（平移），以调整画面位置。
直接修改下方配置变量后运行即可。
依赖：ffmpeg, opencv-python, 以及同目录下的 webm2png.py 和 png2webm.py
"""

import os
import shutil
import tempfile
import subprocess
from pathlib import Path

import cv2
import numpy as np

# 导入已有的转换函数（确保这两个文件在同一目录）
from webm2png import webm_to_png_sequence
from png2webm import png_to_webm

# ==================== 用户配置区域 ====================
INPUT_WEBM = "output/searching.webm"           # 输入的 WebM 文件路径
OUTPUT_WEBM = "searching.webm"                 # 输出的 WebM 文件路径
LEFT_MARGIN = 0                               # 左侧要透明的像素宽度
RIGHT_MARGIN = 0                               # 右侧要透明的像素宽度
SHIFT_OFFSET = -30                               # 水平偏移量（像素）：正数→内容右移，负数→内容左移
FPS = 24                                       # 输出帧率（None 则自动从原视频读取）
KEEP_TEMP = False                              # 是否保留临时帧目录（调试用）
# =====================================================


def get_video_fps(video_path):
    """使用 ffprobe 获取视频帧率"""
    try:
        cmd = [
            'ffprobe', '-v', '0', '-of', 'csv=p=0',
            '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fps_str = result.stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            return float(num) / float(den)
        else:
            return float(fps_str)
    except Exception:
        return None


def remove_edges_alpha(image, left, right):
    """
    将图像左边缘 left 像素和右边缘 right 像素范围内的 Alpha 通道设为 0（完全透明）
    如果图像没有 Alpha 通道，则添加一个全不透明白色通道后再操作
    """
    h, w = image.shape[:2]
    if image.shape[2] == 3:
        # 添加 alpha 通道，初始为 255（不透明）
        alpha = np.full((h, w, 1), 255, dtype=image.dtype)
        img = np.concatenate([image, alpha], axis=2)
    else:
        img = image.copy()

    # 左边缘
    if left > 0:
        img[:, :min(left, w), 3] = 0
    # 右边缘
    if right > 0:
        img[:, max(0, w - right):w, 3] = 0

    return img


def shift_image_alpha(image, shift):
    """
    水平平移图像内容，同时保持尺寸不变，空缺处用透明填充。
    shift > 0：内容向右移动，左侧填充透明，右侧裁剪
    shift < 0：内容向左移动，右侧填充透明，左侧裁剪
    """
    if shift == 0:
        return image

    h, w = image.shape[:2]
    # 全透明背景
    new_img = np.zeros_like(image)

    if shift > 0:
        # 右移：取源图像左侧 (w - shift) 宽，放到目标右侧
        src_w = w - shift
        if src_w <= 0:
            return new_img  # 全部移出，全透明
        new_img[:, shift:shift + src_w] = image[:, :src_w]
    else:  # shift < 0
        shift_abs = -shift
        src_w = w - shift_abs
        if src_w <= 0:
            return new_img
        new_img[:, :src_w] = image[:, shift_abs:]

    return new_img


def process_frames(frames_dir, left_margin, right_margin, shift_offset):
    """
    对 frames_dir 下的所有 PNG 执行：
      1. 边缘透明化
      2. 水平偏移（若 shift_offset != 0）
    直接覆盖原文件
    """
    png_files = sorted(Path(frames_dir).glob("*.png"))
    if not png_files:
        print(f"❌ 在 {frames_dir} 中未找到 PNG 帧")
        return False

    print(f"开始处理 {len(png_files)} 帧，左边缘 {left_margin}px，右边缘 {right_margin}px 设为透明")
    if shift_offset:
        print(f"并应用水平偏移：{shift_offset:+d}px")
    for idx, png_path in enumerate(png_files, 1):
        img = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"⚠️ 无法读取 {png_path}，跳过")
            continue
        # 1. 去除边缘水印（透明化）
        processed = remove_edges_alpha(img, left_margin, right_margin)
        # 2. 水平偏移（如有）
        if shift_offset != 0:
            processed = shift_image_alpha(processed, shift_offset)
        cv2.imwrite(str(png_path), processed)
        if idx % 50 == 0:
            print(f"  已处理 {idx}/{len(png_files)} 帧")
    print("✅ 所有帧处理完成")
    return True


def main():
    input_path = Path(INPUT_WEBM)
    output_path = Path(OUTPUT_WEBM)

    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_path}")
        return

    if LEFT_MARGIN == 0 and RIGHT_MARGIN == 0 and SHIFT_OFFSET == 0:
        print("⚠️ 警告：左右边距和偏移量均为 0，将不会修改任何像素")

    # 获取原始帧率
    if FPS is None:
        fps = get_video_fps(input_path)
        if fps is None:
            print("⚠️ 无法获取输入视频帧率，使用默认 15 fps")
            fps = 15
        else:
            print(f"检测到原始帧率: {fps:.2f} fps")
    else:
        fps = FPS

    # 创建临时目录存放帧
    temp_dir = tempfile.mkdtemp(prefix="webm_watermark_")
    print(f"临时帧目录: {temp_dir}")

    try:
        # 1. 拆帧为 PNG
        print("\n[1/3] 拆解 WebM 为 PNG 序列...")
        webm_to_png_sequence(str(input_path), output_dir=temp_dir, start_frame=0, end_frame=None)

        # 2. 处理每一帧：边缘透明 + 偏移
        print("\n[2/3] 处理帧边缘及偏移...")
        success = process_frames(temp_dir, LEFT_MARGIN, RIGHT_MARGIN, SHIFT_OFFSET)
        if not success:
            print("❌ 帧处理失败")
            return

        # 3. 重新合成 WebM
        print("\n[3/3] 合成新的 WebM...")
        result = png_to_webm(str(temp_dir), str(output_path), fps)
        if result:
            print(f"✅ 成功生成 {output_path}")
        else:
            print("❌ 合成失败")

    finally:
        if not KEEP_TEMP:
            print("清理临时目录...")
            shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            print(f"保留临时目录: {temp_dir}")


if __name__ == "__main__":
    main()