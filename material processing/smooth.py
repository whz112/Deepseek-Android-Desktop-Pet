import cv2
import numpy as np
import os
import glob
import re
from PIL import Image

# ==================== 工具函数 ====================

def natural_sort_key(s):
    """自然排序：按数字顺序排列文件名"""
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', s)]


def read_image_with_alpha(filepath):
    """读取PNG，返回 (BGR, Alpha)"""
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
            bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            alpha = np.ones((img_array.shape[0], img_array.shape[1]), dtype=np.uint8) * 255
            return bgr, alpha
    except:
        img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None, None
        if img.shape[-1] == 4:
            return img[:, :, :3], img[:, :, 3]
        else:
            return img, np.ones((img.shape[0], img.shape[1]), dtype=np.uint8) * 255


def save_image_with_alpha(filepath, bgr, alpha):
    """保存带Alpha通道的PNG"""
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = alpha
    cv2.imwrite(filepath, rgba)


def read_sequence(folder, extension='png'):
    """读取文件夹中的所有PNG序列，返回 (BGR列表, Alpha列表, 文件名列表)"""
    folder = os.path.normpath(folder)
    pattern = os.path.join(folder, f'*.{extension}')
    files = glob.glob(pattern)
    if not files:
        print(f"错误: 在 {folder} 中没有找到 *.{extension} 文件")
        return [], [], []
    files = sorted(files, key=natural_sort_key)
    bgr_list, alpha_list, name_list = [], [], []
    for f in files:
        bgr, alpha = read_image_with_alpha(f)
        if bgr is not None and alpha is not None:
            bgr_list.append(bgr)
            alpha_list.append(alpha)
            name_list.append(os.path.basename(f))
        else:
            print(f"警告: 跳过无法读取的文件 {f}")
    print(f"成功读取 {len(bgr_list)} 张图像")
    return bgr_list, alpha_list, name_list


# ==================== 亮度平滑（来自 smooth.py） ====================

def blend_brightness_simple(img1, alpha1, img2, alpha2, weight):
    """简单亮度混合：调整img2的亮度以匹配img1，然后按权重混合"""
    if img1.shape != img2.shape:
        return img1, alpha1

    a1 = alpha1.astype(np.float32) / 255.0
    a2 = alpha2.astype(np.float32) / 255.0

    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY).astype(np.float32)

    mean1 = np.sum(gray1 * a1) / (np.sum(a1) + 1e-6)
    mean2 = np.sum(gray2 * a2) / (np.sum(a2) + 1e-6)
    if mean1 < 1 or mean2 < 1:
        return img1, alpha1

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


