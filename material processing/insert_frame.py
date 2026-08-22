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
    """
    读取PNG图像，返回 (BGR, Alpha)
    """
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
            # 灰度图
            bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            alpha = np.ones((img_array.shape[0], img_array.shape[1]), dtype=np.uint8) * 255
            return bgr, alpha
    except:
        # 降级：OpenCV读取
        img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None, None
        if img.shape[-1] == 4:
            bgr = img[:, :, :3]
            alpha = img[:, :, 3]
            return bgr, alpha
        else:
            bgr = img
            alpha = np.ones((img.shape[0], img.shape[1]), dtype=np.uint8) * 255
            return bgr, alpha


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


# ==================== 光流插帧核心 ====================

def compute_optical_flow(img1, img2):
    """
    计算两幅BGR图像之间的稠密光流（Farneback）
    返回 (flow_x, flow_y)
    """
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
    """
    根据光流场扭曲图像到时间 t (0~1)
    t=0 保持原图，t=1 完全移动到目标位置
    """
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
    在两张图像之间生成插值帧（带透明度）
    t: 0~1，0为img1，1为img2
    如果未提供光流，则自动计算从img1到img2的光流
    """
    if flow_x is None or flow_y is None:
        flow_x, flow_y = compute_optical_flow(img1, img2)

    # 将两张图都扭曲到中间位置
    warped1, warped_a1 = warp_with_flow(img1, alpha1, flow_x, flow_y, -t / 2)  # 向img2方向移动一半
    warped2, warped_a2 = warp_with_flow(img2, alpha2, flow_x, flow_y, (1 - t) / 2)  # 向img1方向移动一半

    # Alpha混合
    a1 = warped_a1.astype(np.float32) / 255.0
    a2 = warped_a2.astype(np.float32) / 255.0
    a1_exp = np.expand_dims(a1, axis=2)
    a2_exp = np.expand_dims(a2, axis=2)

    # 合成
    denom = (1 - t) * a1_exp + t * a2_exp + 1e-6
    blended = ((1 - t) * warped1.astype(np.float32) * a1_exp +
               t * warped2.astype(np.float32) * a2_exp) / denom
    blended = np.clip(blended, 0, 255).astype(np.uint8)

    blended_alpha = ((1 - t) * a1 + t * a2) * 255
    blended_alpha = blended_alpha.astype(np.uint8)

    return blended, blended_alpha


def generate_loop_interpolation(first_bgr, first_alpha, last_bgr, last_alpha, num_frames):
    """
    生成从 last 到 first 的过渡帧（不包含 last 和 first 本身）
    返回: (插帧BGR列表, 插帧Alpha列表)
    """
    if num_frames <= 0:
        return [], []

    # 计算从 last 到 first 的光流
    print("计算光流...")
    flow_x, flow_y = compute_optical_flow(last_bgr, first_bgr)

    interp_bgr = []
    interp_alpha = []

    # t 从 1/(num_frames+1) 到 num_frames/(num_frames+1) 均匀分布
    for i in range(1, num_frames + 1):
        t = i / (num_frames + 1)  # t=0对应last, t=1对应first
        print(f"  生成插帧 {i}/{num_frames}  (t={t:.3f})")
        bgr, alpha = interpolate_between_images(
            last_bgr, last_alpha, first_bgr, first_alpha, t, flow_x, flow_y
        )
        interp_bgr.append(bgr)
        interp_alpha.append(alpha)

    return interp_bgr, interp_alpha


# ==================== 主函数 ====================

def insert_loop_frames(
        input_folder: str,
        output_folder: str,
        num_interp_frames: int = 4,
        extension: str = "png"
) -> bool:
    """
    PNG序列循环插帧（从尾帧到首帧插帧，实现平滑循环）

    Args:
        input_folder: 原始PNG序列文件夹
        output_folder: 输出文件夹（包含原帧+插帧）
        num_interp_frames: 要生成的插帧数量（从尾帧到首帧）
        extension: 文件扩展名，默认png

    Returns:
        bool: 处理成功返回True，失败返回False
    """
    print("=" * 60)
    print("PNG序列循环插帧工具")
    print("=" * 60)

    if not os.path.exists(input_folder):
        print(f"错误: 输入文件夹 '{input_folder}' 不存在")
        return False

    # 读取序列
    bgr_list, alpha_list, name_list = read_sequence(input_folder, extension)
    if len(bgr_list) < 2:
        print("错误: 至少需要2张图像才能插帧")
        return False

    first_bgr, first_alpha = bgr_list[0], alpha_list[0]
    last_bgr, last_alpha = bgr_list[-1], alpha_list[-1]

    print(f"原始序列帧数: {len(bgr_list)}")
    print(f"首帧尺寸: {first_bgr.shape}, 尾帧尺寸: {last_bgr.shape}")
    print(f"将生成 {num_interp_frames} 个插帧（从尾帧到首帧）")

    # 生成插帧
    interp_bgr, interp_alpha = generate_loop_interpolation(
        first_bgr, first_alpha, last_bgr, last_alpha, num_interp_frames
    )

    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 保存所有帧：原帧 + 插帧（按顺序重命名）
    total_frames = len(bgr_list) + len(interp_bgr)
    print(f"\n保存完整序列（共 {total_frames} 帧）到 {output_folder}")

    # 先保存原始帧
    for idx, (bgr, alpha, name) in enumerate(zip(bgr_list, alpha_list, name_list)):
        new_name = f"frame_{idx + 1:06d}.png"
        out_path = os.path.join(output_folder, new_name)
        save_image_with_alpha(out_path, bgr, alpha)
        if (idx + 1) % 50 == 0:
            print(f"  已保存 {idx + 1} 张原始帧")

    # 保存插帧（接在后面）
    for idx, (bgr, alpha) in enumerate(zip(interp_bgr, interp_alpha)):
        frame_num = len(bgr_list) + idx + 1
        new_name = f"frame_{frame_num:06d}.png"
        out_path = os.path.join(output_folder, new_name)
        save_image_with_alpha(out_path, bgr, alpha)
        if (idx + 1) % 20 == 0:
            print(f"  已保存 {idx + 1} 张插帧")

    print(f"\n处理完成！结果保存在: {output_folder}")
    print(f"原始帧数: {len(bgr_list)}, 新增插帧: {len(interp_bgr)}, 总帧数: {total_frames}")
    return True


# ==================== 直接运行示例 ====================

if __name__ == "__main__":
    # 调用示例
    insert_loop_frames(
        input_folder="./brightness_smoothed_front_interp",
        output_folder="./output_sequence",
        num_interp_frames=4,
        extension="png"
    )