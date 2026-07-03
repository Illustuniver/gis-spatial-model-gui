# -*- coding: utf-8 -*-
"""
file_picker.py — 文件/目录选择组件
====================================
一行布局: 标签 + 输入框 + 浏览按钮。
支持三种模式: file (单文件) / files (多文件) / dir (目录)。

静默友好: 取消选择时静默返回，不弹警告框。
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog


class FilePicker(ttk.Frame):
    """文件/目录选择组件.

    Usage:
        picker = FilePicker(master, label_text="目标矢量:", mode="file",
                           filetypes=[("SHP", "*.shp"), ("All", "*.*")])
        picker.pack(fill='x')
        picker.bind('<<FileSelected>>', lambda e: print(picker.get_path()))
    """

    def __init__(self, master, label_text="文件:", mode="file",
                 filetypes=None, default_value="", width=55):
        """
        Args:
            master:        父容器
            label_text:    标签文字
            mode:          'file' (单选文件) / 'files' (多选文件) / 'dir' (目录)
            filetypes:     文件过滤列表, 如 [("SHP", "*.shp"), ("All", "*.*")]
            default_value: 初始路径
            width:         输入框宽度 (字符数)
        """
        super().__init__(master)
        self._mode = mode
        self._filetypes = filetypes or [("All files", "*.*")]
        self._paths = []  # 多选模式下存所有路径
        self._width = width

        # 标签
        self._label = ttk.Label(self, text=label_text)
        self._label.pack(side='left')

        # 输入框
        self._var = tk.StringVar(value=default_value)
        self._entry = ttk.Entry(self, textvariable=self._var, width=width)
        self._entry.pack(side='left', padx=2, fill='x', expand=True)

        # 浏览按钮
        self._btn = ttk.Button(self, text="浏览", command=self._browse)
        self._btn.pack(side='left', padx=2)

    def _browse(self):
        """弹出选择对话框."""
        if self._mode == 'file':
            path = filedialog.askopenfilename(
                title="选择文件", filetypes=self._filetypes)
            if path:
                self._paths = [path]
                self._var.set(path)
                self.event_generate('<<FileSelected>>')

        elif self._mode == 'files':
            paths = filedialog.askopenfilenames(
                title="选择文件 (可多选)", filetypes=self._filetypes)
            if paths:
                self._paths = list(paths)
                # 输入框: 第一个路径 + (N-1)
                first = self._paths[0]
                extra = len(self._paths) - 1
                if extra > 0:
                    self._var.set(f"{first} (+{extra}个)")
                else:
                    self._var.set(first)
                self.event_generate('<<FileSelected>>')

        elif self._mode == 'dir':
            path = filedialog.askdirectory(title="选择目录")
            if path:
                self._paths = [path]
                self._var.set(path)
                self.event_generate('<<FileSelected>>')

    def get_path(self):
        """获取当前路径 (单选/目录模式)."""
        if self._paths:
            return self._paths[0]
        return self._var.get().strip()

    def get_paths(self):
        """获取所有路径 (多选模式)."""
        return list(self._paths) if self._paths else [self._var.get().strip()]

    def set_path(self, path):
        """设置路径."""
        self._paths = [path]
        self._var.set(path)

    def clear(self):
        """清空."""
        self._paths = []
        self._var.set("")

    def set_mode(self, mode):
        """切换模式."""
        self._mode = mode
