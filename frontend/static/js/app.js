// AI早报前端应用主脚本

// 全局状态
let currentPage = 1;
let pageSize = 10;
let totalCount = 0;
let totalPages = 0;
let currentDetailFilename = null;

// DOM元素
const listView = document.getElementById('list-view');
const detailView = document.getElementById('detail-view');
const loading = document.getElementById('loading');
const newspapersList = document.getElementById('newspapers-list');
const pagination = document.getElementById('pagination');
const detailContent = document.getElementById('detail-content');
const totalCountSpan = document.getElementById('total-count');

// 初始化应用
document.addEventListener('DOMContentLoaded', function() {
    loadNewspapers();
});

// 加载早报列表
async function loadNewspapers(page = 1) {
    try {
        showLoading(true);

        const response = await fetch(`/api/newspapers?page=${page}&page_size=${pageSize}`);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '加载失败');
        }

        const data = result.data;
        currentPage = data.pagination.current_page;
        totalCount = data.pagination.total_count;
        totalPages = data.pagination.total_pages;

        // 更新统计信息
        totalCountSpan.textContent = `共 ${totalCount} 条早报`;

        // 渲染早报列表
        renderNewspapersList(data.newspapers);

        // 渲染分页控件
        renderPagination(data.pagination);

        showLoading(false);

    } catch (error) {
        console.error('加载早报失败:', error);
        showToast('加载早报失败: ' + error.message, 'error');
        showLoading(false);
    }
}

// 渲染早报列表
function renderNewspapersList(newspapers) {
    if (!newspapers || newspapers.length === 0) {
        newspapersList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-newspaper" style="font-size: 48px; color: #ccc; margin-bottom: 15px;"></i>
                <p style="color: #999;">暂无早报数据</p>
            </div>
        `;
        return;
    }

    const html = newspapers.map(newspaper => `
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
                ${escapeHtml(newspaper.overview || '').substring(0, 150)}...
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

    newspapersList.innerHTML = html;
}

// 渲染分页控件
function renderPagination(paginationData) {
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    // 上一页按钮
    html += `
        <button
            onclick="loadNewspapers(${currentPage - 1})"
            ${!paginationData.has_prev ? 'disabled' : ''}
            title="上一页"
        >
            <i class="fas fa-chevron-left"></i>
        </button>
    `;

    // 页码按钮
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        html += `<button onclick="loadNewspapers(1)">1</button>`;
        if (startPage > 2) {
            html += `<span style="color: #999;">...</span>`;
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `
            <button
                onclick="loadNewspapers(${i})"
                class="${i === currentPage ? 'active' : ''}"
            >
                ${i}
            </button>
        `;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += `<span style="color: #999;">...</span>`;
        }
        html += `<button onclick="loadNewspapers(${totalPages})">${totalPages}</button>`;
    }

    // 下一页按钮
    html += `
        <button
            onclick="loadNewspapers(${currentPage + 1})"
            ${!paginationData.has_next ? 'disabled' : ''}
            title="下一页"
        >
            <i class="fas fa-chevron-right"></i>
        </button>
    `;

    // 页面信息
    html += `
        <div class="pagination-info">
            第 ${currentPage} / ${totalPages} 页
        </div>
    `;

    pagination.innerHTML = html;
}

// 显示早报详情
async function showNewspaperDetail(filename) {
    try {
        showLoading(true);
        currentDetailFilename = filename;

        const response = await fetch(`/api/newspapers/${encodeURIComponent(filename)}`);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '加载详情失败');
        }

        const newspaper = result.data;
        renderNewspaperDetail(newspaper);

        // 切换视图
        listView.classList.add('hidden');
        detailView.classList.remove('hidden');

        showLoading(false);

        // 滚动到顶部
        window.scrollTo(0, 0);

    } catch (error) {
        console.error('加载早报详情失败:', error);
        showToast('加载详情失败: ' + error.message, 'error');
        showLoading(false);
    }
}

