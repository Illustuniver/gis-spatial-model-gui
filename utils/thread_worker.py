# -*- coding: utf-8 -*-
"""
thread_worker.py — 统一后台任务封装
=====================================
替代原 datasets_gui.py 中 _run_in_thread 的重复模式。
提供: 进度回调、取消支持、完成/错误回调、运行状态查询。

注意: 零 tkinter 依赖，纯 threading 实现。
"""

import threading
import traceback


class TaskWorker:
    """统一后台任务执行器.

    所有耗时操作都通过这个类执行，替代原 _run_in_thread() 的重复代码。

    Usage:
        worker = TaskWorker(
            task_func=my_long_task,
            on_progress=lambda cur, total, msg: print(f"{cur}/{total}: {msg}"),
            on_finished=lambda result: print(f"Done: {result}"),
            on_error=lambda exc: print(f"Error: {exc}"),
        )
        worker.start(param1=value1)
        # ... 稍后 ...
        worker.cancel()
    """

    def __init__(self, task_func, on_progress=None, on_finished=None, on_error=None):
        """
        Args:
            task_func: 要执行的任务函数.
                      签名: func(*args, stop_event=None, progress_cb=None, **kwargs)
                      - stop_event: threading.Event, 用于取消检测
                      - progress_cb: callable(current, total, msg), 进度回调
            on_progress: 进度回调 (current: int, total: int, msg: str) -> None
            on_finished: 完成回调 (result: Any) -> None
            on_error:    错误回调 (exception: Exception) -> None
        """
        self._task_func = task_func
        self._on_progress = on_progress
        self._on_finished = on_finished
        self._on_error = on_error

        self._stop_event = None       # threading.Event, 由外部 (AppState) 注入
        self._thread = None           # 后台线程
        self._running = False

    def start(self, *args, **kwargs):
        """启动后台线程执行任务.

        Args:
            *args, **kwargs: 直接传给 task_func.
            会自动注入 stop_event 和 progress_cb 关键字参数.
        """
        if self._running:
            return  # 防止重复启动

        self._running = True

        def _progress_cb(current, total, msg=''):
            """线程安全的进度回调."""
            if self._on_progress:
                try:
                    self._on_progress(current, total, msg)
                except Exception:
                    pass

        def _run():
            try:
                result = self._task_func(
                    *args,
                    stop_event=self._stop_event,
                    progress_cb=_progress_cb,
                    **kwargs,
                )
                if self._on_finished:
                    self._on_finished(result)
            except Exception as exc:
                traceback.print_exc()
                if self._on_error:
                    self._on_error(exc)
            finally:
                self._running = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def set_stop_event(self, stop_event):
        """注入全局取消事件 (由 AppState 提供).

        Args:
            stop_event: threading.Event 实例.
                        注意: 全局只放一个 Event，所有 TaskWorker 共用。
        """
        self._stop_event = stop_event

    def cancel(self):
        """设置取消标志，请求任务停止."""
        if self._stop_event:
            self._stop_event.set()

    def is_running(self):
        """返回当前是否正在运行."""
        return self._running

    def join(self, timeout=None):
        """等待后台线程结束.

        Args:
            timeout: 最大等待秒数, None 表示无限等待.
        """
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
