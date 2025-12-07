"""
AI驱动的字幕处理模块
使用 OpenAI API 智能提炼新闻要点、生成概览和提取来源链接
"""

import os
import re
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

from ..logger import get_logger
from .bilibili_api import BilibiliAPI
from .content_formatter import ContentFormatter

load_dotenv()
LLM_MODEL = os.getenv("OPENAI_MODEL")
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "8192"))

class AISubtitleProcessor:
    """AI驱动的字幕智能处理器"""

    def __init__(self, video_dir: Optional[Path] = None):
        # 使用统一的日志器
        self.logger = get_logger()

        # 使用 OpenAI API
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=90.0
        )

        # 初始化 Bilibili API
        self.bilibili_api = BilibiliAPI({})

        # 设置视频数据保存目录
        self.video_dir = video_dir

        # 初始化内容格式化器
        self.content_formatter = ContentFormatter()

    def process(self, subtitle_data: List[Dict], video_info: Dict, speech_texts: List[str] = None) -> Dict:
        """
        使用AI处理字幕数据，生成结构化的新闻报告

        Args:
            subtitle_data: 字幕列表，每项包含 from, to, content
            video_info: 视频信息，包含 bvid, title, desc 等
            speech_texts: 语音转文字结果（当没有字幕时必须提供）

        Returns:
            处理后的结构化数据
        """
        # 提取视频描述中的链接
        desc_links = self._extract_links_from_desc(video_info.get('desc', ''))
        video_desc = video_info.get('desc', '').strip()
        video_title = video_info.get('title', '')

        # 生成日期目录（用于保存评论数据）
        date_dir = datetime.fromtimestamp(video_info.get('pubdate', 0)).strftime('%Y%m%d')

        # 明确五种处理场景：
        # 场景1: 有字幕 - 直接使用字幕生成早报
        if subtitle_data and len(subtitle_data) > 0:
            self.logger.info("Using subtitles to extract news...")
            # 1. 合并字幕文本
            full_text = self._merge_subtitles(subtitle_data)
            # 2. 使用AI提炼新闻内容
            news_items = self._ai_extract_news(full_text, subtitle_data, desc_links, video_title)

        # 场景2、3、4、5: 没有字幕
        else:
            # 场景2: 有简介且有语音转文字 - 优先结合生成（质量最高）
            if video_desc and len(video_desc) >= 30 and speech_texts:
                self.logger.info("Combining video description with speech-to-text for enhanced news extraction...")
                news_items = self._extract_news_from_description_and_speech(video_desc, speech_texts, desc_links, video_title)

            # 场景3: 有简介但无语音转文字 - 仅使用简介（无需语音转写能力）
            elif video_desc and len(video_desc) >= 30:
                self.logger.info("No subtitles available, using video description to extract news...")
                news_items = self._extract_news_from_description(video_desc, desc_links, video_title)

            # 场景4: 简介太短但有语音转文字 - 尝试获取评论并结合语音转文字
            elif speech_texts:
                self.logger.info("Video description too short or empty, attempting to fetch comments and combine with speech-to-text...")
                news_items = self._extract_news_from_speech_and_comments(speech_texts, desc_links, video_title, video_info, date_dir)

            # 场景5: 无简介且无语音转文字 - 尝试仅使用评论（如果有）
            else:
                self.logger.info("No subtitles, description, or speech-to-text available, attempting to extract news from comments only...")
                news_items = self._extract_news_from_comments_only(desc_links, video_title, video_info, date_dir)

        # 3. 生成概览
        overview_text = self._ai_generate_overview(news_items, video_info, video_title)

        # 4. 构建最终结构
        overview = {
            'summary': overview_text,
            'total_news': len(news_items),
            'video_title': video_info.get('title', ''),
            'bvid': video_info.get('bvid', ''),
            'publish_date': datetime.fromtimestamp(video_info.get('pubdate', 0)).strftime('%Y-%m-%d'),
            'processed_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        return {
            'overview': overview,
            'news_items': news_items,
            'raw_subtitles': subtitle_data if subtitle_data else [],
            'speech_texts': speech_texts if speech_texts else [],
            'video_info': video_info
        }

    def _merge_subtitles(self, subtitles: List[Dict]) -> str:
        """合并字幕为完整文本"""
        return ' '.join([s['content'] for s in subtitles])

    def _extract_json_from_response(self, result_text: str) -> dict:
        """
        从API响应中提取JSON数据

        Args:
            result_text: API返回的文本内容

        Returns:
            解析后的JSON对象

        Raises:
            json.JSONDecodeError: JSON解析失败时抛出
        """
        # 提取JSON（去除可能的markdown代码块标记）
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]

        return json.loads(result_text)

    def _extract_links_from_desc(self, desc: str) -> List[Dict[str, any]]:
        """从视频描述中提取链接（带标题和时间戳）"""
        links_with_context = []

        # 按行分割描述
        lines = desc.split('\n')
        current_title = None
        current_time = None

        for line in lines:
            line = line.strip()

            # 匹配标题行：⬛️ 标题: 时间
            title_match = re.match(r'⬛️\s+(.+?):\s+(\d+:\d+)', line)
            if title_match:
                current_title = title_match.group(1).strip()
                current_time = title_match.group(2).strip()
                continue

            # 匹配链接行：🔗 https://...
            link_match = re.match(r'🔗\s+(https?://[^\s]+)', line)
            if link_match and current_title:
                links_with_context.append({
                    'title': current_title,
                    'time': current_time,
                    'url': link_match.group(1).strip()
                })

        return links_with_context

    def _ai_extract_news(self, full_text: str, subtitles: List[Dict], desc_links: List[Dict], video_title: str = "") -> List[Dict]:
        """使用AI提炼新闻条目"""

        prompt = f"""你是一个专业的AI资讯编辑。请从以下AI早报的字幕文本中，提炼出结构化的新闻条目。

视频标题：{video_title}

字幕文本：
{full_text}

要求：
1. 视频标题通常指向本期最重要的新闻，注意识别标题对应的新闻内容
2. 识别并提取每一条独立的AI新闻
3. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
4. 写一段详细的新闻报道，尽可能详细地包含：
   - 核心事件描述（什么公司/产品发布/更新了什么）
   - 关键功能、特性、技术细节的详细说明
   - 使用场景、应用价值或行业影响
   - 保留字幕中提到的所有具体数据、版本号、时间点、技术术语
5. 提取相关的公司/产品/技术名称（2-3个主要实体）
6. 保持专业客观的语气，提供充分信息量
7. 重点关注视频标题所指向的新闻，适当增加其内容的详细程度

内容写作要求：
- 详细展开每个要点，不要概括性描述
- 将字幕中的技术细节完整保留并展开说明
- 多用"功能包括"、"特点是"、"支持"等词汇来展开内容
- 避免"此外"、"同时"等生硬连接词，改用自然衔接
- 尽可能详细，但保持内容的可读性和专业性

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容（150-300字）",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=MAX_TOKENS
            )

            result_text = response.choices[0].message.content.strip()
            result = self._extract_json_from_response(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            return news_items

        except Exception as e:
            self.logger.error(f"AI提取失败: {e}")
            # 降级为简单提取
            return self._simple_extract_news(subtitles)

    def _match_links_for_news(self, news: Dict, desc_links: List[Dict]) -> List[str]:
        """尝试为新闻匹配相关链接"""
        matched_links = []

        # 策略：基于标题相似度匹配
        news_title = news.get('title', '').lower()
        news_content = news.get('content', '').lower()
        news_entities = [e.lower() for e in news.get('entities', [])]

        for link_item in desc_links:
            desc_title = link_item['title'].lower()
            url = link_item['url']

            # 计算相似度
            score = 0

            # 1. 实体匹配
            for entity in news_entities:
                if entity in desc_title:
                    score += 3

            # 2. 标题关键词匹配
            news_words = set(news_title.split())
            desc_words = set(desc_title.split())
            common_words = news_words & desc_words
            score += len(common_words)

            # 3. 内容关键词匹配
            if any(word in news_content for word in desc_title.split()):
                score += 1

            if score >= 2:  # 阈值
                url = url.replace('http://','https://') # 避免出现http链接
                matched_links.append(url)

        return matched_links[:3]  # 最多3个链接


    def _ai_generate_overview(self, news_items: List[Dict], video_info: Dict, video_title: str = "") -> str:
        """使用AI生成本期概览"""

        # 构建新闻列表
        news_list = '\n'.join([f"{i}. {item['title']}" for i, item in enumerate(news_items, 1)])

        prompt = f"""你是AI资讯编辑，请为这期AI早报写一段简洁的概览（60-120字）。

