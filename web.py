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
    print(f"正在安装依赖包: {', '.join(packages)}")
    try:
        import subprocess
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install'
        ] + packages)
        print("✓ 依赖包安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 依赖包安装失败: {e}")
        return False

def check_dependencies():
    """检查并安装必要的依赖"""
    print("检查依赖包...")

    required_packages = ['flask', 'flask-cors', 'markdown']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✓ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} 未安装")

    if missing_packages:
        return install_dependencies(missing_packages)

    return True

def check_docs_directory():
    """检查docs目录是否存在"""
    docs_dir = Path(__file__).parent / "docs"
    if not docs_dir.exists():
        print(f"警告: docs目录不存在 ({docs_dir})")
        print("请确保项目根目录下有docs目录，并包含AI早报的markdown文件")
        return False

    # 检查是否有markdown文件
    md_files = list(docs_dir.glob("*.md"))
    if not md_files:
        print(f"警告: docs目录中没有找到markdown文件")
        return False

    print(f"✓ 找到 {len(md_files)} 个早报文件")
    return True

def main():
    """主函数"""
    print("AI早报前端项目启动脚本")
    print("="*30)

    # 检查Python版本
    if sys.version_info < (3, 6):
        print("✗ 需要Python 3.6或更高版本")
        sys.exit(1)

    print(f"✓ Python版本: {sys.version.split()[0]}")

    # 检查frontend目录
    if not frontend_dir.exists():
        print(f"✗ frontend目录不存在: {frontend_dir}")
        print("请确保在项目根目录下运行此脚本")
        sys.exit(1)

    print(f"✓ Frontend目录: {frontend_dir}")

    # 检查docs目录
    if not check_docs_directory():
        print("\n注意: 虽然docs目录有问题，但服务仍将启动")
        print("你可以在服务启动后，将早报文件放入docs目录")

    # 检查依赖
    if not check_dependencies():
        print("✗ 依赖检查失败")
        sys.exit(1)

    # 直接导入并启动Flask应用，不使用子进程
    try:
        # 导入app模块
        from app import app

        print("\n" + "="*50)
        print("🚀 AI早报前端服务启动中...")
        print("="*50)

        # 启动信息
        host = '0.0.0.0'
        port = 15000
        print(f"📍 访问地址: http://localhost:{port}")
        print("按 Ctrl+C 停止服务")
        print("="*50)

        # 直接运行Flask应用
        app.run(debug=True, host=host, port=port)

    except ImportError as e:
        print(f"✗ 无法导入应用模块: {e}")
        print("请检查frontend/app.py文件是否存在")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except Exception as e:
        print(f"\n✗ 运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()