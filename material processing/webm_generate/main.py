#!/usr/bin/env python3
"""
完整的素材处理流水线，支持在文件顶部设置最终输出分辨率和帧率。
通过模块导入方式调用各步骤，避免子进程开销。
"""

import shutil
from pathlib import Path

# 导入各步骤处理函数
import crop_step01
import mask
import chroma_step02
import normalize_step03
import encode_thumbs

SCRIPT_DIR = Path(__file__).resolve().parent

# -------------------- 可调参数（用户只需改这里） --------------------
FINAL_SIZE = 400  # 最终输出的正方形尺寸（像素）
FINAL_FPS = 24  # 最终输出的帧率
# -------------------------------------------------------------------

# 需要清空的目录
DIRS_TO_CLEAR = ["step01", "step02", "step03", "step04", "masks"]


def clear_dirs():
    """清空并重建中间目录，保留 video 源目录"""
    for d in DIRS_TO_CLEAR:
        p = SCRIPT_DIR / d
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(exist_ok=True)
        print(f"✓ 已清理并重建 {p}")


def ask_yes_no(question: str, default: bool = True) -> bool:
    """询问用户是/否问题"""
    if default:
        prompt = " [Y/n]: "
    else:
        prompt = " [y/N]: "

    while True:
        answer = input(question + prompt).strip().lower()
        if not answer:
            return default
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print("请输入 y 或 n")


def main() -> int:
    try:
        clear_dirs()

        # 1. 裁剪视频（从 video/ 读取，输出到 step01/）
        print("\n▶ 运行 crop_step01")
        ret = crop_step01.crop_directory(SCRIPT_DIR / "video", SCRIPT_DIR / "step01")
        if ret != 0:
            raise RuntimeError("crop_step01 失败")
        print("✅ crop_step01 完成")

        # 2. 生成蒙版（从 step01/ 读取，输出到 masks/）
        print("\n▶ 运行 mask")
        ret = mask.generate_masks(SCRIPT_DIR / "step01", SCRIPT_DIR / "masks")
        if ret != 0:
            raise RuntimeError("mask 失败")
        print("✅ mask 完成")

        # 3. 去绿幕（从 step01/ 读取，使用 masks/ 中的蒙版，输出到 step02/）
        print("\n▶ 运行 chroma_step02")
        ret = chroma_step02.remove_green_screen(
            SCRIPT_DIR / "step01",
            SCRIPT_DIR / "step02",
            SCRIPT_DIR / "masks"
        )
        if ret != 0:
            raise RuntimeError("chroma_step02 失败")
        print("✅ chroma_step02 完成")

        # 4. 询问是否运行 step3（统一角色尺寸）
        print("\n▶ 是否进行 step3（如果不包含站立姿态的视频可能会出现裁剪错误，建议跳过）")
        run_step3 = ask_yes_no("是否运行 step3 统一角色尺寸？", default=True)

        if run_step3:
            # 4a. 统一角色尺寸（从 step02/ 读取，输出到 step03/）
            print("\n▶ 运行 normalize_step03")
            ret = normalize_step03.unify_character_size(
                SCRIPT_DIR / "step02",
                SCRIPT_DIR / "step03",
                fps=FINAL_FPS  # 使用最终帧率
            )
            if ret != 0:
                raise RuntimeError("normalize_step03 失败")
            print("✅ normalize_step03 完成")

            # 使用 step03 作为 step4 的输入
            input_dir = SCRIPT_DIR / "step03"
        else:
            print("\n⏭️  跳过 step3，将 step2 的内容直接交给 step4")
            # 使用 step02 作为 step4 的输入
            input_dir = SCRIPT_DIR / "step02"

        # 5. 生成缩略图（从 step03/ 或 step02/ 读取，输出到 step04/）
        print("\n▶ 运行 encode_thumbs")
        ret = encode_thumbs.transcode_thumbnails(
            input_dir,
            SCRIPT_DIR / "step04",
            size=FINAL_SIZE,
            fps=FINAL_FPS
        )
        if ret != 0:
            raise RuntimeError("encode_thumbs 失败")
        print("✅ encode_thumbs 完成")

        print("\n🎉 全流程处理完成！")
        source = "step03" if run_step3 else "step02（跳过step3）"
        print(f"最终产物：{SCRIPT_DIR / 'step04'} 下 {FINAL_SIZE}x{FINAL_SIZE}，{FINAL_FPS} fps")
        print(f"数据来源：{source}")
        return 0

    except Exception as e:
        print(f"\n❌ 流水线中断: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())