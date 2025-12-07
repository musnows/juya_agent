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

from utils.modules.bilibili_api import BilibiliAPI
from utils.modules.subtitle_processor_ai import AISubtitleProcessor
from utils.modules.email_sender import EmailSender
from utils.video_fallback import VideoFallbackProcessor
from utils.web_generator import WebGenerator
from utils.logger import get_logger

# 加载环境变量
load_dotenv()

# 全局配置
PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_VIDEOS_PATH = PROJECT_ROOT / "data" / "processed_videos.json"
DOCS_DIR = PROJECT_ROOT / "docs"
COOKIE_FILE = PROJECT_ROOT / "config" / "cookies.json"
DIST_DIR = PROJECT_ROOT / "dist"

# 橘鸦UP主UID
JUYA_UID = 285286947

# 创建必要的目录
DOCS_DIR.mkdir(exist_ok=True)
(PROJECT_ROOT / "data").mkdir(exist_ok=True)

# 使用统一的日志器
logger = get_logger()


class JuyaProcessor:
    """橘鸦AI早报处理器"""

    def __init__(self):
        """初始化处理器"""
        # 使用统一的日志器
        self.logger = get_logger()

        # 初始化各个模块
        self.api = self._get_bili_api()
        self.email_sender = EmailSender()
        self.fallback_processor = VideoFallbackProcessor(PROJECT_ROOT)

        # 初始化处理器，传入视频数据目录
        self.processor = AISubtitleProcessor(self.fallback_processor.video_dir)
    
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
        title = video_info.get('title', '')
        desc = video_info.get('desc', '')

        # 使用正则表达式检测"AI早报"，处理任意数量的空格和大小写
        # ai\s*早报 匹配 "AI" + 任意数量空格 + "早报"
        ai_early_report_pattern = re.compile(r'AI\s*早报', re.IGNORECASE)

        # 检查标题中的AI早报关键词
        title_has_ai_early_report = bool(ai_early_report_pattern.search(title))

        # 如果标题中没有找到"AI早报"，则检查是否只有"早报"关键词（作为备选）
        if not title_has_ai_early_report:
            # 只匹配"早报"关键词
            early_report_pattern = re.compile(r'早报')
            title_has_early_report = bool(early_report_pattern.search(title))
        else:
            title_has_early_report = True  # 如果找到AI早报，则认为满足早报条件

        # 检查描述中的关键词（作为辅助判断，主要用于没有明确标题的情况）
        desc_has_ai_early_report = bool(ai_early_report_pattern.search(desc))

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

        # 判断逻辑：必须满足日期条件，且满足以下任一条件：
        # 1. 标题包含"AI早报"（优先级最高）
        # 2. 标题包含"早报"（备选条件）
        # 3. 描述包含"AI早报"（辅助条件）
        is_ai_report = (title_has_ai_early_report or title_has_early_report or desc_has_ai_early_report)

        # 调试信息
        if is_ai_report:
            self.logger.info(f"Checking video: {title[:50]}..., AI早报 keywords: title_ai_early={title_has_ai_early_report}, title_early={title_has_early_report}, desc_ai_early={desc_has_ai_early_report}, is {date_str}: {is_target_date}, video date: {video_date.date()}, target: {date.today() if not target_date else target_date}")

        return is_ai_report and is_target_date
    
    def _check_today_report_exists(self) -> bool:
        """检查今日是否已存在AI早报文件"""
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # 搜索docs目录下包含今日日期的md文件
        for md_file in DOCS_DIR.glob(f"*{today_str}*.md"):
            if md_file.is_file():
                self.logger.info(f"Found today's report file: {md_file.name}")
                return True
        
        return False
    
    def get_latest_ai_report(self) -> Optional[str]:
        """获取最新的AI早报视频BV号"""
        self.logger.info("Searching for latest AI report video...")

        # 获取最近20个视频
        videos = self.api.get_user_videos(uid=JUYA_UID, page_size=20)

        for video in videos:
            if self._is_ai_early_report(video):
                bvid = video['bvid']
                title = video['title']
                self.logger.info(f"Found AI report video: {title} ({bvid})")
                return bvid

        self.logger.warning("No AI report video found for today")
        return None

    def get_ai_reports_by_date_range(self, start_date: date, end_date: date) -> List[Dict]:
        """获取指定日期范围内的所有AI早报视频"""
        self.logger.info(f"Searching for AI report videos from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        ai_reports = []

        # 计算需要获取的天数
        days_count = (end_date - start_date).days + 1

        # 由于B站API限制，我们需要获取更多视频来覆盖整个日期范围
        # 通常一天可能有多个视频，所以我们获取更多的视频
        estimated_videos_needed = days_count * 10  # 估算每天最多10个视频
        page_size = min(estimated_videos_needed, 50)  # B站API限制最多50个

        self.logger.info(f"Fetching {page_size} videos...")

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
                self.logger.info(f"Found AI report for {current_date.strftime('%Y-%m-%d')}: {latest_video['title']}")
            else:
                self.logger.warning(f"No AI report found for {current_date.strftime('%Y-%m-%d')}")

            current_date += timedelta(days=1)

        # 按日期排序（最新的在前面）
        ai_reports.sort(key=lambda x: x['date'], reverse=True)

        self.logger.info(f"Found {len(ai_reports)} AI report videos in total")
        return ai_reports
    
    def process_video(self, bvid: str, force_regenerate: bool = False) -> bool:
        """处理单个视频"""
        self.logger.info(f"Starting video processing: {bvid}")

        try:
            # 获取视频信息
            video_info = self.api.get_video_info(bvid)
            video_date = datetime.fromtimestamp(video_info['pubdate'])
            date_str = video_date.strftime('%Y-%m-%d')
            date_str_yyyymmdd = video_date.strftime('%Y%m%d')  # 用于视频下载的日期格式
            filename = f"{date_str}_AI早报_{bvid}.md"
            filepath = DOCS_DIR / filename

            # 检查是否已处理
            if not force_regenerate and filepath.exists():
                self.logger.info(f"Document already exists, skipping regeneration: {filepath}")
                return True

            # 这部分逻辑现在移到后面，因为需要先检查字幕情况

            # 获取字幕
            self.logger.info("Fetching subtitles...")
            subtitle = self.api.get_subtitle(bvid)

            # 检查是否需要触发兜底逻辑
            speech_texts = None
            should_use_fallback = False
            has_subtitle = bool(subtitle)

            # 新的兜底逻辑：无字幕时只要腾讯云SDK可用，都需要生成语音转写
            if self.fallback_processor.should_trigger_fallback(video_info, has_subtitle):
                self.logger.info("No subtitles available, triggering video fallback processing for speech-to-text")
                speech_texts = self.fallback_processor.process_video_fallback(bvid, video_info, date_str_yyyymmdd)
                should_use_fallback = speech_texts is not None

            # 检查是否应该跳过文件生成（视频字幕、简介、语音转写均不可用）
            if self.fallback_processor.should_skip_file_generation(video_info, has_subtitle, bool(should_use_fallback)):
                self.logger.warning("Skipping file generation: insufficient content and no speech SDK available")
                return False

            # 处理字幕/简介/语音转文字
            self.logger.info("Processing AI report generation...")
            processed_data = self.processor.process(
                subtitle if subtitle else [],
                video_info,
                speech_texts if should_use_fallback else None
            )

            # 生成Markdown文档
            self.logger.info("Generating document...")
            markdown = self.processor.format_markdown(processed_data)

            # 保存Markdown文档
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)

            self.logger.info(f"Document generated: {filepath}")

            # 生成JSON文件
            json_filepath = self._generate_json_file(processed_data, video_info, bvid, filepath, should_use_fallback)
            self.logger.info(f"JSON file generated: {json_filepath}")

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
            self.logger.error(f"Failed to process video: {e}")
            return False
    
    def _generate_json_file(self, processed_data: Dict, video_info: Dict, bvid: str, md_filepath: str, video_fallback: bool = False) -> str:
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
                "date": overview.get('publish_date', datetime.fromtimestamp(video_info.get('pubdate', 0)).strftime('%Y-%m-%d')),
                "video_fallback": video_fallback
            }
            
            # 生成JSON文件路径（与MD文件同目录同名）
            md_path = Path(md_filepath)
            json_filepath = md_path.with_suffix('.json')
            
            # 保存JSON文件
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            return str(json_filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to generate JSON file: {e}")
            # 返回默认路径
            md_path = Path(md_filepath)
            return str(md_path.with_suffix('.json'))
    
    def send_email_report(self, bvid: str, to_email: str = None) -> bool:
        """发送邮件报告"""
        try:
            to_email = to_email or os.getenv('EMAIL_TO')
            if not to_email:
                self.logger.error("Recipient email not configured")
                return False

            # 检查处理记录
            processed = self._load_processed_videos()
            if bvid not in processed:
                self.logger.error(f"Video {bvid} not yet processed")
                return False

            md_path = processed[bvid].get('subtitle_path')
            if not md_path or not os.path.exists(md_path):
                self.logger.error(f"Processed document not found: {md_path}")
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
                self.logger.info(f"Email sent to {to_email}")
            else:
                self.logger.error("Failed to send email")

            return success

        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
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
        self.logger.info(f"Starting history processing for {days} days...")

        # 计算日期范围
        end_date = date.today() - timedelta(days=1)  # 不包括今天
        start_date = end_date - timedelta(days=days - 1)

        self.logger.info(f"Processing date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        # 获取日期范围内的所有AI早报视频
        ai_reports = self.get_ai_reports_by_date_range(start_date, end_date)

        if not ai_reports:
            self.logger.warning("No historical AI report videos found")
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

            self.logger.info(f"Processing video for {report_date}: {title} (BV: {bvid})")

            # 检查是否已存在文档
            video_info = self.api.get_video_info(bvid)
            video_date = datetime.fromtimestamp(video_info['pubdate'])
            date_str = video_date.strftime('%Y-%m-%d')
            filename = f"{date_str}_AI早报_{bvid}.md"
            filepath = DOCS_DIR / filename

            if not force_regenerate and filepath.exists():
                self.logger.info(f"Document already exists, skipping: {filename}")
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
                self.logger.info("Processing completed successfully")
            else:
                failed_count += 1
                results.append({
                    'date': report_date,
                    'bvid': bvid,
                    'title': title,
                    'status': 'failed',
                    'reason': '处理失败'
                })
                self.logger.error("Processing failed")

        # 生成处理报告
        self.logger.info(f"History processing summary: found={len(ai_reports)}, processed={processed_count}, skipped={skipped_count}, failed={failed_count}")

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


def single_run(processor: JuyaProcessor, send_email: bool = False, generate_web: bool = False):
    """单次运行模式：获取最新AI早报"""
    logger.info("="*60)
    logger.info("Single run mode - fetching latest AI report")
    logger.info("="*60)

    # 获取最新AI早报视频
    bvid = processor.get_latest_ai_report()
    if not bvid:
        logger.error("No AI report video found")
        return False

    # 处理视频
    success = processor.process_video(bvid)
    if not success:
        logger.error("Failed to process video")
        return False

    # 发送邮件（如果需要）
    if send_email:
        processor.send_email_report(bvid)

    # 生成静态前端（如果需要）
    if generate_web:
        logger.info("Generating static frontend website...")
        web_generator = WebGenerator(DOCS_DIR, DIST_DIR)
        web_result = web_generator.generate_static_site()
        if web_result:
            logger.info("Static frontend website updated")
        else:
            logger.error("Failed to generate static frontend website")

    logger.info("Single run completed")
    return True


def bv_run(processor: JuyaProcessor, bvid: str, send_email: bool = False, generate_web: bool = False, force: bool = False):
    """指定BV号运行模式"""
    logger.info("="*60)
    logger.info(f"Specified BV mode - {bvid}")
    logger.info("="*60)

    # 处理视频
    success = processor.process_video(bvid, force_regenerate=force)
    if not success:
        logger.error("Failed to process video")
        return False

    # 发送邮件（如果需要）
    if send_email:
        processor.send_email_report(bvid)

    # 生成静态前端（如果需要）
    if generate_web:
        logger.info("Generating static frontend website...")
        web_generator = WebGenerator(DOCS_DIR, DIST_DIR)
        web_result = web_generator.generate_static_site()
        if web_result:
            logger.info("Static frontend website updated")
        else:
            logger.error("Failed to generate static frontend website")

    logger.info("BV mode completed")
    return True


def loop_run(processor: JuyaProcessor, send_email: bool = False, generate_web: bool = False):
    """定时运行模式：每15分钟检测一次，0-7点跳过检查"""
    logger.info("="*60)
    logger.info("Scheduled run mode - checking every 15 minutes, skipping 0-7 hours")
    logger.info("="*60)

    if generate_web:
        logger.info("Auto frontend update mode enabled")

    check_interval = 900  # 15分钟

    try:
        while True:
            current_time = datetime.now()
            current_hour = current_time.hour

            # 检查是否在跳过时间（0-7点）
            if 0 <= current_hour < 7:
                logger.info(f"Current time {current_time.strftime('%Y-%m-%d %H:%M:%S')} in skip period (0-7 hours), waiting {check_interval // 60} minutes")
                time.sleep(check_interval)
                continue

            logger.info(f"Starting check at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # 检查今日是否已有报告
            if processor._check_today_report_exists():
                logger.info("Today's AI report already exists, skipping this check")
            else:
                # 获取最新AI早报
                bvid = processor.get_latest_ai_report()
                if bvid:
                    # 处理视频
                    success = processor.process_video(bvid)
                    if success:
                        # 发送邮件（如果需要）
                        if send_email:
                            processor.send_email_report(bvid)

                        # 生成静态前端（如果需要）
                        if generate_web:
                            logger.info("Updating static frontend website...")
                            web_generator = WebGenerator(DOCS_DIR, DIST_DIR)
                            web_result = web_generator.generate_static_site()
                            if web_result:
                                logger.info("Static frontend website updated")
                            else:
                                logger.error("Failed to generate static frontend website")
                else:
                    logger.info("No new AI reports available")

            logger.info(f"Waiting {check_interval // 60} minutes for next check...")
            time.sleep(check_interval)

    except KeyboardInterrupt:
        logger.info("Scheduled run stopped")
    except Exception as e:
        logger.error(f"Scheduled run error: {e}")


def history_run(processor: JuyaProcessor, days: int = 30, force: bool = False, generate_web: bool = False):
    """历史运行模式：处理指定天数的历史AI早报"""
    logger.info("="*60)
    logger.info(f"History run mode - processing {days} days of AI reports")
    logger.info("="*60)

    # 处理历史报告
    result = processor.process_history_reports(days=days, force_regenerate=force)

    # 生成处理报告
    if result['total_found'] > 0:
        logger.info(f"History processing completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Date range: {result['date_range']['start']} to {result['date_range']['end']}")
        logger.info(f"Summary: found={result['total_found']}, processed={result['total_processed']}, skipped={result['total_skipped']}, failed={result['total_failed']}")

        # 保存处理报告
        report_filename = f"history_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = DOCS_DIR / report_filename

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"Detailed report saved: {report_path}")

        # 生成静态前端（如果需要）
        if generate_web:
            logger.info("Generating static frontend website...")
            web_generator = WebGenerator(DOCS_DIR, DIST_DIR)
            web_result = web_generator.generate_static_site()
            if web_result:
                logger.info("Static frontend website updated")
            else:
                logger.error("Failed to generate static frontend website")
    else:
        logger.warning("No historical AI report videos found")

    return result


def web_run(processor: JuyaProcessor):
    """Web运行模式：生成静态前端网站"""
    logger.info("="*60)
    logger.info("Web run mode - generating static frontend website")
    logger.info("="*60)

    try:
        # 创建Web生成器
        web_generator = WebGenerator(DOCS_DIR, DIST_DIR)

        logger.info("📁 准备生成静态前端...")
        logger.info(f"   源目录: {DOCS_DIR}")
        logger.info(f"   输出目录: {DIST_DIR}")

        # 生成静态网站
        result = web_generator.generate_static_site()

        if result:
            logger.info("Static frontend website generated successfully!")
            logger.info(f"Output directory: {DIST_DIR}")
            logger.info(f"Main page: {DIST_DIR}/index.html")
            logger.info("To view the website, open in browser:")
            logger.info(f"file://{DIST_DIR}/index.html")
        else:
            logger.error("Failed to generate static frontend website")
            return False

        return True

    except Exception as e:
        logger.error(f"Failed to generate static frontend: {e}")
        return False


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
  %(prog)s --loop                    # 定时运行，每15分钟检测一次，0-7点跳过检查
  %(prog)s --history                 # 处理历史30天的AI早报
  %(prog)s --history 15              # 处理历史15天的AI早报
  %(prog)s --history 30 --force      # 强制重新生成历史30天的AI早报
  %(prog)s --web                     # 生成静态前端网站到dist目录

组合选项:
  %(prog)s --web                     # 仅生成静态前端网站
  %(prog)s --single --web            # 单次运行并生成静态前端
  %(prog)s --bv BV1234567890 --web   # 处理指定BV号并生成静态前端
  %(prog)s --loop --web              # 定时运行并自动更新静态前端
  %(prog)s --history --web           # 处理历史早报并生成静态前端
  %(prog)s --send-email --web        # 发送邮件并生成静态前端
  %(prog)s --history --force --web   # 强制重新生成历史早报并更新静态前端
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
    parser.add_argument('--web', action='store_true', help='处理完成后生成静态前端网站（可与其他参数组合使用）')

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
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)

    # 执行对应的运行模式
    try:
        # 如果只有--web参数（没有其他任何参数），执行纯web生成
        if args.web and not args.single and not args.bv and not args.loop and args.history is None and not args.send_email and not args.force:
            web_run(processor)
        elif mode == 'single':
            single_run(processor, args.send_email, args.web)
        elif mode == 'bv':
            bv_run(processor, args.bv, args.send_email, args.web, args.force)
        elif mode == 'loop':
            loop_run(processor, args.send_email, args.web)
        elif mode == 'history':
            history_run(processor, days=args.history, force=args.force, generate_web=args.web)
    except KeyboardInterrupt:
        logger.info("Program stopped")
    except Exception as e:
        logger.error(f"Runtime error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