视频标题：{video_info.get('title', '')}
新闻列表：
{news_list}

要求：
1. 识别视频标题指向的重点新闻，突出其重要性
2. 用2-3句话概括本期核心内容
3. 重点突出视频标题所指向新闻的关键词和核心信息
4. 简洁、信息密度高，不要冗余修饰
5. 避免使用"本期"、"今天"、"此外"、"同时"等词
6. 直接陈述事实，不要评论性语言
7. 确保概览重点突出与视频标题相关的重要内容

只返回概览文本，不要其他内容。"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=MAX_TOKENS
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"AI生成概览失败: {e}")
            return f"本期AI早报共包含 {len(news_items)} 条资讯，涵盖AI领域的最新动态。"

    def _extract_news_from_description_and_speech(self, description: str, speech_texts: List[str], desc_links: List[Dict], video_title: str = "") -> List[Dict]:
        """
        结合视频简介和语音转文字结果提取新闻（场景2：有简介+语音转文字）

        Args:
            description: 视频简介文本
            speech_texts: 语音转文字结果列表
            desc_links: 从简介中提取的链接列表
            video_title: 视频标题

        Returns:
            新闻列表
        """
        if not speech_texts:
            self.logger.warning("Speech recognition result is empty, cannot extract news")
            return []

        # 合并所有声道的文本
        full_speech_text = ' '.join(speech_texts)

        self.logger.info(f"Combining description and speech-to-text for news extraction, desc length: {len(description)}, speech length: {len(full_speech_text)}")

        prompt = f"""你是一个专业的AI资讯编辑。请结合以下视频标题、视频简介和语音转文字内容，提炼出结构化的新闻条目。

视频标题：{video_title}

视频简介：
{description}

语音转文字内容：
{full_speech_text}

重要说明：
1. 视频标题通常指向本期最重要的新闻，需要注意识别对应的新闻内容
2. 视频简介通常提供了新闻的核心要点和结构，但可能不够详细
3. 语音转文字包含了详细的讲解内容，但可能存在专有名词转写错误
4. 请结合三者的优势：用标题识别重点新闻，用简介确定新闻结构和要点，用语音转文字补充详细信息

处理策略：
1. 识别视频标题指向的重点新闻内容
2. 优先从视频简介中识别新闻条目的结构和标题
3. 从语音转文字中提取详细的技术细节、功能描述和具体数据
4. 修正语音转文字中可能错误的技术术语和专有名词
5. 补充简介中可能缺失的重要细节
6. 重点关注视频标题所指向的新闻，适当增加其内容详细程度

要求：
1. 识别并提取每一条独立的AI新闻
2. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
3. 写一段详细的新闻报道，尽可能详细地包含：
   - 核心事件描述（什么公司/产品发布/更新了什么）
   - 关键功能、特性、技术细节的详细说明
   - 使用场景、应用价值或行业影响
   - 保留语音转文字中的所有具体数据、版本号、时间点
4. 提取相关的公司/产品/技术名称（2-3个主要实体）
5. 保持专业客观的语气，提供充分信息量
6. 重点关注视频标题所指向的新闻，适当增加其内容的详细程度

内容写作要求：
- 详细展开每个要点，不要概括性描述
- 将语音转文字中的技术细节完整保留并展开说明
- 修正明显的语音转写错误（实体名称、专有名词等）
- 多用"功能包括"、"特点是"、"支持"等词汇来展开内容
- 避免生硬连接词，改用自然衔接
- 尽可能详细，但保持内容的可读性和专业性

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容（150-300字）",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=MAX_TOKENS
            )

            result_text = response.choices[0].message.content.strip()
            result = self._extract_json_from_response(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            self.logger.info(f"Extracted {len(news_items)} news items from combined description and speech-to-text")
            return news_items

        except Exception as e:
            self.logger.error(f"Failed to extract news from combined description and speech-to-text: {e}")
            # 如果结合处理失败，降级为仅使用语音转文字
            self.logger.info("Falling back to speech-to-text only...")
            return self._extract_news_from_speech_text(speech_texts, desc_links, video_title)

    def _extract_news_from_description(self, description: str, desc_links: List[Dict], video_title: str = "") -> List[Dict]:
        """
        从视频简介中提取新闻（备用方案，当没有字幕时使用）

        Args:
            description: 视频简介文本
            desc_links: 从简介中提取的链接列表
            video_title: 视频标题

        Returns:
            新闻列表
        """
        if not description or len(description.strip()) < 30:
            self.logger.warning("Video description too short to extract news")
            return []

        prompt = f"""你是一个专业的AI资讯编辑。请结合视频标题和视频简介，提炼出结构化的新闻条目。

