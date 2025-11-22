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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import markdown


class WebGenerator:
    """静态前端生成器"""

    def __init__(self, docs_dir: str, output_dir: str):
        """初始化生成器

        Args:
            docs_dir: 源文档目录路径
            output_dir: 输出目录路径
        """
        self.docs_dir = Path(docs_dir)
        self.output_dir = Path(output_dir)
        self.page_size = 10

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

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

            # 提取概览
            overview_match = re.search(r'## 📋 本期概览\n\n(.+?)\n\n---', content, re.DOTALL)
            overview = overview_match.group(1).strip() if overview_match else ''

            return {
                'title': title,
                'publish_date': publish_date,
                'bv_id': bv_id,
                'organize_time': organize_time,
                'news_count': news_count,
                'overview': overview,
                'content': content,
                'html_content': markdown.markdown(
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
            }
        except Exception as e:
            print(f"解析文件失败 {filepath}: {e}")
            return None

    def _load_newspapers(self) -> List[Dict]:
        """加载所有早报数据"""
        newspapers = []

        if not self.docs_dir.exists():
            print(f"文档目录不存在: {self.docs_dir}")
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

            cards_html += f"""
        <div class="newspaper-card" onclick="showNewspaperDetail('{newspaper['filename']}')">
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
        // 早报数据
        const newspapersData = """ + json.dumps(newspapers, ensure_ascii=False, indent=2) + """;
        let currentPage = 1;
        let pageSize = """ + str(self.page_size) + """;
        let totalCount = """ + str(total_count) + """;

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

        function showListView() {
            document.getElementById('list-view').classList.remove('hidden');
            document.getElementById('detail-view').classList.add('hidden');
        }

        function showNewspaperDetail(filename) {
            const newspaper = newspapersData.find(n => n.filename === filename);
            if (!newspaper) {
                showToast('早报不存在', 'error');
                return;
            }

            // 生成详情内容
            const detailHtml = `
                <div class="newspaper-detail">
                    <div class="detail-title">
                        <h1>${escapeHtml(newspaper.title)}</h1>
                        <div class="detail-meta">
                            <div class="meta-item">
                                <i class="fas fa-calendar"></i>
                                <span>${newspaper.publish_date || '未知日期'}</span>
                            </div>
                            <div class="meta-item">
                                <i class="fas fa-video"></i>
                                <span>${newspaper.bv_id || '未知BV号'}</span>
                            </div>
                            <div class="meta-item">
                                <i class="fas fa-edit"></i>
                                <span>${formatDate(newspaper.organize_time)}</span>
                            </div>
                            <div class="meta-item">
                                <i class="fas fa-list"></i>
                                <span>${newspaper.news_count || 0} 条资讯</span>
                            </div>
                        </div>
                    </div>
                    <div class="detail-body">
                        ${newspaper.html_content}
                    </div>
                </div>
            `;

            document.getElementById('detail-content').innerHTML = detailHtml;
            document.getElementById('list-view').classList.add('hidden');
            document.getElementById('detail-view').classList.remove('hidden');
        }

        function loadMore() {
            currentPage++;
            const startIndex = (currentPage - 1) * pageSize;
            const endIndex = Math.min(startIndex + pageSize, totalCount);

            const newNewspapers = newspapersData.slice(startIndex, endIndex);
            const newspapersList = document.getElementById('newspapers-list');

            const newCardsHtml = newNewspapers.map(newspaper => `
                <div class="newspaper-card" onclick="showNewspaperDetail('${newspaper.filename}')">
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
            `).join('');

            newspapersList.insertAdjacentHTML('beforeend', newCardsHtml);

            // 如果已经加载完所有数据，隐藏加载更多按钮
            if (endIndex >= totalCount) {
                const loadMoreContainer = document.querySelector('.load-more-container');
                if (loadMoreContainer) {
                    loadMoreContainer.style.display = 'none';
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
        print(f"   ✅ 静态文件已复制到: {target_static_dir}")

    def _generate_json_data(self, newspapers: List[Dict]):
        """生成JSON数据文件"""
        # 生成完整的早报数据JSON
        json_data = {
            'newspapers': newspapers,
            'total_count': len(newspapers),
            'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'page_size': self.page_size
        }

        json_filepath = self.output_dir / 'data.json'
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"   ✅ JSON数据已生成: {json_filepath}")

    def generate_static_site(self) -> bool:
        """生成完整的静态网站"""
        try:
            print("📚 加载早报数据...")
            newspapers = self._load_newspapers()

            if not newspapers:
                print("⚠️ 没有找到早报数据")
                return False

            print(f"   📄 找到 {len(newspapers)} 个早报文件")

            print("🌐 生成HTML页面...")
            # 生成首页HTML
            index_html = self._generate_html_index(newspapers)
            index_filepath = self.output_dir / 'index.html'
            with open(index_filepath, 'w', encoding='utf-8') as f:
                f.write(index_html)
            print(f"   ✅ 首页已生成: {index_filepath}")

            print("📁 复制静态文件...")
            # 复制CSS、JS、图片等静态文件
            self._copy_static_files()

            print("📊 生成JSON数据...")
            # 生成JSON数据文件
            self._generate_json_data(newspapers)

            # 生成README文件
            readme_content = f"""# AI早报静态网站

## 生成时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 文件说明
- `index.html` - 主页面
- `static/` - 静态资源目录
  - `css/style.css` - 样式文件
  - `js/app.js` - JavaScript文件
  - `favicon.jpeg` - 网站图标
- `data.json` - 早报数据（JSON格式）

## 使用方法
直接在浏览器中打开 `index.html` 即可查看网站。

## 数据统计
- 早报总数: {len(newspapers)}
- 最新早报: {newspapers[0]['title'] if newspapers else '无'}
- 最新日期: {newspapers[0]['publish_date'] if newspapers else '无'}
"""

            readme_filepath = self.output_dir / 'README.md'
            with open(readme_filepath, 'w', encoding='utf-8') as f:
                f.write(readme_content)

            print(f"   ✅ README文件已生成: {readme_filepath}")

            return True

        except Exception as e:
            print(f"❌ 生成静态网站失败: {e}")
            return False