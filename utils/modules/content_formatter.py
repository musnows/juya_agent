"""
内容格式化模块
负责将处理后的新闻数据转换为各种输出格式（Markdown、HTML等）
"""

import re
from typing import Dict, List
from datetime import datetime


class ContentFormatter:
    """内容格式化器，支持多种输出格式"""

    def __init__(self):
        pass

    def format_markdown(self, processed_data: Dict) -> str:
        """
        将处理后的数据格式化为精美的 Markdown

        Args:
            processed_data: process() 返回的结构化数据

        Returns:
            Markdown 格式的文本
        """
        overview = processed_data['overview']
        news_items = processed_data['news_items']

        md_lines = []

        # 标题
        md_lines.append(f"# {overview['video_title']}\n")

        # 检查是否完全依赖语音转写生成早报（无字幕+无简介）
        raw_subtitles = processed_data.get('raw_subtitles', [])
        speech_texts = processed_data.get('speech_texts', [])
        video_info = processed_data.get('video_info', {})
        video_desc = video_info.get('desc', '') if video_info else ''

        # 只有在完全依赖语音转写时才添加警告（无字幕+无简介+有语音转写）
        if (not raw_subtitles and not video_desc and speech_texts):
            # 添加兜底逻辑说明
            md_lines.append("> ⚠️ **重要说明**：因B站视频缺少简介，当前早报内容使用语音转写生成，内容因语音转写可能存在失真，请以原视频内容为准。\n\n")

        # 元信息
        md_lines.append(f"**📅 发布日期：** {overview['publish_date']}")
        md_lines.append(f"**🎬 BV号：** [{overview['bvid']}](https://www.bilibili.com/video/{overview['bvid']})")
        md_lines.append(f"**📝 整理时间：** {overview['processed_time']}")
        md_lines.append(f"**📊 资讯数量：** {overview['total_news']} 条\n")
        md_lines.append("---\n")

        # 概览（同时作为目录）
        md_lines.append("## 📋 本期概览\n")
        for item in news_items:
            category_emoji = {
                '产品发布': '🚀',
                '技术更新': '🔧',
                '行业动态': '📈',
                '其他': '📰'
            }.get(item['category'], '📰')
            md_lines.append(f"{item['index']}. {category_emoji} {item['title']}")
        md_lines.append("\n---\n")

        # 详细内容（不需要标题）

        for item in news_items:
            category_emoji = {
                '产品发布': '🚀',
                '技术更新': '🔧',
                '行业动态': '📈',
                '其他': '📰'
            }.get(item['category'], '📰')

            md_lines.append(f"### {item['index']}. {category_emoji} {item['title']} {{#{item['index']}-{self._slugify(item['title'])}}}\n")

            # 标签
            if item['entities']:
                tags = ' '.join([f"`{entity}`" for entity in item['entities']])
                md_lines.append(f"**标签**： {tags}\n")

            # 详细内容
            md_lines.append(f"{item['content']}\n")

            # 来源链接
            if item['sources']:
                md_lines.append("**🔗 相关链接：**")
                for link in item['sources']:
                    https_link = link.replace('http://','https://')
                    md_lines.append(f"- <{https_link}>")
                md_lines.append("")

            md_lines.append("---\n")

        # 页脚
        md_lines.append("---\n")
        md_lines.append("## 🎬 视频链接\n")
        md_lines.append(f"**Bilibili**： <https://www.bilibili.com/video/{overview['bvid']}>\n")
        md_lines.append("---\n")
        md_lines.append(f"*整理自橘鸦AI早报 | BV号：{overview['bvid']} | {overview['processed_time']}*")

        return '\n'.join(md_lines)

    def generate_email_html(self, processed_data: Dict) -> str:
        """
        生成精美的HTML邮件内容

        Args:
            processed_data: process() 返回的结构化数据

        Returns:
            HTML 格式的邮件内容
        """
        overview = processed_data['overview']
        news_items = processed_data['news_items']

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
            font-size: 1.5em;
        }}
        .meta {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
            color: #856404;
        }}
        .warning strong {{
            color: #856404;
        }}
        .overview {{
            background-color: #f8f9fa;
            border-left: 4px solid #4CAF50;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .overview-item {{
            margin: 8px 0;
            padding-left: 10px;
        }}
        .news-item {{
            margin: 20px 0;
            padding: 15px 0;
            border-bottom: 1px solid #e8e8e8;
        }}
        .news-item:last-child {{
            border-bottom: none;
        }}
        .news-item h3 {{
            margin-top: 0;
            margin-bottom: 10px;
            color: #2c3e50;
            font-size: 1.1em;
        }}
        .tags {{
            margin: 10px 0;
        }}
        .tag {{
            display: inline-block;
            background-color: #e3f2fd;
            color: #1976d2;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            margin-right: 5px;
        }}
        .sources {{
            margin-top: 10px;
            font-size: 0.9em;
        }}
        .sources a {{
            color: #1976d2;
            text-decoration: none;
        }}
        .sources a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #999;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📺 {overview['video_title']}</h1>

        <div class="meta">
            📅 发布日期：{overview['publish_date']} |
            🎬 BV号：{overview['bvid']} |
            📊 资讯数量：{overview['total_news']} 条
        </div>
