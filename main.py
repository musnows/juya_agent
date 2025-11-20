#!/usr/bin/env python3
"""
Juya AI早报生成器
直接实现业务逻辑，无需Agent，支持三种运行模式：
1. 单次运行：拉取最新早报视频并生成报告
2. 指定BV号：处理指定的BV号视频
3. 定时运行：每10分钟检测当日AI早报
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from modules.bilibili_api import BilibiliAPI, parse_cookie_string
from modules.subtitle_processor_ai import AISubtitleProcessor
from modules.email_sender import EmailSender

# 加载环境变量
load_dotenv()

# 全局配置
PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_VIDEOS_PATH = PROJECT_ROOT / "data" / "processed_videos.json"
DOCS_DIR = PROJECT_ROOT / "docs"
COOKIE_FILE = PROJECT_ROOT / "config" / "cookies.json"

# 橘鸦UP主UID
JUYA_UID = 285286947

# 创建必要的目录
DOCS_DIR.mkdir(exist_ok=True)
(PROJECT_ROOT / "data").mkdir(exist_ok=True)


class JuyaProcessor:
    """橘鸦AI早报处理器"""
    
    def __init__(self):
        """初始化处理器"""
        # 初始化各个模块
        self.api = self._get_bili_api()
        self.processor = AISubtitleProcessor()
        self.email_sender = EmailSender()
    
    def _get_bili_api(self) -> BilibiliAPI:
        """获取B站API客户端"""
        if not COOKIE_FILE.exists():
            raise FileNotFoundError(f"请配置 {COOKIE_FILE} 文件")
        
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        return BilibiliAPI(cookies)
    
    def _load_processed_videos(self) -> Dict:
        """加载已处理的视频记录"""
        if PROCESSED_VIDEOS_PATH.exists():
            with open(PROCESSED_VIDEOS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_processed_videos(self, processed: Dict):
        """保存已处理的视频记录"""
        with open(PROCESSED_VIDEOS_PATH, 'w', encoding='utf-8') as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)
    
    def _is_ai_early_report(self, video_info: Dict) -> bool:
        """判断是否为AI早报视频"""
        title = video_info.get('title', '').lower()
        desc = video_info.get('desc', '').lower()
        
        # 检查标题和描述中是否包含AI早报相关关键词
        ai_keywords = ['ai', '人工智能', '早报', '资讯', '科技', '技术']
        
        # 标题检查
        title_has_ai = any(keyword in title for keyword in ai_keywords)
        
        # 描述检查
        desc_has_ai = any(keyword in desc for keyword in ai_keywords)
        
        # 检查是否为当日视频（适配不同字段名）
        timestamp = video_info.get('pubdate') or video_info.get('created') or 0
        video_date = datetime.fromtimestamp(timestamp)
        today = date.today()
        
        # 调试信息
        if title_has_ai or desc_has_ai:
            print(f"🔍 检查视频: {title[:50]}...")
            print(f"   AI关键词: {title_has_ai or desc_has_ai}")
            print(f"   是否今日: {video_date.date() == today}")
            print(f"   视频日期: {video_date.date()}, 今日: {today}")
        
        return (title_has_ai or desc_has_ai) and video_date.date() == today
    
    def _check_today_report_exists(self) -> bool:
        """检查今日是否已存在AI早报文件"""
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # 搜索docs目录下包含今日日期的md文件
        for md_file in DOCS_DIR.glob(f"*{today_str}*.md"):
            if md_file.is_file():
                print(f"✅ 发现今日早报文件: {md_file.name}")
                return True
        
        return False
    
    def get_latest_ai_report(self) -> Optional[str]:
        """获取最新的AI早报视频BV号"""
        print("🔍 正在搜索最新的AI早报视频...")
        
        # 获取最近20个视频
        videos = self.api.get_user_videos(uid=JUYA_UID, page_size=20)
        
        for video in videos:
            if self._is_ai_early_report(video):
                bvid = video['bvid']
                title = video['title']
                print(f"✅ 找到AI早报视频: {title} ({bvid})")
                return bvid
        
        print("❌ 未找到今日的AI早报视频")
        return None
    
    def process_video(self, bvid: str, force_regenerate: bool = False) -> bool:
        """处理单个视频"""
        print(f"🎬 开始处理视频: {bvid}")
        
        try:
            # 获取视频信息
            video_info = self.api.get_video_info(bvid)
            video_date = datetime.fromtimestamp(video_info['pubdate'])
            date_str = video_date.strftime('%Y-%m-%d')
            filename = f"{bvid}_{date_str}_AI早报.md"
            filepath = DOCS_DIR / filename
            
            # 检查是否已处理
            if not force_regenerate and filepath.exists():
                print(f"📄 文档已存在，跳过重新生成: {filepath}")
                return True
            
            # 获取字幕
            print("📥 获取字幕...")
            subtitle = self.api.get_subtitle(bvid)
            
            if not subtitle:
                print("⚠️ 视频没有字幕，将使用视频简介提取新闻...")
            
            # 处理字幕/简介
            print("🤖 AI整理早报中...")
            processed_data = self.processor.process(
                subtitle if subtitle else [], 
                video_info
            )
            
            # 生成Markdown文档
            print("📝 生成文档...")
            markdown = self.processor.format_markdown(processed_data)
            
            # 保存文档
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            print(f"✅ 文档已生成: {filepath}")
            
            # 更新处理记录
            processed = self._load_processed_videos()
            processed[bvid] = {
                'title': video_info['title'],
                'processed_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'subtitle_path': str(filepath)
            }
            self._save_processed_videos(processed)
            
            return True
            
        except Exception as e:
            print(f"❌ 处理视频失败: {e}")
            return False
    
    def send_email_report(self, bvid: str, to_email: str = None) -> bool:
        """发送邮件报告"""
        try:
            to_email = to_email or os.getenv('EMAIL_TO')
            if not to_email:
                print("❌ 未配置收件人邮箱")
                return False
            
            # 检查处理记录
            processed = self._load_processed_videos()
            if bvid not in processed:
                print(f"❌ 视频 {bvid} 尚未处理")
                return False
            
            md_path = processed[bvid].get('subtitle_path')
            if not md_path or not os.path.exists(md_path):
                print(f"❌ 未找到处理文档: {md_path}")
                return False
            
            # 获取视频信息
            video_info = self.api.get_video_info(bvid)
            
            # 解析Markdown文件生成HTML邮件
            html_content = self._generate_email_html(md_path)
            
            # 发送邮件
            success = self.email_sender.send_video_report(
                to_email=to_email,
                video_title=video_info['title'],
                bvid=bvid,
                html_content=html_content,
                markdown_path=md_path
            )
            
            if success:
                print(f"✅ 邮件已发送到 {to_email}")
            else:
                print("❌ 邮件发送失败")
            
            return success
            
        except Exception as e:
            print(f"❌ 发送邮件失败: {e}")
            return False
    
    def _generate_email_html(self, md_path: str) -> str:
        """从Markdown文件生成HTML邮件（简化版）"""
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 简单的Markdown到HTML转换
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>橘鸦AI早报</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
        <pre style="white-space: pre-wrap; font-family: inherit;">{content}</pre>
    </div>
</body>
</html>
"""
        return html


