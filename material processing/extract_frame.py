import cv2
import os
from pathlib import Path


def extract_frame(video_path, frame_index=0, output_path=None):
    """
    提取视频的指定帧并保存为图片

    Args:
        video_path: 视频文件路径
        frame_index: 帧索引（从0开始），默认为0（第一帧）
        output_path: 输出图片路径（可选），如果不指定则自动生成
    """
    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        print(f"错误: 视频文件 '{video_path}' 不存在")
        return False

    # 打开视频文件
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"错误: 无法打开视频文件 '{video_path}'")
        return False

    # 获取总帧数
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # 检查帧索引是否有效
    if frame_index < 0 or frame_index >= total_frames:
        print(f"错误: 帧索引 {frame_index} 无效，视频总帧数为 {total_frames}")
        cap.release()
        return False

    # 设置要读取的帧位置
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

    # 读取指定帧
    ret, frame = cap.read()

    if not ret:
        print(f"错误: 无法读取第 {frame_index} 帧")
        cap.release()
        return False

    # 如果未指定输出路径，自动生成
    if output_path is None:
        video_name = Path(video_path).stem
        output_path = f"{video_name}_frame_{frame_index}.jpg"

    # 保存图片
    cv2.imwrite(output_path, frame)

    # 释放资源
    cap.release()

    print(f"成功! 第 {frame_index} 帧已保存到: {output_path}")
    return True


# ========== 在这里配置你的视频路径 ==========
VIDEO_PATH = "webm_generate/video-bak/被鼠标拖拽悬空反馈.mp4"  # 修改为你的视频文件路径
FRAME_INDEX = 30  # 修改为你要提取的帧索引（从0开始）
OUTPUT_PATH = None  # 设置为None自动生成文件名，或指定如 "frame.jpg"
# =========================================

if __name__ == "__main__":
    extract_frame(VIDEO_PATH, FRAME_INDEX, OUTPUT_PATH)