// 渲染早报详情
function renderNewspaperDetail(newspaper) {
    const html = `
        <h1>${escapeHtml(newspaper.title || '未知标题')}</h1>

        <div class="detail-meta">
            <div class="detail-meta-grid">
                <div class="detail-meta-item">
                    <i class="fas fa-calendar"></i>
                    <strong>发布日期：</strong>
                    <span>${newspaper.publish_date || '未知日期'}</span>
                </div>
                <div class="detail-meta-item">
                    <i class="fas fa-video"></i>
                    <strong>BV号：</strong>
                    <span>
                        ${newspaper.bv_id ?
                            `<a href="https://www.bilibili.com/video/${newspaper.bv_id}" target="_blank" class="bv-link">${newspaper.bv_id}</a>` :
                            '未知BV号'
                        }
                    </span>
                </div>
                <div class="detail-meta-item">
                    <i class="fas fa-clock"></i>
                    <strong>整理时间：</strong>
                    <span>${formatDate(newspaper.organize_time)}</span>
                </div>
                <div class="detail-meta-item">
                    <i class="fas fa-list"></i>
                    <strong>资讯数量：</strong>
                    <span>${newspaper.news_count || 0} 条</span>
                </div>
            </div>
        </div>

        <div class="detail-content-body">
            ${newspaper.html_content || '<p>内容加载失败</p>'}
        </div>
    `;

    detailContent.innerHTML = html;
}

// 返回列表视图
function showListView() {
    detailView.classList.add('hidden');
    listView.classList.remove('hidden');
    currentDetailFilename = null;
}

// 刷新当前页面数据
async function refreshData() {
    await loadNewspapers(currentPage);
    showToast('数据刷新成功', 'success');
}

// 刷新详情页面
async function refreshDetail() {
    if (currentDetailFilename) {
        await showNewspaperDetail(currentDetailFilename);
        showToast('详情刷新成功', 'success');
    }
}

// 显示/隐藏加载状态
function showLoading(show) {
    if (show) {
        loading.classList.remove('hidden');
        newspapersList.classList.add('hidden');
        pagination.classList.add('hidden');
    } else {
        loading.classList.add('hidden');
        newspapersList.classList.remove('hidden');
        if (totalPages > 1) {
            pagination.classList.remove('hidden');
        }
    }
}

// 显示提示消息
function showToast(message, type = 'success') {
    const toastId = type === 'error' ? 'error-toast' : 'success-toast';
    const messageId = type === 'error' ? 'error-message' : 'success-message';

    const toast = document.getElementById(toastId);
    const messageElement = document.getElementById(messageId);

    messageElement.textContent = message;
    toast.classList.remove('hidden');

    // 触发显示动画
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // 自动隐藏
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 300);
    }, 3000);
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 格式化日期
function formatDate(dateStr) {
    if (!dateStr) return '未知时间';

    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            return dateStr; // 如果无法解析，返回原字符串
        }

        const now = new Date();
        const diff = now - date;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));

        if (days === 0) {
            const hours = Math.floor(diff / (1000 * 60 * 60));
            if (hours === 0) {
                const minutes = Math.floor(diff / (1000 * 60));
                return minutes <= 1 ? '刚刚' : `${minutes}分钟前`;
            }
            return `${hours}小时前`;
        } else if (days === 1) {
            return '昨天';
        } else if (days < 7) {
            return `${days}天前`;
        } else {
            return date.toLocaleDateString('zh-CN');
        }
    } catch (e) {
        return dateStr;
    }
}

// 键盘快捷键支持
document.addEventListener('keydown', function(e) {
    // ESC键返回列表
    if (e.key === 'Escape' && !detailView.classList.contains('hidden')) {
        showListView();
    }

    // 左右箭头切换页面（仅在列表视图）
    if (!detailView.classList.contains('hidden')) {
        return;
    }

    if (e.key === 'ArrowLeft' && currentPage > 1) {
        loadNewspapers(currentPage - 1);
    } else if (e.key === 'ArrowRight' && currentPage < totalPages) {
        loadNewspapers(currentPage + 1);
    }
});

// 响应式处理
window.addEventListener('resize', function() {
    // 可以在这里添加响应式逻辑
});

// 页面可见性变化处理
document.addEventListener('visibilitychange', function() {
    // 如果页面重新变为可见，刷新数据
    if (!document.hidden && !detailView.classList.contains('hidden')) {
        // 可选：自动刷新详情页面
        // refreshDetail();
    }
});