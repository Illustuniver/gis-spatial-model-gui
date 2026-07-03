# -*- coding: utf-8 -*-
"""
main_window.py — 主窗口 (整合调度中心)
========================================
全局状态管理、菜单栏、全局设置栏、4 个标签页、日志面板、状态栏。
工程文件存读、最近工程列表。
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from app.ui.state import AppState, ProjectSnapshot
from app.config.app_config import AppConfig
from app.utils.log_manager import LogManager, LogLevel
from app.utils.project_io import ProjectManager
from app.utils.thread_worker import TaskWorker
from app.ui.widgets.file_picker import FilePicker
from app.ui.widgets.log_panel import LogPanel
from app.ui.pages.tab1_vector_join import VectorJoinPage
from app.ui.pages.tab2_raster_sample import RasterSamplePage
from app.ui.pages.tab3_landscape import LandscapePage
from app.ui.pages.tab4_attribute import AttributePage


class MainWindow:
    """主窗口 — 全局调度中心."""

    def __init__(self, root):
        self.root = root
        self.root.title("数据处理与建模平台")
        self.root.geometry("1200x900")

        # ── 1. 状态初始化 ──
        self.app_state = AppState()
        self.app_state.config = AppConfig()
        self.log_manager = LogManager()
        self.app_state.log_manager = self.log_manager

        # ModelRegistry 自动发现
        try:
            from app.models.registry import registry
            count = registry.auto_discover()
            if count > 0:
                self.log_manager.log(f"发现 {count} 个内置模型")
        except Exception:
            pass

        self._project_manager = ProjectManager()
        self._current_project = None  # 当前工程路径
        self._pages = {}              # {tab_name: page_instance}
        self._log_visible = True

        # ── 2. 构建界面 ──
        self._build_menu()
        self._build_top_bar()
        self._build_notebook()
        self._build_log_panel()
        self._build_status_bar()

        # ── 3. 日志轮询 ──
        self._poll_log()

        # ── 4. 关闭事件 ──
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ━━━━━━ 菜单栏 ━━━━━━

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="新建工程", command=self._on_new_project)
        file_menu.add_command(label="打开工程...", command=self._on_open_project)
        file_menu.add_command(label="保存工程", command=self._on_save_project,
                              accelerator="Ctrl+S")
        file_menu.add_command(label="另存为...", command=self._on_save_project_as)
        file_menu.add_separator()
        self._recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="最近工程", menu=self._recent_menu)
        self._update_recent_menu()
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        # 视图
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="显示/隐藏日志", command=self._toggle_log)
        menubar.add_cascade(label="视图", menu=view_menu)

        # 帮助
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._on_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        # 快捷键
        self.root.bind('<Control-s>', lambda e: self._on_save_project())

    # ━━━━━━ 顶部全局设置栏 ━━━━━━

    def _build_top_bar(self):
        top = ttk.Frame(self.root, padding=5)
        top.pack(fill='x')

        # 参考栅格
        ttk.Label(top, text="参考栅格:").pack(side='left')
        self._ref_picker = FilePicker(top, label_text="", mode="file",
            filetypes=[("GeoTIFF", "*.tif"), ("All", "*.*")],
            width=50)
        self._ref_picker.pack(side='left', padx=2)
        if self.app_state.config.ref_raster:
            self._ref_picker.set_path(self.app_state.config.ref_raster)
        self._ref_picker.bind('<<FileSelected>>', self._on_ref_changed)

        # 输出目录
        ttk.Label(top, text="  输出目录:").pack(side='left', padx=(15, 0))
        self._out_picker = FilePicker(top, label_text="", mode="dir", width=40)
        self._out_picker.pack(side='left', padx=2)
        if self.app_state.config.out_dir:
            self._out_picker.set_path(self.app_state.config.out_dir)
        self._out_picker.bind('<<FileSelected>>', self._on_out_changed)

        # 状态标签
        ttk.Separator(top, orient='vertical').pack(side='left', padx=10, fill='y')
        self.status_label = ttk.Label(top, text="✓ 就绪", foreground="green")
        self.status_label.pack(side='left', padx=5)

    def _on_ref_changed(self, event=None):
        path = self._ref_picker.get_path()
        self.app_state.config.ref_raster = path
        self.app_state.config.save()
        self._update_status()

    def _on_out_changed(self, event=None):
        path = self._out_picker.get_path()
        self.app_state.config.out_dir = path
        self.app_state.config.save()
        self._update_status()

    def _update_status(self):
        ref = self.app_state.config.ref_raster
        out = self.app_state.config.out_dir
        if ref and out:
            try:
                import rasterio
                with rasterio.open(ref) as s:
                    info = f"{s.width}x{s.height}, {s.res[0]}m"
                self.status_label.config(text=f"✓ 就绪  |  参考: {info}", foreground="green")
            except Exception:
                self.status_label.config(text="⚠ 参考栅格无效", foreground="red")
        elif ref or out:
            self.status_label.config(text="⚠ 请设置参考栅格和输出目录", foreground="orange")
        else:
            self.status_label.config(text="⚠ 请先设置参考栅格和输出目录", foreground="orange")

    # ━━━━━━ Notebook (标签页) ━━━━━━

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Tab1: 矢→矢
        tab1 = VectorJoinPage(self.notebook, self.app_state, self.log_manager)
        self.notebook.add(tab1, text="矢→矢 (空间连接)")
        self._pages['tab1'] = tab1

        # Tab2: 矢→栅
        tab2 = RasterSamplePage(self.notebook, self.app_state, self.log_manager)
        self.notebook.add(tab2, text="矢→栅 (提取像元值)")
        self._pages['tab2'] = tab2

        # Tab3: 景观格局
        tab3 = LandscapePage(self.notebook, self.app_state, self.log_manager)
        self.notebook.add(tab3, text="景观格局指数")
        self._pages['tab3'] = tab3

        # Tab4: 属性表管理 (新增)
        tab4 = AttributePage(self.notebook, self.app_state, self.log_manager)
        self.notebook.add(tab4, text="属性表管理")
        self._pages['tab4'] = tab4

    # ━━━━━━ 日志面板 ━━━━━━

    def _build_log_panel(self):
        self._log_panel = LogPanel(self.root, title="日志", height=12)
        self._log_panel.pack(fill='both', expand=False, padx=5, pady=(0, 3))

    def _poll_log(self):
        """从 LogManager 取日志 → 输出到 LogPanel."""
        entries = self.log_manager.get_pending()
        for entry in entries:
            self._log_panel.append(entry['message'], level=entry['level'])
        self.root.after(100, self._poll_log)

    def _toggle_log(self):
        if self._log_visible:
            self._log_panel.pack_forget()
        else:
            self._log_panel.pack(fill='both', expand=False, padx=5, pady=(0, 3))
        self._log_visible = not self._log_visible

    # ━━━━━━ 状态栏 ━━━━━━

    def _build_status_bar(self):
        sb = ttk.Frame(self.root, padding=(5, 2))
        sb.pack(fill='x', side='bottom')

        self._status_text = ttk.Label(sb, text="就绪", foreground="gray")
        self._status_text.pack(side='left')

        recent = self.app_state.config.recent_projects
        recent_text = f"最近: {os.path.basename(recent[0])}" if recent else ""
        self._recent_status = ttk.Label(sb, text=recent_text, foreground="gray")
        self._recent_status.pack(side='right')

    # ━━━━━━ 工程文件 ━━━━━━

    def _on_new_project(self):
        if messagebox.askyesno("确认", "新建工程将清除当前所有参数，确定？"):
            self.app_state.reset()
            for page in self._pages.values():
                page.set_state({})
            self._current_project = None
            self.log_manager.log("新建工程")

    def _on_open_project(self):
        path = filedialog.askopenfilename(
            title="打开工程",
            filetypes=[("工程文件", "*.dsproj"), ("All", "*.*")])
        if not path:
            return
        self._load_project(path)

    def _on_save_project(self):
        if self._current_project:
            self._save_project(self._current_project)
        else:
            self._on_save_project_as()

    def _on_save_project_as(self):
        path = filedialog.asksaveasfilename(
            title="保存工程",
            defaultextension=".dsproj",
            filetypes=[("工程文件", "*.dsproj")])
        if not path:
            return
        self._save_project(path)

    def _save_project(self, path):
        # 收集所有页面状态 → ProjectSnapshot
        tab_mapping = [
            ('tab1', 'tab1_vector_join'),
            ('tab2', 'tab2_raster_sample'),
            ('tab3', 'tab3_landscape'),
            ('tab4', 'tab4_attribute'),
        ]
        snapshot = self.app_state.project
        snapshot.ref_raster = self.app_state.config.ref_raster
        snapshot.out_dir = self.app_state.config.out_dir
        snapshot.fragstats_exe = self.app_state.config.fragstats_exe
        snapshot.fca_dir = self.app_state.config.fca_dir
        from datetime import datetime
        snapshot.saved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        snapshot.tabs_data = {}
        for tab_key, data_key in tab_mapping:
            if tab_key in self._pages:
                snapshot.tabs_data[data_key] = self._pages[tab_key].get_state()

        self._project_manager.save(path, snapshot.to_dict())
        self._current_project = path
        self.app_state.config.add_recent_project(path)
        self._update_recent_menu()
        self.log_manager.log(f"工程已保存: {path}")
        self._recent_status.config(text=f"最近: {os.path.basename(path)}")

    def _load_project(self, path):
        try:
            data = self._project_manager.load(path)
        except Exception as e:
            messagebox.showerror("错误", f"打开工程失败:\n{e}")
            return

        # 全局配置
        g = data.get('global', {})
        self.app_state.config.ref_raster = g.get('ref_raster', '')
        self.app_state.config.out_dir = g.get('out_dir', '')
        self.app_state.config.fragstats_exe = g.get('fragstats_exe', '')
        self.app_state.config.fca_dir = g.get('fca_dir', '')
        self.app_state.config.save()
        self._ref_picker.set_path(self.app_state.config.ref_raster)
        # 工程状态 → ProjectSnapshot
        snapshot = ProjectSnapshot.from_dict(data)
        self.app_state.project = snapshot
        self.app_state.config.ref_raster = snapshot.ref_raster
        self.app_state.config.out_dir = snapshot.out_dir
        self.app_state.config.fragstats_exe = snapshot.fragstats_exe
        self.app_state.config.fca_dir = snapshot.fca_dir
        self.app_state.config.save()
        self._ref_picker.set_path(snapshot.ref_raster)
        self._out_picker.set_path(snapshot.out_dir)
        self._update_status()

        # 各页面恢复
        tab_mapping = [
            ('tab1', 'tab1_vector_join'),
            ('tab2', 'tab2_raster_sample'),
            ('tab3', 'tab3_landscape'),
            ('tab4', 'tab4_attribute'),
        ]
        for tab_key, data_key in tab_mapping:
            if tab_key in self._pages:
                self._pages[tab_key].set_state(snapshot.tabs_data.get(data_key, {}))

        self._current_project = path
        self.app_state.config.add_recent_project(path)
        self._update_recent_menu()
        self.log_manager.log(f"工程已打开: {path}")
        self._recent_status.config(text=f"最近: {os.path.basename(path)}")

    def _update_recent_menu(self):
        self._recent_menu.delete(0, 'end')
        recent = self.app_state.config.recent_projects
        if not recent:
            self._recent_menu.add_command(label="(无)", state='disabled')
            return
        for p in recent[:10]:
            self._recent_menu.add_command(
                label=os.path.basename(p),
                command=lambda path=p: self._load_project(path) if os.path.exists(path) else self.log_manager.log(f"工程不存在: {path}", 'warn'))

    # ━━━━━━ 其他 ━━━━━━

    def _on_about(self):
        messagebox.showinfo("关于",
            "数据处理与建模平台 v1.0\n\n"
            "基于分层架构的 GIS 数据处理桌面工具\n"
            "功能: 矢量空间连接 / 栅格像元提取 / 景观格局指数 / 属性表管理\n\n"
            "架构: app/ 分层设计 (config/core/models/utils/ui)\n"
            "原代码: scripts/processing/ (零修改)")

    def _on_close(self):
        # 保存配置
        self.app_state.config.ref_raster = self._ref_picker.get_path()
        self.app_state.config.out_dir = self._out_picker.get_path()
        self.app_state.config.save()

        # 终止所有任务
        self.app_state.cancel_all()
        self.root.destroy()
