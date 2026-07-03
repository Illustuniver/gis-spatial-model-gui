# -*- coding: utf-8 -*-
"""
tab1_vector_join.py — 矢→矢空间连接页
========================================
从原 datasets_gui.py 的 _build_tab1() + _list_fields_t1() + _run_tab1() 迁移。
功能: 将源图层字段根据空间关系赋值给目标图层。
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import geopandas as gpd

from app.ui.widgets.file_picker import FilePicker
from app.utils.thread_worker import TaskWorker


class VectorJoinPage(ttk.Frame):
    """矢→矢空间连接页面."""

    def __init__(self, master, app_state, log_manager):
        super().__init__(master)
        self.app_state = app_state
        self.log = log_manager

        # 内部状态变量
        self.t1_target = tk.StringVar()
        self.t1_source = tk.StringVar()
        self.t1_rel = tk.StringVar(value="点在面内")
        self.t1_field = tk.StringVar()
        self.t1_newname = tk.StringVar()
        self.t1_out = tk.StringVar(value="result_extracted.shp")
        self.t1_overwrite = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self):
        """构建界面."""
        frame = self  # self 就是 Frame
        row = 0

        # 目标图层
        ttk.Label(frame, text="目标图层 (接收属性):").grid(row=row, column=0, sticky='w', pady=2)
        self._target_picker = FilePicker(frame, label_text="", mode="file",
            filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
        self._target_picker.grid(row=row, column=1, columnspan=2, sticky='we', pady=2)
        self._target_picker.bind('<<FileSelected>>', lambda e: self.t1_target.set(self._target_picker.get_path()))
        row += 1

        # 源图层
        ttk.Label(frame, text="源图层 (提供属性):").grid(row=row, column=0, sticky='w', pady=2)
        self._source_picker = FilePicker(frame, label_text="", mode="file",
            filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
        self._source_picker.grid(row=row, column=1, columnspan=2, sticky='we', pady=2)
        self._source_picker.bind('<<FileSelected>>', lambda e: self.t1_source.set(self._source_picker.get_path()))
        row += 1

        # 空间关系
        ttk.Label(frame, text="空间关系:").grid(row=row, column=0, sticky='w', pady=2)
        ttk.Combobox(frame, textvariable=self.t1_rel,
            values=["点在面内", "面包含点", "相交", "最近"],
            width=15, state='readonly'
        ).grid(row=row, column=1, sticky='w', pady=2)
        row += 1

        # 提取字段
        ttk.Label(frame, text="提取字段:").grid(row=row, column=0, sticky='w', pady=2)
        self.t1_field_box = ttk.Combobox(frame, textvariable=self.t1_field, width=25)
        self.t1_field_box.grid(row=row, column=1, sticky='w', pady=2)
        ttk.Button(frame, text="刷新字段", command=self._list_fields).grid(row=row, column=2)
        row += 1

        # 新字段名
        ttk.Label(frame, text="新字段名:").grid(row=row, column=0, sticky='w', pady=2)
        ttk.Entry(frame, textvariable=self.t1_newname, width=25).grid(row=row, column=1, sticky='w', pady=2)
        row += 1

        # 输出
        ttk.Label(frame, text="输出文件名:").grid(row=row, column=0, sticky='w', pady=2)
        ttk.Entry(frame, textvariable=self.t1_out, width=45).grid(row=row, column=1, sticky='w', pady=2)
        ttk.Checkbutton(frame, text="覆盖已有", variable=self.t1_overwrite).grid(row=row, column=2, sticky='w')
        row += 1

        # 执行
        ttk.Button(frame, text="▶ 执行", command=self._on_run).grid(row=row, column=1, pady=10)

        # 列权重
        frame.columnconfigure(1, weight=1)

    def _list_fields(self):
        """刷新源图层字段列表."""
        path = self.t1_source.get().strip()
        if not path or not os.path.exists(path):
            self.log.log("[WARN] 请先选择源图层", 'warn')
            return
        try:
            gdf = gpd.read_file(path)
            fields = [c for c in gdf.columns if c != gdf.geometry.name]
            self.t1_field_box['values'] = fields
            if fields:
                self.t1_field.set(fields[0])
                self.t1_newname.set(fields[0])
            self.log.log(f"源图层字段: {len(fields)} 个")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _on_run(self):
        """执行空间连接."""
        # 智能文件选择: 空时弹出对话框
        target = self.t1_target.get().strip()
        if not target:
            p = filedialog.askopenfilename(title="选择目标图层",
                filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
            if not p:
                return
            self.t1_target.set(p)
            target = p

        source = self.t1_source.get().strip()
        if not source:
            p = filedialog.askopenfilename(title="选择源图层",
                filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
            if not p:
                return
            self.t1_source.set(p)
            source = p

        out_dir = self.app_state.config.out_dir if self.app_state.config else ''
        if not out_dir:
            messagebox.showwarning("配置", "请先设置输出目录")
            return

        out_path = os.path.join(out_dir, self.t1_out.get().strip())
        if os.path.exists(out_path) and not self.t1_overwrite.get():
            messagebox.showwarning("文件已存在",
                f"{out_path}\n请勾选 [覆盖已有] 或修改输出文件名")
            return

        params = {
            'target': target,
            'source': source,
            'relation': self.t1_rel.get(),
            'field': self.t1_field.get(),
            'new_name': self.t1_newname.get() or self.t1_field.get(),
            'output': out_path,
        }

        def _task(stop_event=None, progress_cb=None):
            from app.core.processors import VectorJoinProcessor
            proc = VectorJoinProcessor(params, log_func=self.log.log, stop_event=stop_event)
            result = proc.run()
            if result:
                self.log.log(f"✓ 空间连接完成 → {result}")
            return result

        worker = TaskWorker(_task, on_finished=lambda r: None,
                          on_error=lambda e: self.log.log(f"✗ 错误: {e}", 'error'))
        worker.set_stop_event(self.app_state.stop_event)
        worker.start()

    # ── 状态读写 ──

    def get_state(self):
        return {
            'target': self.t1_target.get(),
            'source': self.t1_source.get(),
            'relation': self.t1_rel.get(),
            'field': self.t1_field.get(),
            'new_name': self.t1_newname.get(),
            'output_name': self.t1_out.get(),
            'overwrite': self.t1_overwrite.get(),
        }

    def set_state(self, state):
        if not state:
            return
        self.t1_target.set(state.get('target', ''))
        self.t1_source.set(state.get('source', ''))
        self.t1_rel.set(state.get('relation', '点在面内'))
        self.t1_field.set(state.get('field', ''))
        self.t1_newname.set(state.get('new_name', ''))
        self.t1_out.set(state.get('output_name', 'result_extracted.shp'))
        self.t1_overwrite.set(state.get('overwrite', False))
        if self.t1_target.get():
            self._target_picker.set_path(self.t1_target.get())
        if self.t1_source.get():
            self._source_picker.set_path(self.t1_source.get())
