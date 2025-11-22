#!/usr/bin/env python3
"""
批量重命名脚本
将docs目录下原有格式的md和json文件重命名为新的 日期_AI早报_BV号 格式
原格式: BV号_日期_AI早报.md/json
新格式: 日期_AI早报_BV号.md/json
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Tuple, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_DIR = PROJECT_ROOT / "docs"
DATA_DIR = PROJECT_ROOT / "data"

def parse_old_filename(filename: str) -> Optional[Tuple[str, str]]:
    """
    解析旧格式文件名
    支持格式:
    - BV号_日期_AI早报.md
    - BV号_日期_AI早报.json
    返回: (bvid, date_str) 或 None
    """
    # 移除文件扩展名
    name_without_ext = Path(filename).stem

    # 匹配旧格式: BV号_日期_AI早报
    pattern = r'^(BV\w+)_(\d{4}-\d{2}-\d{2})_AI早报$'
    match = re.match(pattern, name_without_ext)

    if match:
        bvid = match.group(1)
        date_str = match.group(2)
        return bvid, date_str

    return None

def generate_new_filename(bvid: str, date_str: str, extension: str) -> str:
    """生成新格式文件名: 日期_AI早报_BV号.ext"""
    return f"{date_str}_AI早报_{bvid}{extension}"

def load_processed_videos() -> Dict:
    """加载已处理的视频记录"""
    processed_file = DATA_DIR / "processed_videos.json"
    if processed_file.exists():
        with open(processed_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_processed_videos(processed: Dict):
    """保存已处理的视频记录"""
    processed_file = DATA_DIR / "processed_videos.json"
    with open(processed_file, 'w', encoding='utf-8') as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)

def update_processed_video_paths(processed: Dict, old_path: str, new_path: str):
    """更新处理记录中的文件路径"""
    for bvid, info in processed.items():
        if info.get('subtitle_path') == old_path:
            info['subtitle_path'] = new_path
        if info.get('json_path') == old_path:
            info['json_path'] = new_path

def rename_files():
    """批量重命名文件"""
    print("🔄 开始批量重命名文件...")

    if not DOCS_DIR.exists():
        print(f"❌ docs目录不存在: {DOCS_DIR}")
        return False

    # 加载处理记录
    processed = load_processed_videos()

    # 获取所有需要重命名的文件
    all_files = list(DOCS_DIR.glob("*.md")) + list(DOCS_DIR.glob("*.json"))

    renamed_count = 0
    skipped_count = 0
    error_count = 0

    print(f"📁 在 {DOCS_DIR} 目录下找到 {len(all_files)} 个文件")

    for file_path in all_files:
        print(f"\n🔍 检查文件: {file_path.name}")

        # 尝试解析旧格式文件名
        parsed = parse_old_filename(file_path.name)
        if not parsed:
            print(f"   ⏭️  跳过: 不符合旧格式")
            skipped_count += 1
            continue

        bvid, date_str = parsed
        extension = file_path.suffix
        new_filename = generate_new_filename(bvid, date_str, extension)
        new_file_path = file_path.parent / new_filename

        # 检查新文件名是否已存在
        if new_file_path.exists():
            print(f"   ⚠️  跳过: 目标文件已存在 {new_filename}")
            skipped_count += 1
            continue

        try:
            # 重命名文件
            file_path.rename(new_file_path)
            print(f"   ✅ 重命名: {file_path.name} -> {new_filename}")

            # 更新处理记录中的路径
            old_path_str = str(file_path)
            new_path_str = str(new_file_path)
            update_processed_video_paths(processed, old_path_str, new_path_str)

            renamed_count += 1

        except Exception as e:
            print(f"   ❌ 重命名失败: {e}")
            error_count += 1

    # 保存更新后的处理记录
    if renamed_count > 0:
        save_processed_videos(processed)
        print(f"\n💾 已更新处理记录文件")

    # 输出统计信息
    print(f"\n📊 重命名完成统计:")
    print(f"   总文件数: {len(all_files)}")
    print(f"   成功重命名: {renamed_count}")
    print(f"   跳过文件: {skipped_count}")
    print(f"   错误文件: {error_count}")

    return renamed_count > 0

def preview_changes():
    """预览重命名变更（不实际执行）"""
    print("👀 预览重命名变更（不会实际执行）...")

    if not DOCS_DIR.exists():
        print(f"❌ docs目录不存在: {DOCS_DIR}")
        return

    all_files = list(DOCS_DIR.glob("*.md")) + list(DOCS_DIR.glob("*.json"))

    print(f"\n📁 在 {DOCS_DIR} 目录下找到 {len(all_files)} 个文件\n")

    for file_path in all_files:
        parsed = parse_old_filename(file_path.name)
        if parsed:
            bvid, date_str = parsed
            extension = file_path.suffix
            new_filename = generate_new_filename(bvid, date_str, extension)
            print(f"   🔄 {file_path.name}")
            print(f"   -> {new_filename}")
            print()

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="批量重命名docs目录下的AI早报文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --preview           # 预览重命名变更（不实际执行）
  %(prog)s --execute           # 执行批量重命名
  %(prog)s                     # 默认执行批量重命名
        """
    )

    parser.add_argument('--preview', action='store_true', help='预览重命名变更（不实际执行）')
    parser.add_argument('--execute', action='store_true', help='执行批量重命名')

    args = parser.parse_args()

    print("=" * 60)
    print("📝 橘鸦AI早报文件批量重命名工具")
    print("=" * 60)

    if args.preview:
        preview_changes()
    else:
        # 执行重命名
        success = rename_files()
        if success:
            print("\n🎉 批量重命名完成！")
        else:
            print("\n⚠️ 没有文件被重命名")

if __name__ == "__main__":
    main()