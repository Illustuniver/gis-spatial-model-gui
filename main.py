# -*- coding: utf-8 -*-
"""
main.py — 数据处理与建模平台 入口
====================================
分层架构 GIS 数据处理桌面工具。

运行方式:
    cd app/ && python main.py
"""

import sys
import os

# ── 路径注入: 确保能 import scripts/processing/ 下的模块 ──
# 从 app/ 出发: ../scripts/processing/
_PROCESSING_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', 'scripts', 'processing'
))
if os.path.isdir(_PROCESSING_DIR):
    if _PROCESSING_DIR not in sys.path:
        sys.path.insert(0, _PROCESSING_DIR)

# 同时将工作空间根目录加入 sys.path (确保 from app.xxx import 正常)
_ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from ui.main_window import MainWindow
import tkinter as tk


def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == '__main__':
    main()
