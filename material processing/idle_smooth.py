#!/usr/bin/env python3
"""
idle_smooth.py - WebM循环处理（无平滑）
流程: webm2png -> insert_frame -> png2webm
"""

import os
import shutil
import tempfile
from pathlib import Path

# 导入同目录下的各模块
from webm2png import webm_to_png_sequence
from insert_frame import insert_loop_frames
from png2webm import png_to_webm


def run_pipeline(input_webm, output_webm=None, loop_frames=4, fps=15, keep_temp=False, keep_frames_dir=None):
    """
    完整流程：WebM -> 插帧 -> WebM（无平滑）

    参数:
        input_webm: 输入WebM文件路径
        output_webm: 输出WebM文件路径
        loop_frames: 循环插帧帧数
        fps: 帧率
        keep_temp: 是否保留临时文件
        keep_frames_dir: 保留最终序列帧的文件夹路径，如果为None则不保留
    """

    input_path = Path(input_webm)
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_webm}")
        return False

    # 如果output_webm为None，自动生成
    if output_webm is None:
        # 创建output目录（如果不存在）
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_webm = str(output_dir / f"{input_path.stem}.webm")

    # 如果keep_frames_dir为None，自动生成
    if keep_frames_dir is None:
        keep_frames_dir = f"{input_path.stem}_frames"

    # 如果keep_frames_dir已存在，清空它
    keep_path = Path(keep_frames_dir)
    if keep_path.exists():
        print(f"📁 清空已存在的文件夹: {keep_path}")
        shutil.rmtree(keep_path)
    # 创建空文件夹（稍后移动时会覆盖）
    keep_path.mkdir(parents=True, exist_ok=True)

    # 创建临时目录（在当前目录下）
    temp_dir = Path("temp") / f"idle_smooth_{input_path.stem}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 临时目录: {temp_dir}")

    # 各步骤目录
    dirs = {
        "extract": temp_dir / "01_extract",
        "interpolated": temp_dir / "02_interpolated",
    }

    try:
        # Step 1: WebM -> PNG
        print("\n[1/3] 提取PNG序列...")
        webm_to_png_sequence(input_webm, dirs["extract"])

        # Step 2: 循环插帧（直接对原始帧操作）
        print(f"\n[2/3] 循环插帧 (loop_frames={loop_frames})...")
        insert_loop_frames(
            str(dirs["extract"]),
            str(dirs["interpolated"]),
            num_interp_frames=loop_frames
        )

        # Step 3: PNG -> WebM
        print("\n[3/3] 转换为WebM...")
        png_to_webm(str(dirs["interpolated"]), output_webm, fps)

        # 如果需要保留最终序列帧，将文件夹移动到目标位置
        if keep_frames_dir:
            # 目标文件夹已在前面清空并创建，直接移动
            # 先删除之前创建的空目录（避免移动冲突）
            if keep_path.exists():
                shutil.rmtree(keep_path)
            # 移动整个文件夹
            shutil.move(str(dirs["interpolated"]), str(keep_path))
            print(f"\n📁 序列帧已保存到: {keep_path}")
            # 更新dirs，避免finally中删除
            dirs["interpolated"] = keep_path

        print(f"\n✅ 完成！输出: {output_webm}")
        return True

    except Exception as e:
        print(f"❌ 处理失败: {e}")
        return False

    finally:
        if keep_temp:
            print(f"📁 临时文件保留在: {temp_dir}")
        else:
            # 删除整个临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            print("🧹 清理临时文件")


def main():
    """硬编码配置"""
    # ============ 在这里修改参数 ============
    input_webm = "webm_generate/step04/searching.webm"  # 输入WebM文件
    output_webm = None  # 自动生成为 output/文件名.webm
    loop_frames = 10  # 首尾循环插帧帧数
    fps = 24  # 帧率
    keep_temp = False  # 是否保留临时文件
    keep_frames_dir = None  # 设为None则自动生成为 文件名_frames
    # ========================================

    run_pipeline(input_webm, output_webm, loop_frames, fps, keep_temp, keep_frames_dir)


if __name__ == "__main__":
    main()