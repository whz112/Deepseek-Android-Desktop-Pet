import subprocess
import json
import os
from pathlib import Path


def get_webm_duration_ffmpeg(file_path):
    """
    使用 ffmpeg 获取 WebM 文件的时长（毫秒）
    """
    try:
        # 使用 ffprobe 获取视频信息
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        # 从 format 中获取时长（秒）
        duration_sec = float(data['format']['duration'])
        duration_ms = int(duration_sec * 1000)

        return duration_ms

    except subprocess.CalledProcessError as e:
        print(f"错误: 无法读取文件 {file_path}")
        print(f"错误信息: {e.stderr}")
        return None
    except FileNotFoundError:
        print("错误: 未找到 ffprobe，请先安装 ffmpeg")
        print("安装方法: brew install ffmpeg (Mac) 或 apt-get install ffmpeg (Linux)")
        return None
    except Exception as e:
        print(f"发生错误: {e}")
        return None


def get_video_duration(file_path):
    """
    获取视频文件时长，支持多种格式
    """
    # 支持常见的视频格式
    video_extensions = {'.webm', '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}

    ext = Path(file_path).suffix.lower()
    if ext not in video_extensions:
        # 如果扩展名不在列表中，仍然尝试读取
        pass

    return get_webm_duration_ffmpeg(file_path)


def process_output_directory():
    """
    处理 output 目录下的所有视频文件
    """
    output_dir = Path("output")

    # 检查 output 目录是否存在
    if not output_dir.exists():
        print(f"错误: 目录 '{output_dir}' 不存在")
        return

    if not output_dir.is_dir():
        print(f"错误: '{output_dir}' 不是一个目录")
        return

    # 收集所有视频文件
    video_files = []
    video_extensions = {'.webm', '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}

    for file_path in output_dir.iterdir():
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext in video_extensions:
                video_files.append(file_path)

    if not video_files:
        print(f"在 '{output_dir}' 目录中未找到视频文件")
        print(f"支持的格式: {', '.join(video_extensions)}")
        return

    # 显示所有视频的时长
    print(f"找到 {len(video_files)} 个视频文件\n")
    print("-" * 80)
    print(f"{'文件名':<40} {'时长(毫秒)':<15} {'时长(秒)':<15} {'时长(分钟)':<15}")
    print("-" * 80)

    total_duration_ms = 0
    success_count = 0

    for video_file in sorted(video_files):
        duration_ms = get_video_duration(str(video_file))

        if duration_ms is not None:
            duration_sec = duration_ms / 1000
            duration_min = duration_ms / 60000
            print(f"{video_file.name:<40} {duration_ms:<15} {duration_sec:<15.2f} {duration_min:<15.2f}")
            total_duration_ms += duration_ms
            success_count += 1
        else:
            print(f"{video_file.name:<40} {'读取失败':<15} {'读取失败':<15} {'读取失败':<15}")

    print("-" * 80)

    if success_count > 0:
        total_sec = total_duration_ms / 1000
        total_min = total_duration_ms / 60000
        total_hours = total_duration_ms / 3600000
        print(f"\n总计 ({success_count} 个文件):")
        print(f"  总时长: {total_duration_ms} 毫秒")
        print(f"  总时长: {total_sec:.2f} 秒")
        print(f"  总时长: {total_min:.2f} 分钟")
        print(f"  总时长: {total_hours:.2f} 小时")
    else:
        print("\n没有成功读取任何视频文件")


# 使用示例
if __name__ == "__main__":
    process_output_directory()