#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI早报前端应用 - 后端API服务
提供早报数据的REST API接口
"""

import os
import re
import json
from datetime import datetime
from typing import List, Dict, Optional
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import markdown

app = Flask(__name__)
CORS(app)

# 配置
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
PAGE_SIZE = 10

class NewspaperService:
    """早报数据服务"""

    def __init__(self, docs_dir: str):
        self.docs_dir = docs_dir
        self._cache = {}
        self._last_load_time = None

    def _parse_filename(self, filename: str) -> Dict:
        """解析文件名获取信息"""
        # 文件名格式: BV号_日期_AI早报.md
        match = re.match(r'([^_]+)_(\d{4}-\d{2}-\d{2})_AI早报\.md', filename)
        if match:
            return {
                'bv_id': match.group(1),
                'date': match.group(2),
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
        current_time = datetime.now()

        # 如果缓存存在且未过期，直接返回
        if self._cache and self._last_load_time and \
           (current_time - self._last_load_time).seconds < 300:  # 5分钟缓存
            return self._cache['newspapers']

        newspapers = []

        if not os.path.exists(self.docs_dir):
            print(f"文档目录不存在: {self.docs_dir}")
            return newspapers

        # 遍历docs目录下的所有markdown文件
        for filename in os.listdir(self.docs_dir):
            if filename.endswith('.md'):
                file_info = self._parse_filename(filename)
                if file_info:
                    filepath = os.path.join(self.docs_dir, filename)
                    newspaper_data = self._parse_markdown_file(filepath)

                    if newspaper_data:
                        # 合并文件信息和解析内容
                        newspaper_data.update(file_info)
                        newspapers.append(newspaper_data)

        # 按日期排序（最新的在前面）
        newspapers.sort(key=lambda x: x.get('publish_date', ''), reverse=True)

        # 更新缓存
        self._cache = {
            'newspapers': newspapers,
            'total_count': len(newspapers)
        }
        self._last_load_time = current_time

        return newspapers

    def get_newspapers(self, page: int = 1, page_size: int = PAGE_SIZE) -> Dict:
        """获取早报列表（分页）"""
        newspapers = self._load_newspapers()
        total_count = len(newspapers)

        # 计算分页
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_newspapers = newspapers[start_index:end_index]

        # 计算总页数
        total_pages = (total_count + page_size - 1) // page_size

        return {
            'newspapers': page_newspapers,
            'pagination': {
                'current_page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }

    def get_newspaper_by_filename(self, filename: str) -> Optional[Dict]:
        """根据文件名获取单个早报详情"""
        newspapers = self._load_newspapers()
        for newspaper in newspapers:
            if newspaper.get('filename') == filename:
                return newspaper
        return None

# 创建早报服务实例
newspaper_service = NewspaperService(DOCS_DIR)

@app.route('/')
def index():
    """主页 - 返回前端页面"""
    return render_template('index.html')

@app.route('/api/newspapers')
def get_newspapers():
    """获取早报列表API"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', PAGE_SIZE))

        result = newspaper_service.get_newspapers(page, page_size)
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/newspapers/<filename>')
def get_newspaper_detail(filename):
    """获取早报详情API"""
    try:
        newspaper = newspaper_service.get_newspaper_by_filename(filename)
        if newspaper:
            return jsonify({
                'success': True,
                'data': newspaper
            })
        else:
            return jsonify({
                'success': False,
                'error': '早报不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/refresh')
def refresh_cache():
    """刷新缓存API"""
    try:
        # 清空缓存强制重新加载
        newspaper_service._cache = {}
        newspaper_service._last_load_time = None

        newspapers = newspaper_service._load_newspapers()
        return jsonify({
            'success': True,
            'data': {
                'total_count': len(newspapers),
                'message': '缓存刷新成功'
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print(f"文档目录: {DOCS_DIR}")
    print("启动AI早报前端服务...")
    app.run(debug=True, host='0.0.0.0', port=5001)