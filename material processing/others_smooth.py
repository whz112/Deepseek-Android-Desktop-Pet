#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的 WebM 透明序列处理流水线：
1. 从 WebM 提取 PNG 序列
2. 对前几帧进行亮度平滑（参考尾帧）
3. 在序列尾部插入循环过渡帧（使首尾平滑衔接）
4. 将最终序列转换为 WebM

最终只保留 insert_frame 生成的序列帧文件夹和最终的 WebM 文件，
中间产物自动清理。
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

# 导入同目录下的各模块函数
from webm2png import webm_to_png_sequence
from smooth2 import smooth_front_with_tail
from insert_frame import insert_loop_frames
from png2webm import png_to_webm


def cleanup_dirs(*paths):
    """删除多个目录（如果存在）"""
    for p in paths:
        if p and os.path.exists(p):
            try:
                shutil.rmtree(p)
                print(f"清理临时目录: {p}")
            except Exception as e:
                print(f"清理目录 {p} 失败: {e}")


def main(
    webm_path: str,
    tail_image: str,
    smooth_frames: int = 7,
    interp_frames: int = 4,
    fps: int = 15,
    output_dir: str = None,
    output_webm: str = None
):
    """
    执行完整的处理流水线

    Args:
        webm_path: 输入的 WebM 文件路径
        tail_image: 尾帧图片路径（用作亮度参考）
        smooth_frames: 需要平滑的前几帧数量
        interp_frames: 循环插帧数量（从尾帧到首帧）
        fps: 输出 WebM 的帧率
        output_dir: 最终序列帧输出目录（如果为None则自动生成）
        output_webm: 最终 WebM 输出路径（如果为None则自动生成）
    """
    # 检查输入文件是否存在
    if not os.path.isfile(webm_path):
        print(f"错误：WebM 文件不存在: {webm_path}")
        sys.exit(1)
    if not os.path.isfile(tail_image):
        print(f"错误：尾帧图片不存在: {tail_image}")
        sys.exit(1)

    # 获取输入文件名（不含扩展名）
    input_name = Path(webm_path).stem

    # 如果output_dir为None，自动生成
    if output_dir is None:
        output_dir = f"{input_name}_frames"

    # 如果output_webm为None，自动生成（放在output目录）
    if output_webm is None:
        output_dir_path = Path("output")
        output_dir_path.mkdir(exist_ok=True)
        output_webm = str(output_dir_path / f"{input_name}.webm")

    # 如果output_dir已存在，清空它
    final_dir_path = Path(output_dir)
    if final_dir_path.exists():
        print(f"📁 清空已存在的文件夹: {final_dir_path}")
        shutil.rmtree(final_dir_path)
    # 创建空文件夹（稍后移动时会覆盖）
    final_dir_path.mkdir(parents=True, exist_ok=True)

    # 创建临时目录
    raw_dir = tempfile.mkdtemp(prefix="raw_")
    smoothed_dir = tempfile.mkdtemp(prefix="smoothed_")
    final_dir = output_dir

    try:
        # 1. 提取原始 PNG 序列
        print("\n=== 步骤 1: 提取 WebM 为 PNG 序列 ===")
        webm_to_png_sequence(webm_path, output_dir=raw_dir)
        # 检查是否成功
        raw_files = list(Path(raw_dir).glob("*.png"))
        if not raw_files:
            print("错误：提取 PNG 序列失败")
            sys.exit(1)
        print(f"提取成功，共 {len(raw_files)} 帧")

        # 2. 亮度平滑（前几帧）
        print("\n=== 步骤 2: 前帧亮度平滑 ===")
        success = smooth_front_with_tail(
            tail_image=tail_image,
            input_folder=raw_dir,
            output_folder=smoothed_dir,
            blend_frames=smooth_frames,
            extension="png",
            interp_frames=None  # 内部自动计算
        )
        if not success:
            print("错误：亮度平滑失败")
            sys.exit(1)

        # 3. 循环插帧（尾帧到首帧）
        print("\n=== 步骤 3: 循环插帧 ===")
        success = insert_loop_frames(
            input_folder=smoothed_dir,
            output_folder=final_dir,
            num_interp_frames=interp_frames,
            extension="png"
        )
        if not success:
            print("错误：循环插帧失败")
            sys.exit(1)

        # 4. 转换为 WebM
        print("\n=== 步骤 4: 转换为 WebM ===")
        success = png_to_webm(
            input_folder=final_dir,
            output_file=output_webm,
            fps=fps
        )
        if not success:
            print("错误：转换 WebM 失败")
            sys.exit(1)

        print("\n✅ 全部处理完成！")
        print(f"最终序列帧目录: {os.path.abspath(final_dir)}")
        print(f"最终 WebM 文件: {os.path.abspath(output_webm)}")

    except Exception as e:
        print(f"\n❌ 处理过程中发生异常: {e}")
        sys.exit(1)
    finally:
        # 清理中间临时目录
        cleanup_dirs(raw_dir, smoothed_dir)


if __name__ == "__main__":
    # ========== 在此处修改参数 ==========
    main(
        webm_path="webm_generate/step04/reading.webm",           # 输入的 WebM 文件
        tail_image="./idle_frames/frame_000265.png",  # 尾帧图片（idle的尾帧）
        smooth_frames=7,                     # 与idle动画尾帧平滑插帧数量
        interp_frames=15,                     # 首尾循环插帧数量
        fps=24,                              # 输出帧率
        output_dir=None,                     # 自动生成为 文件名_frames
        output_webm=None                     # 自动生成为 output/文件名.webm
    )
    # ===================================