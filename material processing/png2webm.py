import os
import cv2
import numpy as np
from pathlib import Path
import subprocess
import tempfile


def get_png_files(folder_path):
    """获取文件夹下所有PNG文件，并按文件名排序"""
    png_files = []
    for file in Path(folder_path).iterdir():
        if file.suffix.lower() == '.png' and file.is_file():
            png_files.append(str(file.absolute()))
    return sorted(png_files)


def create_webm_with_alpha(png_files, output_path, fps=15):
    """
    将PNG图片序列转换为带Alpha通道的WebM视频
    使用VP9编码器支持透明通道
    """
    if not png_files:
        print("错误：没有找到PNG文件！")
        return False

    # 读取第一张图片获取尺寸
    first_img = cv2.imread(png_files[0], cv2.IMREAD_UNCHANGED)
    if first_img is None:
        print(f"错误：无法读取图片 {png_files[0]}")
        return False

    height, width = first_img.shape[:2]

    # 检查是否包含Alpha通道
    if first_img.shape[2] == 4:
        print(f"检测到Alpha通道，图片尺寸: {width}x{height}")
    else:
        print(f"警告：图片没有Alpha通道，将使用纯白背景")

    # 创建临时文件存放图片列表
    temp_dir = tempfile.mkdtemp()
    list_file = os.path.join(temp_dir, "filelist.txt")

    # 使用绝对路径并转义特殊字符
    with open(list_file, 'w', encoding='utf-8') as f:
        for png_file in png_files:
            safe_path = png_file.replace('\\', '/')
            if ' ' in safe_path:
                safe_path = f"'{safe_path}'"
            f.write(f"file {safe_path}\n")
            f.write(f"duration {1.0 / fps:.6f}\n")
        # 添加最后一张图片的duration（避免最后一帧过短）
        last_file = png_files[-1].replace('\\', '/')
        if ' ' in last_file:
            last_file = f"'{last_file}'"
        f.write(f"file {last_file}\n")
        f.write(f"duration {1.0 / fps:.6f}\n")

    try:
        # 检查FFmpeg是否可用
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)

        # 构建FFmpeg命令
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c:v', 'libvpx-vp9',
            '-pix_fmt', 'yuva420p',
            '-auto-alt-ref', '1',
            '-lag-in-frames', '25',
            '-row-mt', '1',
            '-f', 'webm',
            output_path
        ]

        print(f"正在转换 {len(png_files)} 张图片...")
        print(f"输出: {output_path}")

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode == 0:
            print("✅ 转换成功！")
            return True
        else:
            print(f"❌ 转换失败: {result.stderr}")
            print("尝试备用方法...")
            return create_webm_with_alpha_fallback(png_files, output_path, fps)

    except FileNotFoundError:
        print("❌ 未找到FFmpeg！请安装FFmpeg并添加到系统PATH中")
        print("下载地址: https://ffmpeg.org/download.html")
        return False
    except Exception as e:
        print(f"❌ 转换出错: {e}")
        return False
    finally:
        try:
            if os.path.exists(list_file):
                os.remove(list_file)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass


def create_webm_with_alpha_fallback(png_files, output_path, fps=15):
    """备用方法：使用image2输入"""
    try:
        first_file = png_files[0]
        base_dir = os.path.dirname(first_file)

        import re
        pattern = re.compile(r'.*?(\d+)\.png$')
        numbers = []
        for f in png_files:
            match = pattern.search(f)
            if match:
                numbers.append(int(match.group(1)))

        if not numbers:
            print("无法识别文件名模式")
            return False

        num_digits = len(str(max(numbers)))
        file_pattern = f"frame_%0{num_digits}d.png"

        cmd = [
            'ffmpeg',
            '-y',
            '-framerate', str(fps),
            '-i', os.path.join(base_dir, file_pattern),
            '-c:v', 'libvpx-vp9',
            '-pix_fmt', 'yuva420p',
            '-auto-alt-ref', '1',
            '-lag-in-frames', '25',
            '-row-mt', '1',
            '-f', 'webm',
            output_path
        ]

        print("使用备用方法转换...")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode == 0:
            print("✅ 转换成功！")
            return True
        else:
            print(f"❌ 备用方法也失败: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ 备用方法出错: {e}")
        return False


def png_to_webm(input_folder, output_file, fps=15):
    """
    将PNG序列转换为WebM视频（带透明通道）

    Args:
        input_folder: PNG图片所在文件夹路径
        output_file: 输出视频文件路径
        fps: 视频帧率，默认15

    Returns:
        bool: 转换成功返回True，失败返回False
    """
    # 转换为绝对路径
    input_folder = os.path.abspath(input_folder)
    output_file = os.path.abspath(output_file)

    # 检查输入文件夹是否存在
    if not os.path.exists(input_folder):
        print(f"❌ 错误：输入文件夹不存在: {input_folder}")
        return False

    # 检查输出文件夹是否存在，不存在则创建
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建输出目录: {output_dir}")

    # 获取所有PNG文件
    png_files = get_png_files(input_folder)

    if not png_files:
        print(f"❌ 在 {input_folder} 中没有找到PNG文件")
        return False

    print(f"找到 {len(png_files)} 个PNG文件:")
    for f in png_files[:5]:
        print(f"  - {os.path.basename(f)}")
    if len(png_files) > 5:
        print(f"  ... 还有 {len(png_files) - 5} 个文件")

    # 创建WebM视频
    return create_webm_with_alpha(png_files, output_file, fps)


# ==================== 直接运行示例 ====================
if __name__ == "__main__":
    # 调用示例
    png_to_webm(
        input_folder="sleepy_frames",
        output_file="output/sleepy.webm",
        fps=24
    )