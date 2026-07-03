# -*- coding: utf-8 -*-
"""
log_panel.py — 线程安全日志面板组件
====================================
封装 ScrolledText，支持三级日志颜色 (info/warn/error)。
线程安全: 后台线程调用 append() 塞队列，主线程 after() 轮询刷新。

红线: 绝对不能在后台线程直接调用 text.insert()，tkinter 不是线程安全的。
"""

import queue
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime


class LogPanel(ttk.LabelFrame):
    """线程安全日志面板.

    Usage:
        panel = LogPanel(master, title="日志", height=12)
        panel.pack(fill='both', expand=True)

        # 任何线程安全调用
        panel.append("处理开始")
        panel.append("警告: CRS 不一致", level="warn")
        panel.append("错误: 文件不存在", level="error")
    """

    # 级别 → (前景色, 前缀)
    LEVEL_STYLES = {
        'info':  ('black',  '[INFO]'),
        'warn':  ('#D2691E', '[WARN]'),   # 巧克力色 (暗色主题友好)
        'error': ('red',    '[ERROR]'),
    }

    def __init__(self, master, title="日志", height=12):
        """
        Args:
            master: 父容器
            title:  面板标题
            height: 文本框高度 (行数)
        """
        super().__init__(master, text=title, padding=3)
        self._queue = queue.Queue()
        self._poll_id = None

        # ScrolledText
        self._text = scrolledtext.ScrolledText(
            self, height=height, width=100,
            wrap='word', state='disabled'
        )
        self._text.pack(fill='both', expand=True)

        # 配置颜色标签
        for level, (color, _) in self.LEVEL_STYLES.items():
            tag_name = f"level_{level}"
            self._text.tag_config(tag_name, foreground=color)

        # 启动轮询
        self._start_poll()

    def append(self, msg, level='info'):
        """线程安全地追加一条日志.

        Args:
            msg:   日志内容
            level: 'info' / 'warn' / 'error'
        """
        ts = datetime.now().strftime('%H:%M:%S')
        self._queue.put((ts, level, str(msg)))

    def _start_poll(self):
        """启动主线程轮询, 每 100ms 取队列中的日志."""
        self._poll()

    def _poll(self):
        """批量从队列取日志并刷新到界面."""
        count = 0
        while True:
            try:
                ts, level, msg = self._queue.get_nowait()
                self._write_line(ts, level, msg)
                count += 1
            except queue.Empty:
                break

        if count > 0:
            # 自动滚动到底部
            self._text.see('end')

        self._poll_id = self.after(100, self._poll)

    def _write_line(self, ts, level, msg):
        """写入一行日志 (只在主线程调用)."""
        prefix = self.LEVEL_STYLES.get(level, ('[INFO]',))[1]
        tag = f"level_{level}" if level in self.LEVEL_STYLES else "level_info"

        self._text.configure(state='normal')
        self._text.insert('end', f"{prefix} {msg}\n", tag)
        self._text.configure(state='disabled')

    def clear(self):
        """清空所有日志."""
        self._text.configure(state='normal')
        self._text.delete('1.0', 'end')
        self._text.configure(state='disabled')

    def save_to_file(self, path):
        """保存日志到文件.

        Args:
            path: 输出文件路径.

        Returns:
            bool: 是否成功.
        """
        try:
            import os
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._text.get('1.0', 'end'))
            return True
        except Exception:
            import traceback
            traceback.print_exc()
            return False

    def get_text(self):
        """获取全部日志文本."""
        return self._text.get('1.0', 'end')

    def destroy(self):
        """销毁前停止轮询."""
        if self._poll_id:
            self.after_cancel(self._poll_id)
        super().destroy()
