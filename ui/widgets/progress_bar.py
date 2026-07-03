# -*- coding: utf-8 -*-
"""
progress_bar.py — 带取消按钮的进度条组件
=========================================
组成: 进度条 + 百分比文字 + 状态文字 + 取消按钮。
两种模式: 确定模式 (current/total) / 不确定模式 (跑马灯)。
与 TaskWorker 配套，进度更新必须在主线程。
"""

import tkinter as tk
from tkinter import ttk


class ProgressBar(ttk.Frame):
    """带取消的进度条.

    Usage:
        pb = ProgressBar(master, show_cancel=True)
        pb.pack(fill='x')
        pb.set(3, 10, msg="处理中...")
        pb.on_cancel(lambda: stop_event.set())
        # 完成后
        pb.set(10, 10, msg="完成!")
    """

    def __init__(self, master, show_cancel=True):
        """
        Args:
            master:      父容器
            show_cancel: 是否显示取消按钮
        """
        super().__init__(master)
        self._show_cancel = show_cancel
        self._cancel_cb = None
        self._total = 0
        self._finished = False

        # 进度条
        self._bar = ttk.Progressbar(self, mode='determinate', length=300)
        self._bar.pack(side='left', padx=(0, 5))

        # 百分比 + 状态文字
        self._label = ttk.Label(self, text="0%", width=6)
        self._label.pack(side='left', padx=2)

        self._msg_label = ttk.Label(self, text="")
        self._msg_label.pack(side='left', padx=5, fill='x', expand=True)

        # 取消按钮
        if show_cancel:
            self._cancel_btn = ttk.Button(self, text="■ 取消", command=self._on_cancel_click)
            self._cancel_btn.pack(side='right', padx=2)

    def set(self, current, total, msg=""):
        """设置进度 (确定模式).

        Args:
            current: 当前进度值
            total:   总数
            msg:     状态文字
        """
        if total <= 0:
            return
        self._total = total
        self._bar.configure(mode='determinate', maximum=total)
        self._bar['value'] = current
        pct = int(100 * current / total)
        self._label.configure(text=f"{pct}%")
        self._msg_label.configure(text=msg)
        self._finished = (current >= total)

    def set_percent(self, percent, msg=""):
        """直接设置百分比.

        Args:
            percent: 0-100
            msg:     状态文字
        """
        self._bar.configure(mode='determinate', maximum=100)
        self._bar['value'] = percent
        self._label.configure(text=f"{int(percent)}%")
        self._msg_label.configure(text=msg)

    def start_indeterminate(self, msg=""):
        """启动不确定模式 (跑马灯)."""
        self._bar.configure(mode='indeterminate')
        self._bar.start()
        self._label.configure(text="...")
        self._msg_label.configure(text=msg)

    def stop(self):
        """停止不确定模式."""
        self._bar.stop()
        self._bar.configure(mode='determinate')

    def reset(self):
        """重置为 0."""
        self._bar.configure(mode='determinate', maximum=100)
        self._bar['value'] = 0
        self._label.configure(text="0%")
        self._msg_label.configure(text="")
        self._finished = False

    def on_cancel(self, callback):
        """设置取消回调.

        Args:
            callback: callable(), 点击取消按钮时调用.
        """
        self._cancel_cb = callback

    def _on_cancel_click(self):
        """取消按钮点击."""
        if self._cancel_cb:
            self._cancel_cb()
            self._msg_label.configure(text="正在取消...")

    @property
    def is_finished(self):
        """是否已完成."""
        return self._finished
