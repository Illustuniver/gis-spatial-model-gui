# -*- coding: utf-8 -*-
"""
log_manager.py — 统一日志管理器
================================
线程安全的日志队列，支持:
  - 多级别日志 (INFO / WARN / ERROR)
  - 界面轮询消费 (queue.Queue)
  - 保存到文件
  - 清空

零 tkinter 依赖，纯 Python 标准库实现。
"""

import os
import queue
from datetime import datetime


class LogLevel:
    """日志级别常量."""
    INFO = 'info'
    WARN = 'warn'
    ERROR = 'error'


class LogManager:
    """统一日志管理器.

    Usage:
        mgr = LogManager()
        mgr.log("处理开始")
        mgr.log("警告: CRS 不一致", level=LogLevel.WARN)
        mgr.log("错误: 文件不存在", level=LogLevel.ERROR)

        # UI 轮询消费
        for msg in mgr.get_pending():
            display_in_gui(msg)
    """

    # 日志级别元数据: (前缀, 默认颜色)
    LEVEL_META = {
        LogLevel.INFO:  ('[INFO]',  'black'),
        LogLevel.WARN:  ('[WARN]',  'orange'),
        LogLevel.ERROR: ('[ERROR]', 'red'),
    }

    def __init__(self):
        self._queue = queue.Queue()
        self._history = []  # type: list[dict] — 完整历史 (用于保存到文件)

    def log(self, msg, level=LogLevel.INFO):
        """添加一条日志.

        Args:
            msg:   日志内容 (字符串)
            level: 日志级别 (LogLevel.INFO / WARN / ERROR)
        """
        ts = datetime.now().strftime('%H:%M:%S')
        prefix = self.LEVEL_META.get(level, ('[INFO]',))[0]
        full_msg = f"{prefix} {msg}"

        entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': msg,
            'formatted': full_msg,
        }
        self._history.append(entry)
        self._queue.put(entry)

    def get_pending(self):
        """非阻塞获取所有待处理日志条目 (供 UI 轮询).

        Returns:
            list[dict]: 日志条目列表, 每个条目含 timestamp/level/message/formatted.
        """
        entries = []
        while True:
            try:
                entry = self._queue.get_nowait()
                entries.append(entry)
            except queue.Empty:
                break
        return entries

    def save_to_file(self, path):
        """保存全部日志历史到文本文件.

        Args:
            path: 输出文件路径.

        Returns:
            bool: 是否保存成功.
        """
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"日志导出 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n")
                for entry in self._history:
                    ts = entry['timestamp'][:19].replace('T', ' ')
                    f.write(f"[{ts}] {entry['formatted']}\n")
            return True
        except Exception:
            import traceback
            traceback.print_exc()
            return False

    def get_history(self):
        """获取完整日志历史.

        Returns:
            list[dict]: 所有日志条目.
        """
        return list(self._history)

    def clear(self):
        """清空所有日志 (包括历史和队列)."""
        self._history.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