def blend_bidirectional_brightness(seq_bgr, seq_alpha, blend_frames):
    """双向亮度平滑（首尾各 blend_frames 帧）"""
    total = len(seq_bgr)
    if total < 2 or blend_frames <= 0:
        return seq_bgr, seq_alpha

    blend_frames = min(blend_frames, total // 2)
    print(f"开始双向亮度平滑，每端处理 {blend_frames} 帧")

    new_seq_bgr = [img.copy() for img in seq_bgr]
    new_seq_alpha = [alpha.copy() for alpha in seq_alpha]

    for i in range(blend_frames):
        front_idx = i
        back_idx = total - 1 - i
        if front_idx >= back_idx:
            break

        weight = (i + 1) / (blend_frames + 1)

        # 首帧参考尾帧亮度
        blended_front, alpha_front = blend_brightness_simple(
            seq_bgr[front_idx], seq_alpha[front_idx],
            seq_bgr[back_idx], seq_alpha[back_idx], weight
        )
        new_seq_bgr[front_idx] = blended_front
        new_seq_alpha[front_idx] = alpha_front

        # 尾帧参考首帧亮度
        blended_back, alpha_back = blend_brightness_simple(
            seq_bgr[back_idx], seq_alpha[back_idx],
            seq_bgr[front_idx], seq_alpha[front_idx], weight
        )
        new_seq_bgr[back_idx] = blended_back
        new_seq_alpha[back_idx] = alpha_back

    return new_seq_bgr, new_seq_alpha


# ==================== 光流插帧（来自 insert_frame.py） ====================

def compute_optical_flow(img1, img2):
    """计算稠密光流"""
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
    warped1, warped_a1 = warp_with_flow(img1, alpha1, flow_x, flow_y, -t/2)
    warped2, warped_a2 = warp_with_flow(img2, alpha2, flow_x, flow_y, (1-t)/2)

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


# ==================== 主流程 ====================

def main():
    # ===== 用户配置 =====
    input_folder = "./brightness_smoothed_front_interp"      # 原始序列文件夹
    output_folder = "./smoothed_interpolated"   # 输出文件夹
    blend_frames = 4                            # 首尾各多少帧进行亮度平滑
    extension = "png"                           # 图片格式

    # ===== 处理 =====
    print("=" * 60)
    print("亮度平滑 + 边界插帧工具")
    print("=" * 60)

    if not os.path.exists(input_folder):
        print(f"错误: 输入文件夹 '{input_folder}' 不存在")
        return

    # 1. 读取原始序列
    bgr_list, alpha_list, name_list = read_sequence(input_folder, extension)
    if len(bgr_list) < 2 * blend_frames:
        print(f"错误: 序列帧数 ({len(bgr_list)}) 必须大于 2*blend_frames ({2*blend_frames})")
        return

    print(f"原始帧数: {len(bgr_list)}")

    # 2. 亮度平滑
    print("\n--- 执行亮度平滑 ---")
    smooth_bgr, smooth_alpha = blend_bidirectional_brightness(
        bgr_list, alpha_list, blend_frames
    )

    # 3. 确定插帧位置
    N = len(smooth_bgr)
    k = blend_frames   # 每段插帧数量
    if k < 0:
        print("警告: blend_frames < 2，无法插帧，仅保存平滑结果")
        # 直接保存平滑结果并退出
        # 略...
        return

    # 前段边界：索引 blend_frames-1 与 blend_frames 之间
    front_left = blend_frames - 1
    front_right = blend_frames
    # 后段边界：索引 N - blend_frames - 1 与 N - blend_frames 之间
    back_left = N - blend_frames - 1
    back_right = N - blend_frames

    print(f"\n插帧参数: 每段插入 {k} 帧")
    print(f"前段边界: 帧 {front_left+1} 和 {front_right+1} 之间")
    print(f"后段边界: 帧 {back_left+1} 和 {back_right+1} 之间")

    # 4. 生成插帧
    print("\n--- 生成前段插帧 ---")
    front_interp_bgr, front_interp_alpha = generate_intermediate_frames(
        smooth_bgr[front_left], smooth_alpha[front_left],
        smooth_bgr[front_right], smooth_alpha[front_right],
        k
    )
    print(f"生成了 {len(front_interp_bgr)} 个前段插帧")

    print("\n--- 生成后段插帧 ---")
    back_interp_bgr, back_interp_alpha = generate_intermediate_frames(
        smooth_bgr[back_left], smooth_alpha[back_left],
        smooth_bgr[back_right], smooth_alpha[back_right],
        k
    )
    print(f"生成了 {len(back_interp_bgr)} 个后段插帧")

    # 5. 构建完整新序列（按顺序）
    new_bgr = []
    new_alpha = []

    # 前段：0 ~ front_left (包括)
    new_bgr.extend(smooth_bgr[:front_left+1])
    new_alpha.extend(smooth_alpha[:front_left+1])

    # 前段插帧
    new_bgr.extend(front_interp_bgr)
    new_alpha.extend(front_interp_alpha)

    # 中间部分：front_right ~ back_left (包括)
    new_bgr.extend(smooth_bgr[front_right:back_left+1])
    new_alpha.extend(smooth_alpha[front_right:back_left+1])

    # 后段插帧
    new_bgr.extend(back_interp_bgr)
    new_alpha.extend(back_interp_alpha)

    # 后段：back_right ~ end (包括)
    new_bgr.extend(smooth_bgr[back_right:])
    new_alpha.extend(smooth_alpha[back_right:])

    total_frames = len(new_bgr)
    print(f"\n新序列总帧数: {total_frames} (原 {N} 帧 + 新增 {total_frames - N} 帧)")

    # 6. 保存结果
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print(f"\n保存到 {output_folder} ...")
    for idx, (bgr, alpha) in enumerate(zip(new_bgr, new_alpha)):
        filename = f"frame_{idx+1:06d}.png"
        out_path = os.path.join(output_folder, filename)
        save_image_with_alpha(out_path, bgr, alpha)
        if (idx + 1) % 50 == 0:
            print(f"  已保存 {idx+1}/{total_frames}")

    print(f"\n处理完成！结果保存在: {output_folder}")
    print(f"原始帧数: {N}, 插帧数: {total_frames - N}, 总帧数: {total_frames}")


if __name__ == "__main__":
    main()