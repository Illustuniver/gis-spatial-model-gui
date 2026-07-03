# -*- coding: utf-8 -*-
"""
process_manager.py — 跨平台子进程管理器
=========================================
封装 subprocess.Popen, 提供统一的 run() + kill() 接口。
跨平台终止: win32→taskkill /T /PID, 否则→terminate→wait→kill.

设计原则:
  - 精确 PID 终止 (不通杀所有同名进程)
  - 平台自适应 (Windows/Linux/macOS)
  - 与 TaskWorker 互补 (TaskWorker=线程, ProcessManager=子进程)
"""

import sys
import subprocess
import os


class ProcessManager:
    """跨平台子进程管理器.

    Usage:
        mgr = ProcessManager('frg_cmd.exe')
        returncode, stdout, stderr = mgr.run(args=['/m', fca, '/b', fbt], timeout=3600)
        # 或终止:
        mgr.kill()
    """

    def __init__(self, exe_path):
        """
        Args:
            exe_path: 可执行文件路径 (str)
        """
        self._exe = exe_path
        self._proc = None
        self._pid = None

    def run(self, args, timeout=None, cwd=None, env=None):
        """启动子进程并等待完成.

        Args:
            args:    命令行参数列表 (不包含 exe 本身)
            timeout: 超时秒数, None=无超时
            cwd:     工作目录
            env:     环境变量 (默认继承 os.environ)

        Returns:
            (returncode, stdout, stderr) 三元组.
            returncode 为 -1 表示启动失败.

        Raises:
            FileNotFoundError: exe 不存在.
            subprocess.TimeoutExpired: 超时.
        """
        cmd = [self._exe] + (args or [])
        environ = env if env is not None else os.environ.copy()

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=environ,
        )
        self._pid = self._proc.pid

        try:
            stdout, stderr = self._proc.communicate(timeout=timeout)
            return self._proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            self._proc.kill()
            stdout, stderr = self._proc.communicate()
            raise
        finally:
            self._proc = None

    def kill(self):
        """跨平台终止子进程.

        Windows: taskkill /F /T /PID (终止整棵进程树)
        Linux/macOS: terminate() → wait(5s) → kill()
        """
        if self._proc is None:
            return
        pid = self._pid or (self._proc.pid if self._proc else None)
        if pid is None:
            return

        if sys.platform == 'win32':
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(pid)],
                capture_output=True,
            )
        else:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()

        self._proc = None
        self._pid = None

    @property
    def is_running(self):
        """子进程是否在运行."""
        return self._proc is not None and self._proc.poll() is None

    @property
    def pid(self):
        """进程 PID (启动后有效)."""
        return self._pid