"""

        # 检查是否完全依赖语音转写生成早报（无字幕+无简介）
        raw_subtitles = processed_data.get('raw_subtitles', [])
        speech_texts = processed_data.get('speech_texts', [])
        video_info = processed_data.get('video_info', {})
        video_desc = video_info.get('desc', '') if video_info else ''

        # 只有在完全依赖语音转写时才添加警告（无字幕+无简介+有语音转写）
        if (not raw_subtitles and not video_desc and speech_texts):
            html += """
        <div class="warning">
            <strong>⚠️ 重要说明</strong>：因视频缺少简介，当前早报内容使用语音转写生成，内容因语音转写存在失真，请以原视频为准。
        </div>
"""

        html += f"""
        <div class="overview">
            <strong>📋 本期概览</strong>
            <div style="margin-top: 10px;">
"""

        # 概览中列出所有新闻标题（作为目录）
        for item in news_items:
            category_emoji = {
                '产品发布': '🚀',
                '技术更新': '🔧',
                '行业动态': '📈',
                '其他': '📰'
            }.get(item['category'], '📰')
            html += f"""                <div class="overview-item">{item['index']}. {category_emoji} {item['title']}</div>
"""

        html += """            </div>
        </div>
"""

        # 详细内容部分（不需要 h2 标题）
        for item in news_items:
            category_emoji = {
                '产品发布': '🚀',
                '技术更新': '🔧',
                '行业动态': '📈',
                '其他': '📰'
            }.get(item['category'], '📰')

            html += f"""
        <div class="news-item">
            <h3>{item['index']}. {category_emoji} {item['title']}</h3>
"""

            if item['entities']:
                html += '            <div class="tags">\n'
                for entity in item['entities']:
                    html += f'                <span class="tag">{entity}</span>\n'
                html += '            </div>\n'

            html += f"""
            <p>{item['content']}</p>
"""

            if item['sources']:
                html += '            <div class="sources">\n'
                html += '                <strong>🔗 相关链接：</strong><br>\n'
                for link in item['sources']:
                    html += f'                • <a href="{link}" target="_blank">{link}</a><br>\n'
                html += '            </div>\n'

            html += '        </div>\n'

        html += f"""
        <div style="margin-top: 30px; padding: 20px; background-color: #f0f8ff; border-radius: 8px; text-align: center;">
            <h3 style="margin-top: 0;">🎬 观看视频</h3>
            <p style="margin: 10px 0;">
                <a href="https://www.bilibili.com/video/{overview['bvid']}"
                   style="display: inline-block; background-color: #00a1d6; color: white; padding: 10px 20px;
                          border-radius: 5px; text-decoration: none; font-weight: bold;">
                    在 Bilibili 观看完整视频
                </a>
            </p>
            <p style="font-size: 0.9em; color: #666;">BV号：{overview['bvid']}</p>
        </div>

        <div class="footer">
            整理自橘鸦AI早报 | {overview['processed_time']}
        </div>
    </div>
</body>
</html>
"""

        return html

    def _slugify(self, text: str) -> str:
        """将标题转为URL友好的slug"""
        # 简单实现：只保留字母数字
        return re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '-')[:30]