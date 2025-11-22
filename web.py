#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI早报前端项目启动脚本
使用方法: python web.py
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path

# 添加frontend目录到Python路径
frontend_dir = Path(__file__).parent / "frontend"
sys.path.insert(0, str(frontend_dir))

def install_dependencies(packages):
    """安装依赖包"""
    try:
        import subprocess
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install'
        ] + packages)
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 依赖包安装失败: {e}")
        return False

def check_dependencies():
    """检查并安装必要的依赖"""
    required_packages = ['flask', 'flask-cors', 'markdown']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        return install_dependencies(missing_packages)

    return True

def check_docs_directory():
    """检查docs目录是否存在"""
    docs_dir = Path(__file__).parent / "docs"
    if not docs_dir.exists():
        return False

    # 检查是否有markdown文件
    md_files = list(docs_dir.glob("*.md"))
    if not md_files:
        return False

    return True

def main():
    """主函数"""
    # 检查Python版本
    if sys.version_info < (3, 6):
        print("✗ 需要Python 3.6或更高版本")
        sys.exit(1)

    # 检查frontend目录
    if not frontend_dir.exists():
        print(f"✗ frontend目录不存在: {frontend_dir}")
        sys.exit(1)

    # 检查docs目录
    check_docs_directory()

    # 检查依赖
    if not check_dependencies():
        print("✗ 依赖检查失败")
        sys.exit(1)

    # 直接导入并启动Flask应用，不使用子进程
    try:
        # 导入app模块
        from app import app

        # 直接运行Flask应用
        app.run(debug=True, host='0.0.0.0', port=15000)

    except ImportError as e:
        print(f"✗ 无法导入应用模块: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n✗ 运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()