#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PNG序列前帧亮度平滑 + 边界插帧工具

功能：
  1. 根据指定的尾帧图片，对输入序列的前若干帧进行亮度平滑处理，
     使前几帧亮度逐渐过渡到尾帧亮度。
  2. 在平滑区域与未平滑区域的边界处自动插入若干过渡帧，
     使动作和亮度同时平滑过渡（基于 Farneback 光流）。
  所有操作均保留 Alpha 通道（透明度）。
"""

import cv2
import numpy as np
import os
import glob
import re
from PIL import Image


# ==================== 辅助函数 ====================

def natural_sort_key(s):
    """自然排序"""
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', s)]


def read_image_robust(filepath):
    """
    读取图像，保留 Alpha 通道
    返回: (BGR图像, Alpha通道)
    """
    # 方法1: 使用PIL读取（保留透明度）
    try:
        img = Image.open(filepath)
        img_array = np.array(img)
        if img_array.shape[-1] == 4:
            rgb = img_array[:, :, :3]
            alpha = img_array[:, :, 3]
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return bgr, alpha
        elif img_array.shape[-1] == 3:
            rgb = img_array
            alpha = np.ones((img_array.shape[0], img_array.shape[1]), dtype=np.uint8) * 255
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return bgr, alpha
        else:
            alpha = np.ones((img_array.shape[0], img_array.shape[1]), dtype=np.uint8) * 255
            bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            return bgr, alpha
    except Exception:
        pass

    # 方法2: 使用OpenCV读取（保留透明度）
    try:
        img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        if img is not None:
            if img.shape[-1] == 4:
                bgr = img[:, :, :3]
                alpha = img[:, :, 3]
                return bgr, alpha
            else:
                bgr = img
                alpha = np.ones((img.shape[0], img.shape[1]), dtype=np.uint8) * 255
                return bgr, alpha
    except Exception:
        pass

    return None, None


def read_images_from_folder(folder, extension='png'):
    """读取序列图像，保留Alpha通道"""
    folder = os.path.normpath(folder)
    search_pattern = os.path.join(folder, f'*.{extension}')
    files = glob.glob(search_pattern)

    if not files:
        print(f"错误: 在 {folder} 中没有找到 .{extension} 图像文件")
        return [], [], []

    files = sorted(files, key=natural_sort_key)
    print(f"找到 {len(files)} 个图像文件")

    images = []
    alphas = []
    valid_files = []

    for i, f in enumerate(files):
        bgr, alpha = read_image_robust(f)
        if bgr is not None and alpha is not None:
            images.append(bgr)
            alphas.append(alpha)
            valid_files.append(f)
            if (i + 1) % 50 == 0:
                print(f"已读取 {i + 1}/{len(files)} 张图像...")
        else:
            print(f"警告: 无法读取文件 {os.path.basename(f)}")

    if len(images) == 0:
        print("\n错误: 没有找到有效的图像文件")
        return [], [], []

    print(f"\n成功读取 {len(images)} 张有效图像")
    return images, alphas, valid_files


def blend_brightness_simple(img1, alpha1, img2, alpha2, weight):
    """
    简单的亮度混合：保持内容位置不变，仅调整亮度。
    通过整体缩放 img2 的亮度使其接近 img1 的亮度，然后按 weight 混合。
    返回混合后的 BGR 和 Alpha。
    """
    if img1.shape != img2.shape:
        print("警告: 图像尺寸不一致，跳过混合")
        return img1.copy(), alpha1.copy()

    # 转换为浮点数便于计算
    a1 = alpha1.astype(np.float32) / 255.0
    a2 = alpha2.astype(np.float32) / 255.0

    # 计算灰度平均亮度（仅统计非透明区域）
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY).astype(np.float32)

    mean1 = np.sum(gray1 * a1) / (np.sum(a1) + 1e-6)
    mean2 = np.sum(gray2 * a2) / (np.sum(a2) + 1e-6)

    if mean1 < 1:
        mean1 = 1
    if mean2 < 1:
        mean2 = 1

    brightness_ratio = mean1 / mean2
    target_ratio = 1.0 + (brightness_ratio - 1.0) * weight

    adjusted_img2 = np.clip(img2.astype(np.float32) * target_ratio, 0, 255).astype(np.uint8)

    blended_alpha = ((1 - weight) * alpha1.astype(np.float32) +
                     weight * alpha2.astype(np.float32)).astype(np.uint8)

    a1_exp = np.expand_dims(alpha1.astype(np.float32) / 255.0, axis=2)
    a2_exp = np.expand_dims(alpha2.astype(np.float32) / 255.0, axis=2)

    denominator = (1 - weight) * a1_exp + weight * a2_exp + 1e-6
    blended_bgr = ((1 - weight) * img1.astype(np.float32) * a1_exp +
                   weight * adjusted_img2.astype(np.float32) * a2_exp) / denominator
    blended_bgr = np.clip(blended_bgr, 0, 255).astype(np.uint8)

    return blended_bgr, blended_alpha


def smooth_front_frames(seq_bgr, seq_alpha, tail_bgr, tail_alpha, blend_frames):
    """
    对序列的前 blend_frames 帧进行光流变形 + 亮度混合，
    使首帧完全变成尾帧，然后逐渐恢复原始（反向过渡）。
    返回调整后的序列（BGR列表和Alpha列表）。
    """
    total = len(seq_bgr)
    if total == 0:
        return [], []

    blend_frames = min(blend_frames, total)
    print(f"\n将对前 {blend_frames} 帧进行反向光流变形和亮度平滑（首帧变成尾帧）")

    new_seq_bgr = [img.copy() for img in seq_bgr]
    new_seq_alpha = [alpha.copy() for alpha in seq_alpha]

    if blend_frames == 1:
        # 仅一帧，直接替换为尾帧（t=1）
        print("  仅一帧，直接替换为尾帧")
        new_seq_bgr[0] = tail_bgr.copy()
        new_seq_alpha[0] = tail_alpha.copy()
        return new_seq_bgr, new_seq_alpha

    for i in range(blend_frames):
        # 反向映射：i=0 → t=1, i=blend_frames-1 → t=0
        t = 1.0 - i / (blend_frames - 1)
        print(f"  帧 {i + 1:>3d} 变形系数: {t:.3f}")

        # 计算从当前帧到尾帧的光流
        flow_x, flow_y = compute_optical_flow(seq_bgr[i], tail_bgr)

        # 扭曲当前帧和 Alpha 向尾帧移动 t 比例
        warped_bgr, warped_alpha = warp_with_flow(seq_bgr[i], seq_alpha[i],
                                                  flow_x, flow_y, t)

        # 将扭曲后的帧与尾帧按 t 线性混合（考虑 Alpha）
        w_bgr = warped_bgr.astype(np.float32)
        w_alpha = warped_alpha.astype(np.float32) / 255.0
        t_bgr = tail_bgr.astype(np.float32)
        t_alpha = tail_alpha.astype(np.float32) / 255.0

        w_alpha3 = np.expand_dims(w_alpha, axis=2)
        t_alpha3 = np.expand_dims(t_alpha, axis=2)

        denom = (1 - t) * w_alpha3 + t * t_alpha3 + 1e-6
        mixed_bgr = ((1 - t) * w_bgr * w_alpha3 + t * t_bgr * t_alpha3) / denom
        mixed_bgr = np.clip(mixed_bgr, 0, 255).astype(np.uint8)

        mixed_alpha = ((1 - t) * w_alpha + t * t_alpha) * 255
        mixed_alpha = mixed_alpha.astype(np.uint8)

        new_seq_bgr[i] = mixed_bgr
        new_seq_alpha[i] = mixed_alpha

    return new_seq_bgr, new_seq_alpha


# ==================== 光流插帧 ====================

def compute_optical_flow(img1, img2):
    """计算稠密光流（Farneback）"""
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(
        gray1, gray2, None,
        pyr_scale=0.5,
        levels=5,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=cv2.OPTFLOW_FARNEBACK_GAUSSIAN
    )
    return flow[:, :, 0], flow[:, :, 1]


def warp_with_flow(img, alpha, flow_x, flow_y, t):
    """根据光流场扭曲图像到时间 t (0~1)"""
    h, w = img.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    warp_x = x + flow_x * t
    warp_y = y + flow_y * t
    warp_x = np.clip(warp_x, 0, w - 1)
    warp_y = np.clip(warp_y, 0, h - 1)
    warped_img = cv2.remap(img, warp_x, warp_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if alpha is not None:
        warped_alpha = cv2.remap(alpha, warp_x, warp_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    else:
        warped_alpha = np.ones((h, w), dtype=np.uint8) * 255
    return warped_img, warped_alpha


def interpolate_between_images(img1, alpha1, img2, alpha2, t, flow_x=None, flow_y=None):
    """
    在两张图之间生成插值帧（t=0 为 img1，t=1 为 img2）
    若未提供光流，则自动计算从 img1 到 img2 的光流
    """
    if flow_x is None or flow_y is None:
        flow_x, flow_y = compute_optical_flow(img1, img2)

    # 将两张图都向中间扭曲
    warped1, warped_a1 = warp_with_flow(img1, alpha1, flow_x, flow_y, -t / 2)
    warped2, warped_a2 = warp_with_flow(img2, alpha2, flow_x, flow_y, (1 - t) / 2)

    a1 = warped_a1.astype(np.float32) / 255.0
    a2 = warped_a2.astype(np.float32) / 255.0
    a1_exp = np.expand_dims(a1, axis=2)
    a2_exp = np.expand_dims(a2, axis=2)

    denom = (1 - t) * a1_exp + t * a2_exp + 1e-6
    blended = ((1 - t) * warped1.astype(np.float32) * a1_exp +
               t * warped2.astype(np.float32) * a2_exp) / denom
    blended = np.clip(blended, 0, 255).astype(np.uint8)

    blended_alpha = ((1 - t) * a1 + t * a2) * 255
    blended_alpha = blended_alpha.astype(np.uint8)

    return blended, blended_alpha


def generate_intermediate_frames(img1, alpha1, img2, alpha2, n):
    """在 img1 和 img2 之间生成 n 个均匀分布的中间帧（不包括两端）"""
    if n <= 0:
        return [], []
    flow_x, flow_y = compute_optical_flow(img1, img2)
    interp_bgr, interp_alpha = [], []
    for i in range(1, n + 1):
        t = i / (n + 1)
        bgr, alpha = interpolate_between_images(img1, alpha1, img2, alpha2, t, flow_x, flow_y)
        interp_bgr.append(bgr)
        interp_alpha.append(alpha)
    return interp_bgr, interp_alpha


def save_sequence_ordered(images, alphas, output_dir, start_index=1):
    """按顺序保存为 frame_000001.png ..."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    total = len(images)
    for idx, (bgr, alpha) in enumerate(zip(images, alphas), start=start_index):
        rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = alpha
        filename = f"frame_{idx:06d}.png"
        out_path = os.path.join(output_dir, filename)
        cv2.imwrite(out_path, rgba)
        if (idx - start_index + 1) % 50 == 0:
            print(f"  已保存 {idx - start_index + 1}/{total}")
    print(f"成功保存 {total} 张透明 PNG 到 {output_dir}")


