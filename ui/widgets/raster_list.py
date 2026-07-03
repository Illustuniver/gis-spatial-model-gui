# -*- coding: utf-8 -*-
"""
raster_list.py — 栅格列表管理组件
==================================
从原 datasets_gui.py 的 Tab2 栅格 Treeview 提取，封装为可复用组件。
支持: 添加/删除/编辑/自动命名/清空栅格条目。
兼容 .adf 目录和 .tif 文件。

避坑: .adf 目录添加前校验目录有效性，字段名冲突自动加后缀。
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class RasterList(ttk.Frame):
    """栅格列表管理组件.

    Usage:
        rl = RasterList(master, height=6)
        rl.pack(fill='both', expand=True)
        rl.add_raster('/path/to/dem.tif', band=1, field_name='dem_mean')
        rasters = rl.get_rasters()  # [{path, band, field_name, name}]
    """

    def __init__(self, master, show_band=True, show_field_name=True, height=6):
        """
        Args:
            master:          父容器
            show_band:       是否显示波段列
            show_field_name: 是否显示字段名列
            height:          Treeview 高度 (行数)
        """
        super().__init__(master)
        self._show_band = show_band
        self._show_field_name = show_field_name

        # ── Treeview ──
        self._build_columns()
        col_frame = ttk.Frame(self)
        col_frame.pack(fill='both', expand=True)

        self._tree = ttk.Treeview(
            col_frame, columns=self._cols, show='headings', height=height)
        self._tree.heading('path', text='文件路径')
        self._tree.column('path', width=380)
        if show_band:
            self._tree.heading('band', text='波段')
            self._tree.column('band', width=55, anchor='center')
        if show_field_name:
            self._tree.heading('field_name', text='属性表字段名')
            self._tree.column('field_name', width=160, anchor='center')
        self._tree.pack(side='left', fill='both', expand=True)

        # 滚动条
        vsb = ttk.Scrollbar(col_frame, orient='vertical', command=self._tree.yview)
        vsb.pack(side='right', fill='y')
        self._tree.configure(yscrollcommand=vsb.set)

        # 右键删除
        self._tree.bind('<Delete>', lambda e: self.remove_selected())

        # ── 操作按钮 ──
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', pady=(3, 0))
        ttk.Button(btn_frame, text="+ 添加栅格", command=self._add_raster).pack(side='left', padx=1)
        ttk.Button(btn_frame, text="+ 添加目录(.adf)", command=self._add_adf_dir).pack(side='left', padx=1)
        ttk.Button(btn_frame, text="− 删除选中", command=self.remove_selected).pack(side='left', padx=1)
        ttk.Button(btn_frame, text="编辑", command=self.edit_selected).pack(side='left', padx=1)
        ttk.Button(btn_frame, text="自动命名", command=self.auto_fill_names).pack(side='left', padx=(15, 1))
        ttk.Button(btn_frame, text="清空", command=self.clear).pack(side='left', padx=1)

    def _build_columns(self):
        """构建列列表."""
        cols = ['path']
        if self._show_band:
            cols.append('band')
        if self._show_field_name:
            cols.append('field_name')
        self._cols = tuple(cols)

    def _build_values(self, path, band, field_name, name):
        """构建 Treeview 行值元组."""
        vals = [path]
        if self._show_band:
            vals.append(band)
        if self._show_field_name:
            vals.append(field_name)
        return tuple(vals)

    def _add_raster(self):
        """添加栅格文件 (多选)."""
        files = filedialog.askopenfilenames(
            title="选择栅格文件 (可多选)",
            filetypes=[("Raster", "*.tif;*.img"), ("All", "*.*")])
        for f in files:
            band_count = 1
            try:
                import rasterio
                with rasterio.open(f) as src:
                    band_count = src.count
            except Exception:
                pass
            base = os.path.splitext(os.path.basename(f))[0].replace('.', '_')
            field_name = f"{base}_mean"
            # 重名加后缀
            field_name = self._unique_field_name(field_name)
            self._tree.insert('', 'end', values=self._build_values(f, 1, field_name, base))
            if band_count > 1:
                # 日志提示 (通过父级 log 或静默)
                pass

    def _add_adf_dir(self):
        """添加 .adf 目录."""
        d = filedialog.askdirectory(title="选择 .adf 目录")
        if not d:
            return
        adf_files = [f for f in os.listdir(d) if f.endswith('.adf')]
        if not adf_files:
            messagebox.showwarning("无效目录",
                f"目录中未找到 .adf 文件:\n{d}\n\n请选择包含 .adf 文件的父目录")
            return
        base = os.path.basename(d.rstrip('/\\'))
        field_name = self._unique_field_name(f"{base}_mean")
        self._tree.insert('', 'end', values=self._build_values(d, 1, field_name, base))

    def _unique_field_name(self, base_name):
        """确保字段名在当前列表中唯一, 冲突加后缀 _1, _2."""
        existing = set()
        for item in self._tree.get_children():
            vals = self._tree.item(item, 'values')
            # 字段名是最后一列
            if self._show_field_name and len(vals) > 0:
                existing.add(vals[-1])
            elif not self._show_field_name and len(vals) > 1:
                existing.add(vals[-1])

        if base_name not in existing:
            return base_name
        suffix = 1
        while f"{base_name}_{suffix}" in existing:
            suffix += 1
        return f"{base_name}_{suffix}"

    def add_raster(self, path, band=1, field_name=""):
        """添加单个栅格条目.

        Args:
            path:       文件路径
            band:       波段号
            field_name: 属性表字段名 (空则自动生成)
        """
        if not field_name:
            field_name = os.path.splitext(os.path.basename(path))[0].replace('.', '_') + '_mean'
        field_name = self._unique_field_name(field_name)
        name = os.path.basename(path) or os.path.basename(os.path.dirname(path))
        self._tree.insert('', 'end', values=self._build_values(path, band, field_name, name))

    def add_rasters(self, paths):
        """批量添加栅格.

        Args:
            paths: 文件路径列表.
        """
        for p in paths:
            self.add_raster(p)

    def add_adf_dir(self, dir_path):
        """添加 .adf 目录.

        Args:
            dir_path: 目录路径.
        """
        base = os.path.basename(dir_path.rstrip('/\\'))
        field_name = self._unique_field_name(f"{base}_mean")
        self._tree.insert('', 'end', values=self._build_values(dir_path, 1, field_name, base))

    def remove_selected(self):
        """删除选中的条目."""
        for item in self._tree.selection():
            self._tree.delete(item)

    def edit_selected(self):
        """编辑选中的栅格条目 (弹简单编辑框)."""
        sel = self._tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = list(self._tree.item(item, 'values'))

        win = tk.Toplevel(self)
        win.title("编辑栅格条目")
        win.geometry("500x180")
        win.transient(self)

        ttk.Label(win, text="文件/目录路径:").pack(pady=(10, 0))
        path_var = tk.StringVar(value=vals[0] if vals else "")
        ttk.Entry(win, textvariable=path_var, width=65).pack(padx=10)

        ttk.Label(win, text="波段号:").pack()
        band_var = tk.IntVar(value=int(vals[1]) if len(vals) > 1 and self._show_band else 1)
        ttk.Spinbox(win, from_=1, to=99, textvariable=band_var, width=8).pack()

        ttk.Label(win, text="属性表字段名:").pack()
        name_idx = 2 if self._show_band else 1
        name_var = tk.StringVar(value=vals[name_idx] if len(vals) > name_idx else "")
        ttk.Entry(win, textvariable=name_var, width=30).pack()

        def _save():
            new_vals = list(vals)
            new_vals[0] = path_var.get()
            if self._show_band:
                new_vals[1] = band_var.get()
            name_pos = 2 if self._show_band else 1
            if len(new_vals) > name_pos:
                new_vals[name_pos] = name_var.get()
            self._tree.item(item, values=tuple(new_vals))
            win.destroy()

        ttk.Button(win, text="保存", command=_save).pack(pady=8)

    def auto_fill_names(self, prefix=""):
        """自动填充字段名 (基于文件名).

        Args:
            prefix: 前缀 (预留).
        """
        for item in self._tree.get_children():
            vals = list(self._tree.item(item, 'values'))
            base = os.path.splitext(os.path.basename(vals[0]))[0].replace('.', '_')
            if not base:
                base = os.path.basename(os.path.dirname(vals[0]))
            if self._show_field_name:
                name_idx = 2 if self._show_band else 1
                if len(vals) > name_idx:
                    vals[name_idx] = f"{base}_mean"
            self._tree.item(item, values=tuple(vals))

    def clear(self):
        """清空所有条目."""
        for item in self._tree.get_children():
            self._tree.delete(item)

    def get_rasters(self):
        """获取所有栅格信息.

        Returns:
            list[dict]: [{path, band, field_name, name}, ...]
        """
        rasters = []
        for item in self._tree.get_children():
            vals = self._tree.item(item, 'values')
            path = vals[0]
            if self._show_band and self._show_field_name:
                band, field_name = int(vals[1]), vals[2]
            elif self._show_band:
                band, field_name = int(vals[1]), os.path.basename(path)
            elif self._show_field_name:
                band, field_name = 1, vals[1]
            else:
                band, field_name = 1, os.path.basename(path)
            name = os.path.basename(path) or os.path.basename(os.path.dirname(path))
            rasters.append({
                'path': path,
                'band': band,
                'field_name': field_name,
                'name': name,
            })
        return rasters

    def count(self):
        """获取条目数量."""
        return len(self._tree.get_children())