视频标题：{video_title}

视频简介：
{description}

要求：
1. 视频标题通常指向本期最重要的新闻，注意在简介中识别对应的新闻内容
2. 识别并提取每一条独立的AI新闻（简介中通常会列出多条新闻）
3. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
4. 写一段详细的新闻报道，尽可能详细地包含：
   - 核心事件描述（什么公司/产品发布/更新了什么）
   - 从简介中能推断出的关键功能、特性
   - 可能的应用价值或影响
   - 保留简介中的具体数据、版本号、时间点、技术术语
5. 提取相关的公司/产品/技术名称（2-3个主要实体）
6. 保持专业客观的语气
7. 重点关注视频标题所指向的新闻，适当增加其内容的详细程度

注意：
- 简介通常会用"⬛️"或数字标注每条新闻
- 简介可能比字幕简短，请根据有限信息合理补充内容
- 详细展开每个要点，但不要编造不存在的信息

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=MAX_TOKENS
            )

            result_text = response.choices[0].message.content.strip()
            result = self._extract_json_from_response(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            self.logger.info(f"Extracted {len(news_items)} news items from video description")
            return news_items

        except Exception as e:
            self.logger.error(f"Failed to extract news from description: {e}")
            # 如果AI提取失败，返回空列表
            return []

    def _extract_news_from_speech_text(self, speech_texts: List[str], desc_links: List[Dict], video_title: str = "") -> List[Dict]:
        """
        从语音转文字结果中提取新闻（兜底方案，当视频简介为空时使用）

        Args:
            speech_texts: 语音识别结果文本列表
            desc_links: 从简介中提取的链接列表（通常为空）
            video_title: 视频标题

        Returns:
            新闻列表
        """
        if not speech_texts:
            self.logger.warning("Speech recognition result is empty, cannot extract news")
            return []

        # 合并所有声道的文本
        full_text = ' '.join(speech_texts)

        self.logger.info(f"Starting news extraction from speech-to-text, text length: {len(full_text)} characters")

        prompt = f"""你是一个专业的AI资讯编辑。请结合视频标题和语音转文字内容，提炼出结构化的新闻条目。

视频标题：{video_title}

语音转文字内容：
{full_text}

重要说明：
1. 视频标题通常指向本期最重要的新闻，需要注意识别对应的新闻内容
2. 语音转文字内容因语音转写可能存在失真，需要根据专业知识修正为正确的计算机、大模型行业专有名词

要求：
1. 识别并提取每一条独立的AI新闻
2. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
3. 写一段详细的新闻报道，尽可能详细地包含：
   - 核心事件描述（什么公司/产品发布/更新了什么）
   - 关键功能、特性、技术细节的详细说明
   - 使用场景、应用价值或行业影响
   - 修正语音转写中可能错误的技术术语和专有名词
4. 提取相关的公司/产品/技术名称（2-3个主要实体）
5. 保持专业客观的语气，提供充分信息量
6. 重点关注视频标题所指向的新闻，适当增加其内容的详细程度

内容写作要求：
- 详细展开每个要点，不要概括性描述
- 将语音转文字中的技术细节完整保留并展开说明
- 修正明显的语音转写错误（如"GPT"可能被转写为"GPTT"等）
- 多用"功能包括"、"特点是"、"支持"等词汇来展开内容
- 避免"此外"、"同时"等生硬连接词，改用自然衔接
- 尽可能详细，但保持内容的可读性和专业性

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容（150-300字）",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=MAX_TOKENS
            )

            result_text = response.choices[0].message.content.strip()
            result = self._extract_json_from_response(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接（虽然通常为空）
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            self.logger.info(f"Extracted {len(news_items)} news items from speech-to-text result")
            return news_items

        except Exception as e:
            self.logger.error(f"Failed to extract news from speech-to-text: {e}")
            # 如果AI提取失败，返回空列表
            return []

    def format_markdown(self, processed_data: Dict) -> str:
        """
        将处理后的数据格式化为精美的 Markdown

        Args:
            processed_data: process() 返回的结构化数据

        Returns:
            Markdown 格式的文本
        """
        return self.content_formatter.format_markdown(processed_data)

    def generate_email_html(self, processed_data: Dict) -> str:
        """
        生成精美的HTML邮件内容

        Args:
            processed_data: process() 返回的结构化数据

        Returns:
            HTML 格式的邮件内容
        """
        return self.content_formatter.generate_email_html(processed_data)

    def save_comments_output(self, comments: List[Dict], date_dir: str) -> bool:
        """
        保存评论数据到comments_output.txt文件

        Args:
            comments: 评论数据列表
            date_dir: 日期目录名 (YYYYMMDD)

        Returns:
            bool: 保存是否成功
        """
        if not comments:
            self.logger.warning("No comments to save")
            return False

        if not self.video_dir:
            self.logger.warning("video_dir not configured, cannot save comments")
            return False

        target_dir = self.video_dir / date_dir
        comments_output_file = target_dir / "comments_output.txt"

        try:
            # 确保目录存在
            target_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Saving comments output to: {comments_output_file}")

            # 准备保存的内容
            content = []
            content.append("=" * 60)
            content.append("视频评论数据")
            content.append("=" * 60)
            content.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content.append(f"评论数量: {len(comments)}")
            content.append("")

            for i, comment in enumerate(comments, 1):
                content.append(f"评论 {i}:")
                content.append("-" * 20)
                content.append(f"作者: {comment.get('author', 'Unknown')}")
                content.append(f"内容: {comment.get('content', '')}")
                if 'like' in comment:
                    content.append(f"点赞数: {comment['like']}")
                content.append("")

            # 写入文件
            with open(comments_output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))

            self.logger.info(f"Comments output saved successfully: {comments_output_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save comments output: {e}")
            return False

    def _get_uploader_comments_with_retry(self, video_info: Dict, date_dir: str = None, max_retries: int = 10, retry_interval: int = 120) -> List[Dict]:
        """
        获取UP主相关的评论，带重试机制，专门寻找包含时间戳格式的评论

        Args:
            video_info: 视频信息字典
            date_dir: 日期目录名 (YYYYMMDD)，用于保存评论数据
            max_retries: 最大重试次数，默认10次
            retry_interval: 重试间隔（秒），默认120秒（2分钟）

        Returns:
            包含时间戳的评论内容列表
        """
        bvid = video_info.get('bvid', '')
        if not bvid:
            self.logger.warning("No BV ID found in video info, cannot fetch comments")
            return []

        # 首次尝试获取评论
        self.logger.info(f"Starting to fetch uploader comments for video {bvid}")
        comments = self._get_uploader_comments(video_info, date_dir)

        if comments:
            self.logger.info("Successfully fetched uploader comments on first attempt")
            return comments

        # 如果首次获取失败，开始重试
        self.logger.info(f"No uploader comments found on first attempt, starting retry process (max {max_retries} retries)")

        for retry_count in range(1, max_retries + 1):
            self.logger.info(f"Retry attempt {retry_count}/{max_retries} for video {bvid}")

            # 等待指定间隔
            if retry_count > 1:
                self.logger.info(f"Waiting {retry_interval} seconds before next retry...")
                time.sleep(retry_interval)

            # 尝试获取评论
            comments = self._get_uploader_comments(video_info, date_dir)

            if comments:
                self.logger.info(f"Successfully fetched uploader comments after {retry_count} retries")
                return comments

            self.logger.warning(f"Retry attempt {retry_count} failed to fetch comments")

        # 所有重试都失败了
        self.logger.error(f"Failed to fetch uploader comments after {max_retries} retries (total time: {max_retries * retry_interval / 60:.1f} minutes)")
        return []

    def _get_uploader_comments(self, video_info: Dict, date_dir: str = None) -> List[Dict]:
        """
        获取UP主相关的评论，专门寻找包含时间戳格式的评论（单次尝试，不包含重试逻辑）

        Args:
            video_info: 视频信息字典
            date_dir: 日期目录名 (YYYYMMDD)，用于保存评论数据

        Returns:
            包含时间戳的评论内容列表
        """
        try:
            bvid = video_info.get('bvid', '')
            if not bvid:
                self.logger.warning("No BV ID found in video info, cannot fetch comments")
                return []

            # 获取所有UP主相关的评论
            comments = self.bilibili_api.get_all_uploader_related_comments(bvid)

            if not comments:
                self.logger.info("No uploader-related comments found")
                return []

            # 筛选包含时间戳格式的评论
            timestamp_comments = []
            for comment in comments:
                content = comment.get('content', '')
                if self._contains_timestamp_format(content):
                    timestamp_comments.append(comment)
                    self.logger.info(f"Found timestamp comment from {comment['author']}")

            if timestamp_comments:
                self.logger.info(f"Successfully found {len(timestamp_comments)} comments with timestamp format")

                # 保存评论数据到文件（如果提供了date_dir参数）
                if date_dir and self.video_dir:
                    self.save_comments_output(timestamp_comments, date_dir)

                return timestamp_comments
            else:
                self.logger.info("No comments with timestamp format found, skipping comment processing")
                return []

        except Exception as e:
            self.logger.error(f"Failed to fetch uploader comments: {e}")
            return []

    def _contains_timestamp_format(self, content: str) -> bool:
        """
        检查评论内容是否包含时间戳格式（如 "Intro: 00:00", "Outro: 05:53"）

        Args:
            content: 评论内容

        Returns:
            是否包含时间戳格式
        """
        import re

        # 检查是否包含 "Intro: XX:XX" 格式
        intro_pattern = r'Intro:\s*\d{1,2}:\d{2}'
        if re.search(intro_pattern, content, re.IGNORECASE):
            return True

        # 检查是否包含 "Outro: XX:XX" 格式
        outro_pattern = r'Outro:\s*\d{1,2}:\d{2}'
        if re.search(outro_pattern, content, re.IGNORECASE):
            return True

        # 检查是否包含其他时间戳格式（如 "公司名: XX:XX"）
        timestamp_pattern = r':\s*\d{1,2}:\d{2}'
        lines = content.split('\n')
        timestamp_lines = 0

        for line in lines:
            line = line.strip()
            # 如果一行包含时间戳格式，计数
            if re.search(timestamp_pattern, line):
                timestamp_lines += 1

        # 如果有多行包含时间戳格式，可能是早报内容
        return timestamp_lines >= 3

    def _extract_news_from_speech_and_comments(self, speech_texts: List[str], desc_links: List[Dict], video_title: str = "", video_info: Dict = None, date_dir: str = None) -> List[Dict]:
        """
        结合语音转文字和UP主评论提取新闻（场景4：简介太短但有语音转文字）

        Args:
            speech_texts: 语音转文字结果列表
            desc_links: 从简介中提取的链接列表（通常为空）
            video_title: 视频标题
            video_info: 视频信息字典
            date_dir: 日期目录名 (YYYYMMDD)，用于保存评论数据

        Returns:
            新闻列表
        """
        if not speech_texts:
            self.logger.warning("Speech recognition result is empty, cannot extract news")
            return []

        # 获取UP主评论（带重试机制）
        comments = self._get_uploader_comments_with_retry(video_info, date_dir) if video_info else []

        # 合并所有声道的文本
        full_speech_text = ' '.join(speech_texts)

        # 合并评论内容
        comments_text = ''
        if comments:
            comments_list = []
            for comment in comments:
                if comment.get('content'):
                    comments_list.append(comment.get('content', ''))
            comments_text = ' '.join(comments_list)

        self.logger.info(f"Extracting news from speech and comments, speech length: {len(full_speech_text)}, comments length: {len(comments_text)}")

        prompt = f"""你是一个专业的AI资讯编辑。请结合视频标题、语音转文字内容和UP主评论，提炼出结构化的新闻条目。

视频标题：{video_title}

语音转文字内容：
{full_speech_text}

UP主评论内容：
{comments_text if comments_text else "无UP主评论"}

重要说明：
1. 视频标题通常指向本期最重要的新闻，需要注意识别对应的新闻内容
2. 语音转文字内容因语音转写可能存在失真，需要根据专业知识修正
3. UP主评论通常包含重要的补充信息、修正说明或详细的时间戳内容
4. 特别注意评论中的时间戳信息（如"Intro: 00:00"、"Google 上线...: 00:10"等），这些往往是新闻条目的准确时间点
5. 如果评论中有时间戳格式的内容，这是最有价值的新闻结构信息

处理策略：
1. 优先从UP主评论中识别新闻条目结构（特别是时间戳格式）
2. 用评论内容来修正和补充语音转文字中的信息
3. 识别视频标题指向的重点新闻内容
4. 从语音转文字中提取详细的技术细节、功能描述和具体数据
5. 修正语音转文字中可能错误的技术术语和专有名词

要求：
1. 识别并提取每一条独立的AI新闻
2. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
3. 写一段详细的新闻报道，尽可能详细地包含：
   - 核心事件描述（什么公司/产品发布/更新了什么）
   - 关键功能、特性、技术细节的详细说明
   - 使用场景、应用价值或行业影响
   - 保留语音转文字和评论中的所有具体数据、版本号、时间点
4. 提取相关的公司/产品/技术名称（2-3个主要实体）
5. 保持专业客观的语气，提供充分信息量
6. 重点关注视频标题所指向的新闻，适当增加其内容详细程度

内容写作要求：
- 详细展开每个要点，不要概括性描述
- 将语音转文字和评论中的技术细节完整保留并展开说明
- 修正明显的语音转写错误（实体名称、专有名词等）
- 多用"功能包括"、"特点是"、"支持"等词汇来展开内容
- 避免生硬连接词，改用自然衔接
- 尽可能详细，但保持内容的可读性和专业性

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容（150-300字）",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=MAX_TOKENS
            )

            result_text = response.choices[0].message.content.strip()
            result = self._extract_json_from_response(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            self.logger.info(f"Extracted {len(news_items)} news items from speech and comments")
            return news_items

        except Exception as e:
            self.logger.error(f"Failed to extract news from speech and comments: {e}")
            # 如果结合处理失败，降级为仅使用语音转文字
            self.logger.info("Falling back to speech-to-text only...")
            return self._extract_news_from_speech_text(speech_texts, desc_links, video_title)

    def _extract_news_from_comments_only(self, desc_links: List[Dict], video_title: str = "", video_info: Dict = None, date_dir: str = None) -> List[Dict]:
        """
        仅从UP主评论中提取新闻（场景5：无简介且无语音转文字）

        Args:
            desc_links: 从简介中提取的链接列表（通常为空）
            video_title: 视频标题
            video_info: 视频信息字典
            date_dir: 日期目录名 (YYYYMMDD)，用于保存评论数据

        Returns:
            新闻列表
        """
        # 获取UP主评论（带重试机制）
        comments = self._get_uploader_comments_with_retry(video_info, date_dir) if video_info else []

        if not comments:
            self.logger.warning("No uploader comments available, cannot extract news")
            return []

        # 合并评论内容
        comments_text = ''
        comments_list = []
        for comment in comments:
            if comment.get('content'):
                comments_list.append(comment.get('content', ''))
        comments_text = ' '.join(comments_list)

        self.logger.info(f"Extracting news from comments only, total comments: {len(comments)}, text length: {len(comments_text)}")

        prompt = f"""你是一个专业的AI资讯编辑。请结合视频标题和UP主评论，提炼出结构化的新闻条目。

视频标题：{video_title}

UP主评论内容：
{comments_text}

重要说明：
1. 视频标题通常指向本期最重要的新闻，需要注意识别对应的新闻内容
2. UP主评论是唯一的信息来源，需要充分利用评论中的信息
3. 特别注意评论中的时间戳信息（如"Intro: 00:00"、"Google 上线...: 00:10"等），这些往往是新闻条目的准确结构
4. 评论中的时间戳格式内容是最有价值的新闻结构信息
5. 可能需要根据有限的评论信息进行合理的内容扩展

处理策略：
1. 优先从评论中识别新闻条目结构（特别是时间戳格式）
2. 识别视频标题指向的重点新闻内容
3. 根据评论中的信息推断新闻的详细内容
4. 如果评论信息有限，需要基于专业背景进行合理的内容补充
5. 保持评论中已有的具体数据和事实

要求：
1. 识别并提取每一条独立的AI新闻
2. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
3. 写一段详细的新闻报道，尽可能详细地包含：
   - 基于评论信息推断的核心事件描述
   - 从评论中能提取或合理推断的功能、特性说明
   - 可能的应用价值或行业影响
   - 保留评论中的所有具体数据、版本号、时间点
4. 提取相关的公司/产品/技术名称（2-3个主要实体）
5. 保持专业客观的语气
6. 重点关注视频标题所指向的新闻

注意事项：
- 如果评论信息较为简短，需要基于AI领域知识进行合理的内容扩展
- 不要编造与评论信息明显矛盾的内容
- 详细展开每个要点，提供充分的信息量
- 保持内容的可读性和专业性

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容（150-300字）",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,  # 稍微提高创造性来补充信息
                max_tokens=MAX_TOKENS
            )

            result_text = response.choices[0].message.content.strip()
            result = self._extract_json_from_response(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            self.logger.info(f"Extracted {len(news_items)} news items from comments only")
            return news_items

        except Exception as e:
            self.logger.error(f"Failed to extract news from comments only: {e}")
            # 如果AI提取失败，返回空列表
            return []
