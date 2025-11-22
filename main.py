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
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from utils.modules.bilibili_api import BilibiliAPI, parse_cookie_string
from utils.modules.subtitle_processor_ai import AISubtitleProcessor
from utils.modules.email_sender import EmailSender

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
    
    def _is_ai_early_report(self, video_info: Dict, target_date: date = None) -> bool:
        """判断是否为AI早报视频"""
        title = video_info.get('title', '').lower()
        desc = video_info.get('desc', '').lower()

        # 检查标题和描述中是否包含AI早报相关关键词
        ai_keywords = ['ai', '人工智能', '早报', '资讯', '科技', '技术']

        # 标题检查
        title_has_ai = any(keyword in title for keyword in ai_keywords)

        # 描述检查
        desc_has_ai = any(keyword in desc for keyword in ai_keywords)

        # 检查视频日期
        timestamp = video_info.get('pubdate') or video_info.get('created') or 0
        video_date = datetime.fromtimestamp(timestamp)

        # 如果指定了目标日期，检查是否匹配；否则检查是否为当日视频
        if target_date:
            is_target_date = video_date.date() == target_date
            date_str = target_date.strftime('%Y-%m-%d')
        else:
            is_target_date = video_date.date() == date.today()
            date_str = "今日"

        # 调试信息
        if title_has_ai or desc_has_ai:
            print(f"🔍 检查视频: {title[:50]}...")
            print(f"   AI关键词: {title_has_ai or desc_has_ai}")
            print(f"   是否{date_str}: {is_target_date}")
            print(f"   视频日期: {video_date.date()}, {date_str}: {date.today() if not target_date else target_date}")

        return (title_has_ai or desc_has_ai) and is_target_date
    
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

    def get_ai_reports_by_date_range(self, start_date: date, end_date: date) -> List[Dict]:
        """获取指定日期范围内的所有AI早报视频"""
        print(f"🔍 正在搜索 {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')} 的AI早报视频...")

        ai_reports = []

        # 计算需要获取的天数
        days_count = (end_date - start_date).days + 1

        # 由于B站API限制，我们需要获取更多视频来覆盖整个日期范围
        # 通常一天可能有多个视频，所以我们获取更多的视频
        estimated_videos_needed = days_count * 10  # 估算每天最多10个视频
        page_size = min(estimated_videos_needed, 50)  # B站API限制最多50个

        print(f"📥 获取最近 {page_size} 个视频...")

        # 获取更多视频来覆盖历史日期范围
        videos = self.api.get_user_videos(uid=JUYA_UID, page_size=page_size)

        # 按日期检查每个视频
        current_date = start_date
        while current_date <= end_date:
            daily_videos = []

            for video in videos:
                if self._is_ai_early_report(video, current_date):
                    daily_videos.append({
                        'bvid': video['bvid'],
                        'title': video['title'],
                        'date': current_date.strftime('%Y-%m-%d'),
                        'pubdate': video.get('pubdate', 0)
                    })

            if daily_videos:
                # 选择当天最新的视频（通常是发布时间最晚的）
                latest_video = max(daily_videos, key=lambda x: x['pubdate'])
                ai_reports.append(latest_video)
                print(f"✅ {current_date.strftime('%Y-%m-%d')}: 找到AI早报 {latest_video['title']}")
            else:
                print(f"⚠️ {current_date.strftime('%Y-%m-%d')}: 未找到AI早报")

            current_date += timedelta(days=1)

        # 按日期排序（最新的在前面）
        ai_reports.sort(key=lambda x: x['date'], reverse=True)

        print(f"📊 总共找到 {len(ai_reports)} 个AI早报视频")
        return ai_reports
    
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
            
            # 保存Markdown文档
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            print(f"✅ 文档已生成: {filepath}")
            
            # 生成JSON文件
            json_filepath = self._generate_json_file(processed_data, video_info, bvid, filepath)
            print(f"✅ JSON文件已生成: {json_filepath}")
            
            # 更新处理记录
            processed = self._load_processed_videos()
            processed[bvid] = {
                'title': video_info['title'],
                'processed_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'subtitle_path': str(filepath),
                'json_path': str(json_filepath)
            }
            self._save_processed_videos(processed)
            
            return True
            
        except Exception as e:
            print(f"❌ 处理视频失败: {e}")
            return False
    
    def _generate_json_file(self, processed_data: Dict, video_info: Dict, bvid: str, md_filepath: str) -> str:
        """生成JSON文件"""
        try:
            # 提取新闻数据
            news_items = processed_data.get('news_items', [])
            overview = processed_data.get('overview', {})
            
            # 构建data数组
            data_array = []
            for index,item in enumerate(news_items, 1):
                data_array.append({
                    "index": index,
                    "title": item.get('title', ''),
                    "content": item.get('content', ''),
                    "sources": item.get('sources',[])
                })
            
            # 构建完整的JSON结构
            json_data = {
                "data": data_array,
                "created_time": overview.get('processed_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                "title": video_info.get('title', ''),
                "date": overview.get('publish_date', datetime.fromtimestamp(video_info.get('pubdate', 0)).strftime('%Y-%m-%d'))
            }
            
            # 生成JSON文件路径（与MD文件同目录同名）
            md_path = Path(md_filepath)
            json_filepath = md_path.with_suffix('.json')
            
            # 保存JSON文件
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            return str(json_filepath)
            
        except Exception as e:
            print(f"❌ 生成JSON文件失败: {e}")
            # 返回默认路径
            md_path = Path(md_filepath)
            return str(md_path.with_suffix('.json'))
    
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

    def process_history_reports(self, days: int = 30, force_regenerate: bool = False) -> Dict:
        """处理历史AI早报"""
        print(f"📚 开始处理历史 {days} 天的AI早报...")

        # 计算日期范围
        end_date = date.today() - timedelta(days=1)  # 不包括今天
        start_date = end_date - timedelta(days=days - 1)

        print(f"📅 处理日期范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

        # 获取日期范围内的所有AI早报视频
        ai_reports = self.get_ai_reports_by_date_range(start_date, end_date)

        if not ai_reports:
            print("❌ 未找到任何历史AI早报视频")
            return {
                'total_found': 0,
                'total_processed': 0,
                'total_skipped': 0,
                'total_failed': 0,
                'reports': []
            }

        # 处理每个视频
        results = []
        processed_count = 0
        skipped_count = 0
        failed_count = 0

        for report in ai_reports:
            bvid = report['bvid']
            title = report['title']
            report_date = report['date']

            print(f"\n🎬 处理 {report_date} 的视频: {title}")
            print(f"   BV号: {bvid}")

            # 检查是否已存在文档
            video_info = self.api.get_video_info(bvid)
            video_date = datetime.fromtimestamp(video_info['pubdate'])
            date_str = video_date.strftime('%Y-%m-%d')
            filename = f"{bvid}_{date_str}_AI早报.md"
            filepath = DOCS_DIR / filename

            if not force_regenerate and filepath.exists():
                print(f"   ⏭️  文档已存在，跳过: {filename}")
                skipped_count += 1
                results.append({
                    'date': report_date,
                    'bvid': bvid,
                    'title': title,
                    'status': 'skipped',
                    'reason': '已存在'
                })
                continue

            # 处理视频
            success = self.process_video(bvid, force_regenerate=force_regenerate)

            if success:
                processed_count += 1
                results.append({
                    'date': report_date,
                    'bvid': bvid,
                    'title': title,
                    'status': 'success',
                    'reason': '处理成功'
                })
                print(f"   ✅ 处理成功")
            else:
                failed_count += 1
                results.append({
                    'date': report_date,
                    'bvid': bvid,
                    'title': title,
                    'status': 'failed',
                    'reason': '处理失败'
                })
                print(f"   ❌ 处理失败")

        # 生成处理报告
        print(f"\n📊 历史处理完成统计:")
        print(f"   找到视频: {len(ai_reports)} 个")
        print(f"   成功处理: {processed_count} 个")
        print(f"   跳过已存在: {skipped_count} 个")
        print(f"   处理失败: {failed_count} 个")

        return {
            'total_found': len(ai_reports),
            'total_processed': processed_count,
            'total_skipped': skipped_count,
            'total_failed': failed_count,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'reports': results
        }


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


def history_run(processor: JuyaProcessor, days: int = 30, force: bool = False):
    """历史运行模式：处理指定天数的历史AI早报"""
    print("="*60)
    print(f"📚 历史运行模式 - 处理最近 {days} 天的AI早报")
    print("="*60)

    # 处理历史报告
    result = processor.process_history_reports(days=days, force_regenerate=force)

    # 生成处理报告
    if result['total_found'] > 0:
        print(f"\n🎉 历史处理完成！")
        print(f"📋 处理摘要:")
        print(f"   处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   日期范围: {result['date_range']['start']} 到 {result['date_range']['end']}")
        print(f"   找到视频: {result['total_found']} 个")
        print(f"   成功处理: {result['total_processed']} 个")
        print(f"   跳过已存在: {result['total_skipped']} 个")
        print(f"   处理失败: {result['total_failed']} 个")

        # 保存处理报告
        report_filename = f"history_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = DOCS_DIR / report_filename

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"📄 详细报告已保存: {report_path}")
    else:
        print("❌ 未找到任何历史AI早报视频")

    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Juya AI早报生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行示例:
  %(prog)s                           # 单次运行，获取最新AI早报
  %(prog)s --single                  # 同上，显式指定单次运行
  %(prog)s --bv BV1234567890        # 处理指定BV号视频
  %(prog)s --loop                    # 定时运行，每10分钟检测一次
  %(prog)s --history                 # 处理历史30天的AI早报
  %(prog)s --history 15              # 处理历史15天的AI早报
  %(prog)s --history 30 --force      # 强制重新生成历史30天的AI早报
  %(prog)s --send-email              # 发送邮件（可与其他参数组合使用）
        """
    )

    # 运行模式参数（互斥）
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--single', action='store_true', help='单次运行模式（默认）')
    mode_group.add_argument('--bv', type=str, help='指定BV号运行模式')
    mode_group.add_argument('--loop', action='store_true', help='定时运行模式')
    mode_group.add_argument('--history', nargs='?', type=int, const=30, metavar='DAYS', help='处理历史指定天数的AI早报（默认30天）')

    # 其他选项
    parser.add_argument('--force', action='store_true', help='强制重新生成已存在的文档')
    parser.add_argument('--send-email', action='store_true', help='处理完成后发送邮件')

    args = parser.parse_args()

    # 确定运行模式
    if args.loop:
        mode = 'loop'
    elif args.bv:
        mode = 'bv'
    elif args.history is not None:
        mode = 'history'
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
        elif mode == 'history':
            history_run(processor, days=args.history, force=args.force)
    except KeyboardInterrupt:
        print("\n👋 程序已停止")
    except Exception as e:
        print(f"❌ 运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