# ==================== 主函数 ====================

def smooth_front_with_tail(
        tail_image: str,
        input_folder: str,
        output_folder: str,
        blend_frames: int = 7,
        extension: str = "png",
        interp_frames: int = None
) -> bool:
    """
    对序列前几帧进行亮度平滑（参考尾帧），并在边界插帧

    Args:
        tail_image: 尾帧图片路径（作为亮度参考）
        input_folder: 输入序列文件夹
        output_folder: 输出文件夹
        blend_frames: 需要平滑的前几帧数量
        extension: 图片扩展名，默认png
        interp_frames: 插帧数量，None则自动为 blend_frames - 2

    Returns:
        bool: 处理成功返回True，失败返回False
    """
    print("=" * 60)
    print("序列前几帧亮度平滑 + 边界自动插帧")
    print("=" * 60)

    # 显示当前配置
    print(f"\n配置参数:")
    print(f"  尾帧图片: {tail_image}")
    print(f"  输入文件夹: {input_folder}")
    print(f"  输出文件夹: {output_folder}")
    print(f"  平滑帧数: {blend_frames}")
    print(f"  图片扩展名: {extension}")

    if interp_frames is None:
        interp_num = max(0, blend_frames - 2)
        print(f"  插帧数量: 自动 (BLEND_FRAMES - 2 = {interp_num})")
    else:
        interp_num = max(0, interp_frames)
        print(f"  插帧数量: 用户指定 = {interp_num}")

    # 1. 读取尾帧
    print(f"\n读取尾帧: {tail_image}")
    tail_bgr, tail_alpha = read_image_robust(tail_image)
    if tail_bgr is None:
        print(f"错误: 无法读取尾帧文件 {tail_image}")
        return False
    print(f"尾帧尺寸: {tail_bgr.shape[1]}x{tail_bgr.shape[0]}, 带Alpha: {tail_alpha is not None}")

    # 2. 读取序列
    print(f"\n读取序列: {input_folder}")
    seq_bgr, seq_alpha, file_paths = read_images_from_folder(input_folder, extension)
    if len(seq_bgr) == 0:
        print("错误: 未读取到有效序列帧")
        return False

    total_orig = len(seq_bgr)
    print(f"原始序列总帧数: {total_orig}")

    # 3. 检查尺寸，若不一致则调整尾帧尺寸
    h, w = seq_bgr[0].shape[:2]
    th, tw = tail_bgr.shape[:2]
    if (h, w) != (th, tw):
        print(f"\n警告: 尾帧尺寸 ({tw}x{th}) 与序列帧尺寸 ({w}x{h}) 不一致，将尾帧 resize 到序列尺寸")
        tail_bgr = cv2.resize(tail_bgr, (w, h), interpolation=cv2.INTER_LINEAR)
        if tail_alpha is not None:
            tail_alpha = cv2.resize(tail_alpha, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            tail_alpha = np.ones((h, w), dtype=np.uint8) * 255

    # 4. 执行亮度平滑
    smoothed_bgr, smoothed_alpha = smooth_front_frames(
        seq_bgr, seq_alpha,
        tail_bgr, tail_alpha,
        blend_frames
    )

    # 5. 自动插帧（在平滑区域和未平滑区域之间）
    if interp_num > 0 and blend_frames < total_orig:
        left_idx = blend_frames - 1
        right_idx = blend_frames
        print(f"\n在边界帧 {left_idx + 1} 和 {right_idx + 1} 之间插入 {interp_num} 个过渡帧...")
        interp_bgr, interp_alpha = generate_intermediate_frames(
            smoothed_bgr[left_idx], smoothed_alpha[left_idx],
            smoothed_bgr[right_idx], smoothed_alpha[right_idx],
            interp_num
        )
        print(f"成功生成 {len(interp_bgr)} 个插帧")

        # 构建新序列
        new_bgr = smoothed_bgr[:left_idx + 1] + interp_bgr + smoothed_bgr[right_idx:]
        new_alpha = smoothed_alpha[:left_idx + 1] + interp_alpha + smoothed_alpha[right_idx:]
        total_new = len(new_bgr)
        print(f"新序列总帧数: {total_new} (原 {total_orig} 帧 + 新增 {total_new - total_orig} 帧)")
    else:
        # 无需插帧，直接使用平滑结果
        new_bgr = smoothed_bgr
        new_alpha = smoothed_alpha
        total_new = len(new_bgr)
        if interp_num > 0 and blend_frames >= total_orig:
            print("警告: 平滑帧数 >= 总帧数，无边界可插帧，将仅保存平滑结果。")
        else:
            print("插帧数量为0，仅保存平滑结果。")

    # 6. 保存结果
    print(f"\n保存到 {output_folder} ...")
    save_sequence_ordered(new_bgr, new_alpha, output_folder, start_index=1)

    print("\n" + "=" * 60)
    print("处理完成！")
    print("=" * 60)
    return True


# ==================== 直接运行示例 ====================

if __name__ == "__main__":
    try:
        from PIL import Image
    except ImportError:
        print("建议安装 Pillow 库: pip install Pillow")

    # 调用示例
    smooth_front_with_tail(
        tail_image="./idle_frames/frame_000277.png",
        input_folder="./floating_frames",
        output_folder="./brightness_smoothed_front_interp",
        blend_frames=7,
        extension="png",
        interp_frames=None  # None 表示自动为 blend_frames - 2
    )