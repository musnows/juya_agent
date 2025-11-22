# AI早报前端项目

这是一个用于展示AI早报的前端项目，支持列表浏览、分页和详情查看功能。

## 功能特性

- 📰 **早报列表展示**: 网格布局展示所有早报，最新早报在最前面
- 📄 **分页浏览**: 默认每页显示10条早报，支持翻页查看更多
- 🔍 **详情查看**: 点击任意早报可查看完整内容
- 🎨 **响应式设计**: 适配桌面端和移动端设备
- ⚡ **实时刷新**: 支持数据刷新和缓存管理
- ⌨️ **快捷键支持**: 支持键盘快捷键操作

## 项目结构

```
frontend/
├── app.py              # Flask后端应用
├── requirements.txt    # Python依赖包
├── README.md          # 项目说明文档
├── templates/         # HTML模板文件
│   └── index.html     # 主页面模板
└── static/           # 静态资源文件
    ├── css/
    │   └── style.css # 样式文件
    └── js/
        └── app.js    # 前端JavaScript代码
```

## 安装与运行

### 方法1: 使用启动脚本（推荐）

在项目根目录下运行：

```bash
python web.py
```

脚本会自动检查依赖、安装缺失的包并启动服务。

### 方法2: 手动安装运行

1. 安装依赖：
```bash
pip install -r frontend/requirements.txt
```

2. 运行服务：
```bash
cd frontend
python app.py
```

## 访问地址

- 本地访问: http://localhost:5000
- 局域网访问: http://你的IP地址:5000

## API接口

### 获取早报列表
```
GET /api/newspapers?page=1&page_size=10
```

### 获取早报详情
```
GET /api/newspapers/{filename}
```

### 刷新缓存
```
GET /api/refresh
```

## 使用说明

1. **列表浏览**:
   - 打开页面即可看到早报列表
   - 默认每页显示10条，最新早报在前
   - 点击卡片查看详情

2. **分页操作**:
   - 使用页面底部的分页控件
   - 支持上一页/下一页按钮
   - 可直接点击页码跳转

3. **快捷键**:
   - `ESC`: 返回列表视图
   - `←/→`: 在列表视图中切换页面

4. **刷新数据**:
   - 点击右上角刷新按钮
   - 服务会重新读取docs目录中的文件

## 数据格式

早报文件位于 `../docs` 目录下，文件名格式：
```
{BV号}_{日期}_AI早报.md
```

例如：`BV1S9yKB1Ekb_2025-11-21_AI早报.md`

## 技术栈

- **后端**: Python + Flask
- **前端**: HTML5 + CSS3 + JavaScript (ES6+)
- **样式**: CSS Grid + Flexbox (响应式设计)
- **Markdown**: Python-Markdown 库

## 浏览器兼容性

- Chrome 60+
- Firefox 60+
- Safari 12+
- Edge 79+

## 故障排除

1. **端口被占用**: 修改 `app.py` 中的端口设置
2. **依赖包问题**: 删除虚拟环境重新创建
3. **文档目录不存在**: 确保 `../docs` 目录存在且包含markdown文件
4. **样式异常**: 检查浏览器是否支持CSS Grid

## 开发说明

如需修改样式或功能，主要编辑以下文件：
- `static/css/style.css`: 样式调整
- `static/js/app.js`: 前端逻辑
- `app.py`: 后端API
- `templates/index.html`: 页面结构

## 许可证

本项目仅供学习交流使用。