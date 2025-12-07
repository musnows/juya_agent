#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静态前端生成器
用于生成完整的静态前端网站，与frontend/保持一致的页面风格
"""

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import markdown

from .logger import get_logger


class WebGenerator:
    """静态前端生成器"""

    def __init__(self, docs_dir: str, output_dir: str, homepage_page_size: int = 15):
        """初始化生成器

        Args:
            docs_dir: 源文档目录路径
            output_dir: 输出目录路径
            homepage_page_size: 首页显示的早报数量，默认15条
        """
        # 使用统一的日志器
        self.logger = get_logger()

        self.docs_dir = Path(docs_dir)
        self.output_dir = Path(output_dir)
        self.page_size = homepage_page_size  # 首页显示数量
        self.detail_page_size = 20  # 列表页每页显示数量

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建必要的子目录
        (self.output_dir / "detail").mkdir(exist_ok=True)
        (self.output_dir / "archive").mkdir(exist_ok=True)
        (self.output_dir / "data").mkdir(exist_ok=True)

    def _parse_filename(self, filename: str) -> Dict:
        """解析文件名获取信息"""
        # 文件名格式: 日期_AI早报_BV号.md (新格式)
        match = re.match(r'(\d{4}-\d{2}-\d{2})_AI早报_([^\.]+)\.md', filename)
        if match:
            return {
                'bv_id': match.group(2),
                'date': match.group(1),
                'filename': filename
            }

        # 兼容旧格式: BV号_日期_AI早报.md
        match_old = re.match(r'([^_]+)_(\d{4}-\d{2}-\d{2})_AI早报\.md', filename)
        if match_old:
            return {
                'bv_id': match_old.group(1),
                'date': match_old.group(2),
                'filename': filename
            }

        return None

    def _parse_markdown_file(self, filepath: str) -> Dict:
        """解析markdown文件内容"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取标题
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else '未知标题'

            # 提取发布日期
            date_match = re.search(r'\*\*📅 发布日期：\*\* (\d{4}-\d{2}-\d{2})', content)
            publish_date = date_match.group(1) if date_match else None

            # 提取BV号
            bv_match = re.search(r'\*\*🎬 BV号：\*\* ([^\n]+)', content)
            bv_id = bv_match.group(1) if bv_match else None

            # 提取整理时间
            time_match = re.search(r'\*\*📝 整理时间：\*\* ([^\n]+)', content)
            organize_time = time_match.group(1) if time_match else None

            # 提取资讯数量
            count_match = re.search(r'\*\*📊 资讯数量：\*\* (\d+)', content)
            news_count = int(count_match.group(1)) if count_match else 0

            # 检查是否为语音转写生成
            is_voice_generated = '语音转写生成' in content

            # 提取概览
            overview_match = re.search(r'## 📋 本期概览\n\n(.+?)\n\n---', content, re.DOTALL)
            overview = overview_match.group(1).strip() if overview_match else ''

            # 转换为HTML并移除第一个h1标题以避免二次渲染
            html_content = markdown.markdown(
                content,
                extensions=[
                    'extra',
                    'codehilite',
                    'tables',
                    'toc',
                    'fenced_code',
                    'nl2br',
                    'attr_list',
                    'def_list',
                    'footnotes',
                    'admonition'
                ],
                extension_configs={
                    'codehilite': {
                        'css_class': 'highlight',
                        'use_pygments': True
                    }
                }
            )

            # 移除第一个h1标签以避免在详情页面二次渲染标题
            html_content = re.sub(r'<h1[^>]*>.*?</h1>', '', html_content, count=1, flags=re.DOTALL)

            # 移除原有的元数据信息（发布日期、BV号、整理时间、资讯数量）和后面的分隔符
            # 匹配从<strong>📅 发布日期：</strong>开始到<strong>📊 资讯数量：</strong> ... 条</p>以及后面的<hr />，同时清理多余的换行
            metadata_pattern = r'<p><strong>📅 发布日期：</strong>.*?<strong>📊 资讯数量：</strong>\s*\d+\s*条</p>\s*<hr\s*/?>'
            html_content = re.sub(metadata_pattern, '', html_content, flags=re.DOTALL)

            # 清理开头的多余空白字符
            html_content = html_content.lstrip()

            return {
                'title': title,
                'publish_date': publish_date,
                'bv_id': bv_id,
                'organize_time': organize_time,
                'news_count': news_count,
                'overview': overview,
                'content': content,
                'html_content': html_content,
                'is_voice_generated': is_voice_generated
            }
        except Exception as e:
            self.logger.error(f"解析文件失败 {filepath}: {e}")
            return None

    def _load_newspapers(self) -> List[Dict]:
        """加载所有早报数据"""
        newspapers = []

        if not self.docs_dir.exists():
            self.logger.warning(f"文档目录不存在: {self.docs_dir}")
            return newspapers

        # 遍历docs目录下的所有markdown文件
        for filename in os.listdir(self.docs_dir):
            if filename.endswith('.md'):
                file_info = self._parse_filename(filename)
                if file_info:
                    filepath = self.docs_dir / filename
                    newspaper_data = self._parse_markdown_file(filepath)

                    if newspaper_data:
                        # 合并文件信息和解析内容
                        newspaper_data.update(file_info)
                        # 只添加有咨询的文件，跳过0个咨询的文件
                        if newspaper_data.get('news_count', 0) > 0:
                            newspapers.append(newspaper_data)

        # 按日期排序（最新的在前面）
        newspapers.sort(key=lambda x: x.get('publish_date', ''), reverse=True)

        return newspapers

    def _generate_html_index(self, newspapers: List[Dict]) -> str:
        """生成首页HTML内容"""
        # 计算分页数据
        total_count = len(newspapers)
        first_page = newspapers[:self.page_size]

        # 生成早报卡片HTML
        cards_html = ""
        for newspaper in first_page:
            escape_html = lambda text: str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')

            # 检查是否为语音转写生成并添加标识
            voice_badge = '<i class="fas fa-microphone voice-badge"></i>' if newspaper.get('is_voice_generated', False) else ''

            cards_html += f"""
        <div class="newspaper-card" onclick="window.location.href='detail/{newspaper['publish_date']}.html'">
            <div class="newspaper-header">
                <h3 class="newspaper-title">{escape_html(newspaper['title'] or '未知标题')}</h3>
                <div class="newspaper-meta">
                    <div class="meta-item">
                        <i class="fas fa-calendar"></i>
                        <span>{newspaper['publish_date'] or '未知日期'}</span>
                    </div>
                    <div class="meta-item">
                        <i class="fas fa-video"></i>
                        <span>{newspaper['bv_id'] or '未知BV号'}</span>
                        {voice_badge}
                    </div>
                </div>
            </div>
            <div class="newspaper-overview">
                {escape_html((newspaper['overview'] or '')[:150])}...
            </div>
            <div class="newspaper-stats">
                <div class="stats-count">
                    <i class="fas fa-list"></i>
                    {newspaper['news_count'] or 0} 条资讯
                </div>
                <div style="color: #999; font-size: 12px;">
                    {newspaper['organize_time'] or ''}
                </div>
            </div>
        </div>"""

        # 生成完整的HTML页面
        html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI早报 - 每日AI资讯精选</title>
    <link rel="icon" type="image/jpeg" href="static/favicon.jpeg">
    <link rel="stylesheet" href="static/css/style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <meta name="description" content="每日AI资讯精选，把握技术前沿动态">
    <meta name="keywords" content="AI,人工智能,科技资讯,技术前沿,早报">
    <style>
    /* 加载更多按钮样式 - 与页面风格一致 */
    .load-more-container {
        text-align: center;
        margin: var(--spacing-xl) 0;
        padding: 0 var(--spacing-lg);
    }

    .btn-load-more {
        background: var(--primary-brown);
        color: var(--paper-white);
        border: none;
        padding: var(--spacing-sm) var(--spacing-lg);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        position: relative;
        overflow: hidden;
        border-radius: 8px;
        min-width: 160px;
        justify-content: center;
    }

    .btn-load-more::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: var(--accent-orange);
        transition: left 0.3s ease;
        z-index: 0;
    }

    .btn-load-more:hover::before {
        left: 0;
    }

    .btn-load-more:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-medium);
    }

    .btn-load-more i,
    .btn-load-more span {
        position: relative;
        z-index: 1;
    }

    .btn-load-more:active {
        transform: translateY(0);
        box-shadow: var(--shadow-subtle);
    }

    /* 注意：CSS变量已在主CSS文件中定义，此处不再重复 */

    /* 语音标识样式 */
    .voice-badge {
        color: inherit;
        font-size: 0.9em;
        margin-left: 6px;
        vertical-align: middle;
        opacity: 0.8;
    }
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <header class="header">
            <div class="header-content">
                <h1 class="logo">
                    <i class="fas fa-newspaper"></i>
                    AI早报
                </h1>
                <p class="subtitle">每日AI资讯精选，把握技术前沿动态</p>
                <div class="source-info">
                    <p class="source-text">
                        <i class="fas fa-info-circle"></i>
                        所有AI早报整理自
                        <a href="https://space.bilibili.com/285286947" target="_blank" class="bilibili-link">
                            <i class="fab fa-bilibili"></i>
                            B站@橘鸦Juya
                        </a>
                    </p>
                </div>
            </div>
        </header>

        <!-- 主要内容区域 -->
        <main class="main">
            <!-- 列表视图 -->
            <div id="list-view" class="list-view">
                <div class="toolbar">
                    <button class="btn-refresh" onclick="window.location.reload()">
                        <i class="fas fa-sync-alt"></i>
                        刷新
                    </button>
                    <div class="stats">
                        <span id="total-count">共 """ + str(total_count) + """ 条早报</span>
                    </div>
                </div>

                <!-- 早报列表 -->
                <div id="newspapers-list" class="newspapers-list">
                    {cards_html}
                </div>

                <!-- 查看更多按钮 -->
                """ + ('<div class="load-more-container"><button class="btn-load-more" onclick="loadMore()"><i class="fas fa-plus-circle"></i> <span>加载更多</span></button></div>' if total_count > self.page_size else '') + """
            </div>

            <!-- 详情视图 -->
            <div id="detail-view" class="detail-view hidden">
                <div class="detail-header">
                    <button class="btn-back" onclick="showListView()">
                        返回列表
                    </button>
                    <div class="detail-actions">
                        <button class="btn-refresh-detail" onclick="window.location.reload()">
                            刷新
                        </button>
                    </div>
                </div>

                <div id="detail-content" class="detail-content">
                    <!-- 动态生成内容 -->
                </div>
            </div>
        </main>

        <!-- 底部 -->
        <footer class="footer">
            <p>&copy; 2025 AI早报 - <a href="https://github.com/musnows/juya_agent" target="_blank">musnows/juya_agent</a> - 整理自橘鸦AI早报</p>
        </footer>
    </div>

    <!-- 错误提示 -->
    <div id="error-toast" class="toast error hidden">
        <i class="fas fa-exclamation-circle"></i>
        <span id="error-message"></span>
    </div>

    <!-- 成功提示 -->
    <div id="success-toast" class="toast success hidden">
        <i class="fas fa-check-circle"></i>
        <span id="success-message"></span>
    </div>

    <script>
        let currentPage = 1;
        let pageSize = """ + str(self.page_size) + """;
        let totalCount = """ + str(total_count) + """;
        let isLoading = false;

        // 工具函数
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatDate(dateStr) {
            if (!dateStr) return '';
            try {
                const date = new Date(dateStr);
                return date.toLocaleString('zh-CN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } catch (e) {
                return dateStr;
            }
        }

        async function loadMore() {
            if (isLoading) return;

            isLoading = true;
            const loadMoreBtn = document.querySelector('.btn-load-more');
            if (loadMoreBtn) {
                loadMoreBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>加载中...</span>';
                loadMoreBtn.disabled = true;
            }

            try {
                currentPage++;
                const response = await fetch(`data/list_page_${currentPage}.json`);
                if (!response.ok) {
                    throw new Error('加载失败');
                }

                const data = await response.json();
                const newspapersList = document.getElementById('newspapers-list');

                const newCardsHtml = data.newspapers.map(newspaper => {
                    // 检查是否为语音转写生成并添加标识
                    const voiceBadge = newspaper.is_voice_generated ? '<i class="fas fa-microphone voice-badge"></i>' : '';

                    return `
                    <div class="newspaper-card" onclick="window.location.href='detail/${newspaper.publish_date}.html'">
                        <div class="newspaper-header">
                            <h3 class="newspaper-title">${escapeHtml(newspaper.title || '未知标题')}</h3>
                            <div class="newspaper-meta">
                                <div class="meta-item">
                                    <i class="fas fa-calendar"></i>
                                    <span>${newspaper.publish_date || '未知日期'}</span>
                                </div>
                                <div class="meta-item">
                                    <i class="fas fa-video"></i>
                                    <span>${newspaper.bv_id || '未知BV号'}</span>
                                    ${voiceBadge}
                                </div>
                            </div>
                        </div>
                        <div class="newspaper-overview">
                            ${escapeHtml((newspaper.overview || '').substring(0, 150))}...
                        </div>
                        <div class="newspaper-stats">
                            <div class="stats-count">
                                <i class="fas fa-list"></i>
                                ${newspaper.news_count || 0} 条资讯
                            </div>
                            <div style="color: #999; font-size: 12px;">
                                ${formatDate(newspaper.organize_time)}
                            </div>
                        </div>
                    </div>
                `;
                }).join('');

                newspapersList.insertAdjacentHTML('beforeend', newCardsHtml);

                // 如果已经加载完所有数据，隐藏加载更多按钮
                const startIndex = (currentPage - 1) * pageSize;
                if (startIndex + pageSize >= totalCount) {
                    const loadMoreContainer = document.querySelector('.load-more-container');
                    if (loadMoreContainer) {
                        loadMoreContainer.style.display = 'none';
                    }
                }
            } catch (error) {
                console.error('加载更多失败:', error);
                showToast('加载更多失败，请刷新页面重试', 'error');
            } finally {
                isLoading = false;
                if (loadMoreBtn) {
                    loadMoreBtn.innerHTML = '<i class="fas fa-plus-circle"></i> <span>加载更多</span>';
                    loadMoreBtn.disabled = false;
                }
            }
        }

        function showToast(message, type = 'error') {
            const toastId = type === 'error' ? 'error-toast' : 'success-toast';
            const messageId = type === 'error' ? 'error-message' : 'success-message';

            document.getElementById(messageId).textContent = message;
            document.getElementById(toastId).classList.remove('hidden');

            setTimeout(() => {
                document.getElementById(toastId).classList.add('hidden');
            }, 3000);
        }

        // 页面加载完成后初始化
        document.addEventListener('DOMContentLoaded', function() {
            // 显示加载更多按钮状态
            if (totalCount <= pageSize) {
                const loadMoreBtn = document.querySelector('.btn-load-more');
                if (loadMoreBtn) {
                    loadMoreBtn.style.display = 'none';
                }
            }
        });
    </script>
</body>
</html>"""

        return html_content.replace('{cards_html}', cards_html)

    def _generate_detail_page(self, newspaper: Dict) -> str:
        """生成早报详情页面"""
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{newspaper['title'] if newspaper else '未知标题'} - AI早报</title>
    <link rel="icon" type="image/jpeg" href="../static/favicon.jpeg">
    <link rel="stylesheet" href="../static/css/style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <meta name="description" content="{(newspaper['overview'] or '')[:200]}...">
    <meta name="keywords" content="AI,人工智能,科技资讯,技术前沿,早报,{newspaper['publish_date'] or ''}">
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <header class="header">
            <div class="header-content">
                <h1 class="logo">
                    <i class="fas fa-newspaper"></i>
                    AI早报
                </h1>
                <p class="subtitle">每日AI资讯精选，把握技术前沿动态</p>
            </div>
        </header>

        <!-- 主要内容区域 -->
        <main class="main">
            <!-- 详情视图 -->
            <div class="detail-view">
                <div class="detail-header">
                    <button class="btn-back" onclick="window.location.href='../index.html'">
                        返回首页
                    </button>
                    <div class="detail-actions">
                        <button class="btn-share" onclick="copyUrl()">
                            <i class="fas fa-share-alt"></i>
                            分享链接
                        </button>
                    </div>
                </div>

                <div class="detail-content">
                    <div class="newspaper-detail">
                        <div class="detail-title">
                            <h1>{newspaper.get('title', '未知标题')}</h1>
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <i class="fas fa-calendar"></i>
                                    <span>{newspaper.get('publish_date', '未知日期')}</span>
                                </div>
                                <div class="meta-item">
                                    <i class="fas fa-video"></i>
                                    <span>
                                        {f'<a href="https://www.bilibili.com/video/{newspaper.get("bv_id", "")}" target="_blank" class="bv-link">{newspaper.get("bv_id", "未知BV号")}</a>' if newspaper.get('bv_id') else '未知BV号'}
                                    </span>
                                </div>
                                <div class="meta-item">
                                    <i class="fas fa-clock"></i>
                                    <span>{self._format_date(newspaper.get('organize_time', ''))}</span>
                                </div>
                                <div class="meta-item">
                                    <i class="fas fa-list"></i>
                                    <span>{newspaper.get('news_count', 0)} 条资讯</span>
                                </div>
                            </div>
                        </div>
                        <div class="detail-body">
                            {newspaper.get('html_content', '')}
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <!-- 底部 -->
        <footer class="footer">
            <p>&copy; 2025 AI早报 - <a href="https://github.com/musnows/juya_agent" target="_blank">musnows/juya_agent</a> - 整理自橘鸦AI早报</p>
        </footer>
    </div>

    <!-- 成功提示 -->
    <div id="success-toast" class="toast success hidden">
        <i class="fas fa-check-circle"></i>
        <span id="success-message"></span>
    </div>

    <script>
        function showToast(message, type = 'success') {{
            const toast = document.getElementById('success-toast');
            const messageElement = document.getElementById('success-message');

            messageElement.textContent = message;
            toast.classList.remove('hidden');

            setTimeout(() => {{
                toast.classList.add('hidden');
            }}, 3000);
        }}

        function copyUrl() {{
            navigator.clipboard.writeText(window.location.href).then(() => {{
                showToast('链接已复制到剪贴板', 'success');
            }}).catch(() => {{
                showToast('复制失败，请手动复制链接', 'error');
            }});
        }}

        // 键盘快捷键支持
        document.addEventListener('keydown', function(e) {{
            // ESC键返回首页
            if (e.key === 'Escape') {{
                window.location.href = '../index.html';
            }}
        }});
    </script>
</body>
</html>"""
        return html_content

    
    def _format_date(self, date_str: str) -> str:
        """格式化日期显示"""
        if not date_str:
            return ''
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            return date_obj.strftime('%Y年%m月%d日 %H:%M')
        except:
            return date_str

    def _copy_static_files(self):
        """复制静态文件"""
        # 源静态文件目录
        frontend_static_dir = Path(__file__).parent.parent / "frontend" / "static"
        target_static_dir = self.output_dir / "static"

        # 如果目标目录存在，先删除
        if target_static_dir.exists():
            shutil.rmtree(target_static_dir)

        # 复制静态文件
        shutil.copytree(frontend_static_dir, target_static_dir)
        self.logger.info(f"Static files copied to: {target_static_dir}")

    def _generate_json_data(self, newspapers: List[Dict]):
        """生成分页JSON数据文件"""
        data_dir = self.output_dir / "data"

        # 生成分页数据
        total_pages = (len(newspapers) + self.detail_page_size - 1) // self.detail_page_size

        for page_num in range(1, total_pages + 1):
            start_index = (page_num - 1) * self.detail_page_size
            end_index = min(start_index + self.detail_page_size, len(newspapers))
            page_newspapers = newspapers[start_index:end_index]

            # 为每篇早报生成简化的摘要信息
            page_data = {
                'newspapers': [],
                'page': page_num,
                'total_pages': total_pages,
                'total_count': len(newspapers),
                'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            for newspaper in page_newspapers:
                simplified_data = {
                    'title': newspaper.get('title', ''),
                    'publish_date': newspaper.get('publish_date', ''),
                    'bv_id': newspaper.get('bv_id', ''),
                    'organize_time': newspaper.get('organize_time', ''),
                    'news_count': newspaper.get('news_count', 0),
                    'overview': newspaper.get('overview', ''),
                    'is_voice_generated': newspaper.get('is_voice_generated', False)
                }
                page_data['newspapers'].append(simplified_data)

            json_filepath = data_dir / f'list_page_{page_num}.json'
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Generated {total_pages} page data files in: {data_dir}")

        # 生成详情页的单独数据文件（可选，用于SEO和搜索）
        for newspaper in newspapers:
            detail_data = {
                'title': newspaper.get('title', ''),
                'publish_date': newspaper.get('publish_date', ''),
                'bv_id': newspaper.get('bv_id', ''),
                'organize_time': newspaper.get('organize_time', ''),
                'news_count': newspaper.get('news_count', 0),
                'overview': newspaper.get('overview', ''),
                'html_content': newspaper.get('html_content', ''),
                'content': newspaper.get('content', '')
            }

            json_filepath = data_dir / f'detail_{newspaper.get("publish_date", "")}.json'
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(detail_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Generated {len(newspapers)} detail data files")

    def _generate_detail_pages(self, newspapers: List[Dict]):
        """生成所有早报的独立详情页面"""
        detail_dir = self.output_dir / "detail"

        for newspaper in newspapers:
            # 生成详情页面
            detail_html = self._generate_detail_page(newspaper)
            filename = f"{newspaper.get('publish_date', 'unknown')}.html"

            filepath = detail_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(detail_html)

        self.logger.info(f"Generated {len(newspapers)} detail pages in: {detail_dir}")

    def _generate_archive_pages(self, newspapers: List[Dict]):
        """生成归档页面"""
        archive_dir = self.output_dir / "archive"

        # 按年月分组
        by_year_month = {}
        for newspaper in newspapers:
            date = newspaper.get('publish_date', '')
            if len(date) >= 7:  # YYYY-MM格式
                year_month = date[:7]  # 取YYYY-MM
                if year_month not in by_year_month:
                    by_year_month[year_month] = []
                by_year_month[year_month].append(newspaper)

        # 为每个月生成归档页面
        for year_month, month_newspapers in by_year_month.items():
            year = year_month[:4]
            month = year_month[5:7]

            # 生成目录结构: archive/2025/11.html
            year_dir = archive_dir / year
            year_dir.mkdir(exist_ok=True)

            # 生成月度归档页面
            cards_html = ""
            for newspaper in month_newspapers:
                escape_html = lambda text: str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')

                cards_html += f"""
        <div class="newspaper-card" onclick="window.location.href='../detail/{newspaper['publish_date']}.html'">
            <div class="newspaper-header">
                <h3 class="newspaper-title">{escape_html(newspaper.get('title', '未知标题'))}</h3>
                <div class="newspaper-meta">
                    <div class="meta-item">
                        <i class="fas fa-calendar"></i>
                        <span>{newspaper.get('publish_date', '未知日期')}</span>
                    </div>
                    <div class="meta-item">
                        <i class="fas fa-video"></i>
                        <span>{newspaper.get('bv_id', '未知BV号')}</span>
                    </div>
                </div>
            </div>
            <div class="newspaper-overview">
                {escape_html((newspaper.get('overview', '')[:150]))}...
            </div>
            <div class="newspaper-stats">
                <div class="stats-count">
                    <i class="fas fa-list"></i>
                    {newspaper.get('news_count', 0)} 条资讯
                </div>
                <div style="color: #999; font-size: 12px;">
                    {newspaper.get('organize_time', '')}
                </div>
            </div>
        </div>"""

            archive_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{year}年{month}月AI早报归档 - AI早报</title>
    <link rel="icon" type="image/jpeg" href="../static/favicon.jpeg">
    <link rel="stylesheet" href="../static/css/style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <header class="header">
            <div class="header-content">
                <h1 class="logo">
                    <i class="fas fa-newspaper"></i>
                    AI早报
                </h1>
                <p class="subtitle">{year}年{month}月AI早报归档</p>
            </div>
        </header>

        <!-- 主要内容区域 -->
        <main class="main">
            <div class="toolbar">
                <button class="btn-refresh" onclick="window.location.href='../index.html'">
                    <i class="fas fa-arrow-left"></i>
                    返回首页
                </button>
                <div class="stats">
                    <span>共 {len(month_newspapers)} 条早报</span>
                </div>
            </div>

            <div class="newspapers-list">
                {cards_html}
            </div>
        </main>

        <!-- 底部 -->
        <footer class="footer">
            <p>&copy; 2025 AI早报 - <a href="https://github.com/musnows/juya_agent" target="_blank">musnows/juya_agent</a> - 整理自橘鸦AI早报</p>
        </footer>
    </div>
</body>
</html>"""

            month_file = year_dir / f"{month}.html"
            with open(month_file, 'w', encoding='utf-8') as f:
                f.write(archive_html)

        self.logger.info(f"Generated archive pages for {len(by_year_month)} months in: {archive_dir}")

    def _auto_git_commit(self):
        """自动Git提交更新

        检查dist目录是否存在git仓库，如果存在则提交更新。
        提交信息格式: update: daily report auto update yyyy-mm-dd
        """
        dist_git_dir = self.output_dir / ".git"
        if not dist_git_dir.exists():
            self.logger.info("dist directory is not a Git repository, skipping auto commit")
            return

        self.logger.info("Detected Git repository, committing updates...")
        try:
            # 获取当前日期
            current_date = datetime.now().strftime("%Y-%m-%d")

            # 执行git add --all
            subprocess.run(["git", "add", "--all"], check=True, capture_output=True, 
                           text=True, cwd=self.output_dir)
            self.logger.info("All changes added to staging area")

            # 执行git commit
            commit_message = f"update: daily report auto update {current_date}"
            subprocess.run(["git", "commit", "-m", commit_message], check=True, capture_output=True, 
                           text=True, cwd=self.output_dir)
            self.logger.info(f"Committed updates: {commit_message}")

            # 执行git push
            subprocess.run(["git", "push"], check=True, capture_output=True, text=True, 
                           cwd=self.output_dir, timeout=300)
            self.logger.info("Push completed successfully")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git operation failed: {e}")
        except Exception as e:
            self.logger.error(f"Error during Git commit process: {e}")

    def generate_static_site(self) -> bool:
        """生成完整的静态网站（优化版本）"""
        try:
            self.logger.info("Loading newspaper data...")
            newspapers = self._load_newspapers()

            if not newspapers:
                self.logger.warning("No newspaper data found")
                return False

            self.logger.info(f"Found {len(newspapers)} newspaper files")

            # 1. 生成首页HTML（仅包含最新15条数据）
            self.logger.info("Generating optimized homepage...")
            index_html = self._generate_html_index(newspapers)
            index_filepath = self.output_dir / 'index.html'
            with open(index_filepath, 'w', encoding='utf-8') as f:
                f.write(index_html)
            self.logger.info(f"Optimized homepage generated: {index_filepath}")

            # 2. 生成所有独立详情页面
            self.logger.info("Generating detail pages...")
            self._generate_detail_pages(newspapers)

            # 3. 生成归档页面
            self.logger.info("Generating archive pages...")
            self._generate_archive_pages(newspapers)

            # 4. 生成分页数据文件
            self.logger.info("Generating paginated data files...")
            self._generate_json_data(newspapers)

            # 5. 复制静态文件
            self.logger.info("Copying static files...")
            self._copy_static_files()

            # 6. 生成站点地图（SEO优化）
            self.logger.info("Generating sitemap...")
            self._generate_sitemap(newspapers)

            # 7. 生成README文件
            readme_content = f"""# AI早报静态网站（优化版本）

## 生成时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 新特性
✅ **独立详情页面**: 每篇早报都有独立的URL和页面
✅ **快速加载**: 首页仅加载最新15条数据，避免巨大文件影响性能
✅ **路径支持**: 支持分享具体某一天的早报链接
✅ **分页加载**: 使用异步加载，按需获取更多内容
✅ **归档页面**: 按年月组织，方便查找历史早报
✅ **简洁设计**: 详情页面专注内容，无无关推荐

## 文件结构
```
dist/
├── index.html                    # 首页（最新15条早报）
├── detail/                       # 详情页面目录
│   ├── 2025-11-23.html          # 早报详情页
│   └── ...
├── archive/                      # 归档页面目录
│   ├── 2025/11.html             # 2025年11月归档
│   └── ...
├── data/                         # 数据文件目录
│   ├── list_page_1.json         # 分页数据
│   ├── detail_2025-11-23.json   # 详情数据
│   └── ...
├── static/                       # 静态资源
│   ├── css/style.css
│   ├── favicon.jpeg
│   └── ...
└── sitemap.xml                  # 站点地图
```

## 使用方法
1. **直接访问**: 打开 `index.html` 查看最新早报
2. **详情页面**: 访问 `detail/YYYY-MM-DD.html` 查看具体某一天的早报
3. **归档浏览**: 访问 `archive/YYYY/MM.html` 查看月度归档

## 分享链接示例
- 首页: `index.html`
- 2025年11月23日早报: `detail/2025-11-23.html`
- 2025年11月归档: `archive/2025/11.html`

## 数据统计
- 早报总数: {len(newspapers)}
- 最新早报: {newspapers[0]['title'] if newspapers else '无'}
- 最新日期: {newspapers[0]['publish_date'] if newspapers else '无'}
- 首页显示: {min(self.page_size, len(newspapers))} 条
- 详情页面: {len(newspapers)} 个独立页面

## 性能优化
- **首页加载速度**: 从加载全量数据改为仅15条，大幅提升首屏速度
- **按需加载**: 后续页面通过AJAX异步加载，提升用户体验
- **SEO友好**: 每篇早报都有独立URL，便于搜索引擎收录
"""

            readme_filepath = self.output_dir / 'README.md'
            with open(readme_filepath, 'w', encoding='utf-8') as f:
                f.write(readme_content)

            self.logger.info(f"README file generated: {readme_filepath}")

            # 自动Git提交更新
            self._auto_git_commit()

            self.logger.info("✅ Static website generation completed successfully!")
            self.logger.info(f"📊 Generated {len(newspapers)} detail pages")
            self.logger.info(f"🏠 Homepage shows {min(self.page_size, len(newspapers))} recent newspapers")
            self.logger.info(f"📁 Archive pages organized by year/month")

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to generate static website: {e}")
            return False

    def _generate_sitemap(self, newspapers: List[Dict]):
        """生成站点地图（SEO优化）"""
        base_url = "https://your-domain.com"  # 需要用户配置实际域名

        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        # 添加首页
        sitemap_xml += f"""
  <url>
    <loc>{base_url}/</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>"""

        # 添加详情页面
        for newspaper in newspapers:
            date = newspaper.get('publish_date', '')
            if date:
                sitemap_xml += f"""
  <url>
    <loc>{base_url}/detail/{date}.html</loc>
    <lastmod>{date}</lastmod>
    <changefreq>never</changefreq>
    <priority>0.8</priority>
  </url>"""

        # 添加归档页面
        archive_years = set()
        for newspaper in newspapers:
            date = newspaper.get('publish_date', '')
            if len(date) >= 7:
                archive_years.add(date[:7])

        for year_month in sorted(archive_years, reverse=True):
            year = year_month[:4]
            month = year_month[5:7]
            sitemap_xml += f"""
  <url>
    <loc>{base_url}/archive/{year}/{month}.html</loc>
    <lastmod>{year_month}-01</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>"""

        sitemap_xml += '\n</urlset>'

        sitemap_filepath = self.output_dir / 'sitemap.xml'
        with open(sitemap_filepath, 'w', encoding='utf-8') as f:
            f.write(sitemap_xml)

        self.logger.info(f"Sitemap generated: {sitemap_filepath}")