def single_run(processor: JuyaProcessor, send_email: bool = False):
    """单次运行模式：获取最新AI早报"""
    print("="*60)
    print("🚀 单次运行模式 - 获取最新AI早报")
    print("="*60)
    
    # 获取最新AI早报视频
    bvid = processor.get_latest_ai_report()
    if not bvid:
        print("❌ 未找到AI早报视频")
        return False
    
    # 处理视频
    success = processor.process_video(bvid)
    if not success:
        print("❌ 处理视频失败")
        return False
    
    # 发送邮件（如果需要）
    if send_email:
        processor.send_email_report(bvid)
    
    print("✅ 单次运行完成")
    return True


def bv_run(processor: JuyaProcessor, bvid: str, send_email: bool = False):
    """指定BV号运行模式"""
    print("="*60)
    print(f"🎯 指定BV号运行模式 - {bvid}")
    print("="*60)
    
    # 处理视频
    success = processor.process_video(bvid)
    if not success:
        print("❌ 处理视频失败")
        return False
    
    # 发送邮件（如果需要）
    if send_email:
        processor.send_email_report(bvid)
    
    print("✅ BV号运行完成")
    return True


def loop_run(processor: JuyaProcessor, send_email: bool = False):
    """定时运行模式：每10分钟检测一次"""
    print("="*60)
    print("⏰ 定时运行模式 - 每10分钟检测一次")
    print("="*60)
    
    check_interval = 600  # 10分钟
    
    try:
        while True:
            print(f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 开始检测...")
            
            # 检查今日是否已有报告
            if processor._check_today_report_exists():
                print("📄 今日AI早报已存在，跳过本次检测")
            else:
                # 获取最新AI早报
                bvid = processor.get_latest_ai_report()
                if bvid:
                    # 处理视频
                    success = processor.process_video(bvid)
                    if success and send_email:
                        processor.send_email_report(bvid)
                else:
                    print("📭 暂无新的AI早报")
            
            print(f"💤 等待 {check_interval // 60} 分钟后进行下次检测...")
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n👋 定时运行已停止")
    except Exception as e:
        print(f"❌ 定时运行出错: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Juya AI早报生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行示例:
  %(prog)s                    # 单次运行，获取最新AI早报
  %(prog)s --single           # 同上，显式指定单次运行
  %(prog)s --bv BV1234567890 # 处理指定BV号视频
  %(prog)s --loop             # 定时运行，每10分钟检测一次
  %(prog)s --send-email       # 发送邮件（可与其他参数组合使用）
        """
    )
    
    # 运行模式参数（互斥）
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--single', action='store_true', help='单次运行模式（默认）')
    mode_group.add_argument('--bv', type=str, help='指定BV号运行模式')
    mode_group.add_argument('--loop', action='store_true', help='定时运行模式')
    
    # 邮件选项
    parser.add_argument('--send-email', action='store_true', help='处理完成后发送邮件')
    
    args = parser.parse_args()
    
    # 确定运行模式
    if args.loop:
        mode = 'loop'
    elif args.bv:
        mode = 'bv'
    else:
        mode = 'single'  # 默认模式
    
    # 初始化处理器
    try:
        processor = JuyaProcessor()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 执行对应的运行模式
    try:
        if mode == 'single':
            single_run(processor, args.send_email)
        elif mode == 'bv':
            bv_run(processor, args.bv, args.send_email)
        elif mode == 'loop':
            loop_run(processor, args.send_email)
    except KeyboardInterrupt:
        print("\n👋 程序已停止")
    except Exception as e:
        print(f"❌ 运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
