# -*- coding: utf-8 -*-
"""
tab2_raster_sample.py — 矢→栅提取页
=====================================
从原 datasets_gui.py 的 _build_tab2() 全部迁移，含单文件子页和批量提取子页。
核心: 分矢量独立勾选 TIF 状态 + 尺度匹配 + 三模式字段生成。

⚠ 最复杂页面: t3e_tif_states 字典维护分矢量独立勾选状态，迁移完第一位测试。
"""

import os, re, glob
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

from app.ui.widgets.file_picker import FilePicker
from app.ui.widgets.raster_list import RasterList
from app.ui.dialogs.edit_raster import EditRasterDialog
from app.utils.thread_worker import TaskWorker
from app.config.presets import load_preset, list_presets, generate_feature_names
from app.core.spatial_metadata import ProcessingWindow


class RasterSamplePage(ttk.Frame):
    """矢→栅提取页面 (含单文件/批量)."""

    def __init__(self, master, app_state, log_manager):
        super().__init__(master)
        self.app_state = app_state
        self.log = log_manager

        # 子 Notebook
        self._sub_nb = ttk.Notebook(self)
        self._sub_nb.pack(fill='both', expand=True)

        single = ttk.Frame(self._sub_nb, padding=5)
        batch = ttk.Frame(self._sub_nb, padding=5)
        self._sub_nb.add(single, text="单文件提取")
        self._sub_nb.add(batch, text="批量提取")

        self._build_single(single)
        self._build_batch(batch)

    # ==================== 单文件子页 ====================

    def _build_single(self, frame):
        """单文件提取子页."""
        f = frame
        row = 0

        ttk.Label(f, text="目标矢量图层:").grid(row=row, column=0, sticky='w', pady=2)
        self._s_target_var = tk.StringVar()
        self._s_target_picker = FilePicker(f, label_text="", mode="file",
            filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
        self._s_target_picker.grid(row=row, column=1, columnspan=2, sticky='we', pady=2)
        self._s_target_picker.bind('<<FileSelected>>', lambda e: self._s_target_var.set(self._s_target_picker.get_path()))
        row += 1

        # 栅格列表 (用 RasterList 组件)
        ttk.Label(f, text="栅格文件列表:").grid(row=row, column=0, sticky='nw', pady=2)
        self._s_raster_list = RasterList(f, height=6)
        self._s_raster_list.grid(row=row, column=1, columnspan=2, sticky='nsew', pady=2)
        row += 1

        # 提取方式
        ttk.Label(f, text="提取方式:").grid(row=row, column=0, sticky='w', pady=2)
        self._s_method = tk.StringVar(value="直接提取像元值")
        ttk.Combobox(f, textvariable=self._s_method,
            values=["直接提取像元值", "质心提取", "像元均值", "最大值", "最小值"],
            width=18, state='readonly').grid(row=row, column=1, sticky='w', pady=2)
        row += 1

        # 输出
        ttk.Label(f, text="输出文件名:").grid(row=row, column=0, sticky='w', pady=2)
        self._s_out = tk.StringVar(value="sample_extracted.shp")
        ttk.Entry(f, textvariable=self._s_out, width=45).grid(row=row, column=1, sticky='w', pady=2)
        self._s_overwrite = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="覆盖已有", variable=self._s_overwrite).grid(row=row, column=2, sticky='w')
        row += 1

        ttk.Button(f, text="▶ 执行", command=self._run_single).grid(row=row, column=1, pady=10)

        f.columnconfigure(1, weight=1)

    def _run_single(self):
        target = self._s_target_var.get().strip()
        if not target:
            p = filedialog.askopenfilename(title="选择目标矢量",
                filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
            if not p: return
            self._s_target_var.set(p); target = p

        out_dir = self.app_state.config.out_dir if self.app_state.config else ''
        if not out_dir:
            messagebox.showwarning("配置", "请先设置输出目录"); return

        rasters = self._s_raster_list.get_rasters()
        if not rasters:
            messagebox.showwarning("配置", "请至少添加一个栅格"); return

        out_path = os.path.join(out_dir, self._s_out.get().strip())
        if os.path.exists(out_path) and not self._s_overwrite.get():
            messagebox.showwarning("文件已存在", f"{out_path}\n请勾选 [覆盖已有]")
            return

        params = {
            'target': target, 'rasters': rasters,
            'method': self._s_method.get(), 'output': out_path
        }

        def _task(stop_event=None, progress_cb=None):
            from app.core.processors import RasterSampler
            proc = RasterSampler(params, log_func=self.log.log, stop_event=stop_event)
            r = proc.run()
            if r: self.log.log(f"✓ 提取完成 → {r}")
            return r

        worker = TaskWorker(_task, on_error=lambda e: self.log.log(f"✗ {e}", 'error'))
        worker.set_stop_event(self.app_state.stop_event)
        worker.start()

    # ==================== 批量提取子页 ====================

    def _build_batch(self, frame):
        """批量提取子页 — 分矢量独立勾选 TIF 核心."""
        f = frame
        row = 0

        # 矢量源
        ttk.Label(f, text="样点矢量:").grid(row=row, column=0, sticky='nw', pady=2)
        vf = ttk.Frame(f)
        vf.grid(row=row, column=1, columnspan=3, sticky='w')
        self._b_targets = []
        self._b_target_listbox = tk.Listbox(vf, selectmode='single', height=3, width=55, exportselection=False)
        self._b_target_listbox.pack(side='left', fill='y')
        self._b_target_listbox.bind('<<ListboxSelect>>', self._on_vector_select)
        vsb = ttk.Scrollbar(vf, orient='vertical', command=self._b_target_listbox.yview)
        vsb.pack(side='right', fill='y'); self._b_target_listbox.configure(yscrollcommand=vsb.set)
        btns = ttk.Frame(vf); btns.pack(side='left', padx=3, fill='y')
        ttk.Button(btns, text="+ 添加", command=self._add_vector).pack(pady=1)
        ttk.Button(btns, text="- 移除", command=self._remove_vector).pack(pady=1)
        row += 1

        # 数据类型 + 预设
        ttk.Label(f, text="数据类型:").grid(row=row, column=0, sticky='w', pady=2)
        dtype_bar = ttk.Frame(f); dtype_bar.grid(row=row, column=1, columnspan=3, sticky='w')
        self._b_dtype = tk.StringVar(value="landscape")
        for t, v in [("景观指数", "landscape"), ("母质", "parent_material"), ("通用", "generic")]:
            ttk.Radiobutton(dtype_bar, text=t, variable=self._b_dtype, value=v,
                command=self._on_dtype_change).pack(side='left', padx=3)
        row += 1

        # 通用子模式
        self._b_sub_frame = ttk.Frame(f)
        self._b_sub_frame.grid(row=row, column=0, columnspan=4, sticky='w', pady=(0, 2))
        ttk.Label(self._b_sub_frame, text="通用模式:").pack(side='left', padx=(0, 5))
        self._b_sub_mode = tk.StringVar(value="classify")
        for t, v in [("分类栅格", "classify"), ("单波段连续", "single"), ("多波段连续", "multi")]:
            ttk.Radiobutton(self._b_sub_frame, text=t, variable=self._b_sub_mode, value=v,
                command=self._on_sub_mode_change).pack(side='left', padx=3)
        row += 1

        ttk.Label(f, text="提取预设:").grid(row=row, column=0, sticky='w', pady=2)
        self._b_preset = tk.StringVar(value="lu_default")
        self._b_preset_combo = ttk.Combobox(f, textvariable=self._b_preset,
            values=list_presets('landscape'), width=22, state='readonly')
        self._b_preset_combo.grid(row=row, column=1, sticky='w')
        self._b_preset_combo.bind('<<ComboboxSelected>>', lambda e: self._auto_gen_fields())
        row += 1

        # TIF 目录
        ttk.Label(f, text="TIF 目录:").grid(row=row, column=0, sticky='w', pady=2)
        self._b_tif_dir = tk.StringVar()
        ttk.Entry(f, textvariable=self._b_tif_dir, width=55).grid(row=row, column=1, pady=2, sticky='w')
        ttk.Button(f, text="浏览", command=lambda: self._pick_dir(self._b_tif_dir)).grid(row=row, column=2, sticky='w')
        ttk.Button(f, text="扫描 TIF", command=self._scan_tifs).grid(row=row, column=3, sticky='w')
        row += 1

        # 当前矢量标签
        self._b_active_vec_label = ttk.Label(f, text="当前矢量: 全部")
        self._b_active_vec_label.grid(row=row, column=0, sticky='nw', pady=2)

        # TIF 列表 Treeview (勾选/文件名/尺度/输出名/全路径)
        tf = ttk.Frame(f)
        tf.grid(row=row, column=1, columnspan=3, sticky='nsew', pady=2)
        cols = ('check', 'path', 'scale', 'out_name', 'fullpath')
        self._b_tif_tree = ttk.Treeview(tf, columns=cols, show='headings', height=6,
            displaycolumns=('check', 'path', 'scale', 'out_name'))
        self._b_tif_tree.heading('check', text='✓'); self._b_tif_tree.column('check', width=30, anchor='center')
        self._b_tif_tree.heading('path', text='文件名'); self._b_tif_tree.column('path', width=260)
        self._b_tif_tree.heading('scale', text='尺度'); self._b_tif_tree.column('scale', width=80, anchor='center')
        self._b_tif_tree.heading('out_name', text='输出名称'); self._b_tif_tree.column('out_name', width=180)
        self._b_tif_tree.pack(side='left', fill='both', expand=True)
        tsb = ttk.Scrollbar(tf, orient='vertical', command=self._b_tif_tree.yview)
        tsb.pack(side='right', fill='y'); self._b_tif_tree.configure(yscrollcommand=tsb.set)
        self._b_tif_tree.bind('<ButtonRelease-1>', self._toggle_tif_check)

        # TIF 右侧按钮
        btns2 = ttk.Frame(tf); btns2.pack(side='right', padx=3, fill='y')
        sf = ttk.Frame(btns2); sf.pack(pady=1, fill='x')
        ttk.Label(sf, text="尺度:").pack(side='left')
        self._b_scale_combo = ttk.Combobox(sf, width=8, state='readonly')
        self._b_scale_combo.pack(side='left', padx=2)
        ttk.Button(sf, text="选", command=self._on_scale_check).pack(side='left')
        ttk.Separator(btns2, orient='horizontal').pack(fill='x', pady=3)
        ttk.Button(btns2, text="全选", command=lambda: self._set_all_checks(True)).pack(pady=1)
        ttk.Button(btns2, text="取消全选", command=lambda: self._set_all_checks(False)).pack(pady=1)
        ttk.Button(btns2, text="生成名称", command=self._auto_out_names).pack(pady=1)
        ttk.Button(btns2, text="编辑选中", command=self._edit_tif_row).pack(pady=1)
        ttk.Button(btns2, text="+ 添加TIF", command=self._add_tif_files).pack(pady=1)
        ttk.Button(btns2, text="- 移除", command=self._remove_tif_row).pack(pady=1)
        row += 1

        # 字段配置
        ttk.Label(f, text="字段配置:").grid(row=row, column=0, sticky='nw', pady=2)
        ff = ttk.Frame(f); ff.grid(row=row, column=1, columnspan=3, sticky='w')
        self._b_n_bands = tk.StringVar(value="1")
        ttk.Label(ff, text="波段数:").pack(side='left')
        ttk.Entry(ff, textvariable=self._b_n_bands, width=3).pack(side='left', padx=2)
        self._b_prefix_lbl = ttk.Label(ff, text=" 前缀:")
        self._b_prefix = tk.StringVar(value="")
        ttk.Entry(ff, textvariable=self._b_prefix, width=8)
        ttk.Button(ff, text="自动生成字段名", command=self._auto_gen_fields).pack(side='left', padx=10)
        self._b_field_text = scrolledtext.ScrolledText(ff, width=55, height=4)
        self._b_field_text.pack(side='left', padx=5, fill='x', expand=True)
        row += 1

        # 输出 + 按钮
        ttk.Label(f, text="输出前缀:").grid(row=row, column=0, sticky='w', pady=2)
        self._b_out = tk.StringVar(value="extracted")
        ttk.Entry(f, textvariable=self._b_out, width=25).grid(row=row, column=1, sticky='w', pady=2)
        self._b_overwrite = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="覆盖已有", variable=self._b_overwrite).grid(row=row, column=2, sticky='w')
        self._b_update = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="更新已有字段", variable=self._b_update).grid(row=row, column=3, sticky='w')
        row += 1

        bf2 = ttk.Frame(f)
        bf2.grid(row=row, column=1, columnspan=3, sticky='w', pady=10)
        ttk.Button(bf2, text="▶ 执行提取", command=self._run_batch).pack(side='left', padx=2)
        ttk.Button(bf2, text="■ 终止", command=self._on_stop).pack(side='left', padx=2)
        ttk.Button(bf2, text="💾 保存日志", command=self._save_log).pack(side='left', padx=2)

        f.columnconfigure(1, weight=1)
        self._b_tif_states = {}  # {vec_path: [bool, ...]}
        self._active_target = None
        self._on_dtype_change()

    # ━━ 矢量管理 ━━

    def _add_vector(self):
        p = filedialog.askopenfilename(title="选择矢量文件",
            filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
        if p and p not in self._b_targets:
            self._b_targets.append(p)
            self._b_target_listbox.insert('end', os.path.basename(p))
            n_tifs = len(self._b_tif_tree.get_children())
            self._b_tif_states[p] = [False] * n_tifs
            idx = len(self._b_targets) - 1
            self._b_target_listbox.selection_clear(0, 'end')
            self._b_target_listbox.selection_set(idx)
            self._on_vector_select()

    def _remove_vector(self):
        sel = self._b_target_listbox.curselection()
        if not sel: return
        idx = sel[0]
        removed = self._b_targets[idx]
        del self._b_targets[idx]
        self._b_target_listbox.delete(idx)
        if removed in self._b_tif_states:
            del self._b_tif_states[removed]
        self._active_target = None
        self._b_active_vec_label.config(text="当前矢量: 全部")
        self._refresh_tif_tree_for_target(None)

    def _on_vector_select(self, event=None):
        sel = self._b_target_listbox.curselection()
        if not sel:
            self._active_target = None
            self._b_active_vec_label.config(text="当前矢量: 全部")
        else:
            self._active_target = self._b_targets[sel[0]]
            self._b_active_vec_label.config(text=f"当前矢量: {os.path.basename(self._active_target)}")
        self._refresh_tif_tree_for_target(self._active_target)

    def _refresh_tif_tree_for_target(self, target):
        if target and target in self._b_tif_states:
            states = self._b_tif_states[target]
        elif self._b_targets and self._b_targets[0] in self._b_tif_states:
            states = self._b_tif_states[self._b_targets[0]]
        else:
            states = None

        for i, item in enumerate(self._b_tif_tree.get_children()):
            vals = list(self._b_tif_tree.item(item, 'values'))
            if states and i < len(states):
                vals[0] = '☑' if states[i] else '☐'
            else:
                vals[0] = '☐'
            self._b_tif_tree.item(item, values=vals)

    def _get_active_key(self):
        if self._active_target and self._active_target in self._b_tif_states:
            return self._active_target
        if self._b_targets:
            t = self._b_targets[0]
            n = len(self._b_tif_tree.get_children())
            if t not in self._b_tif_states:
                self._b_tif_states[t] = [False] * n
            return t
        return None

    # ━━ 数据类型 ━━

    def _on_dtype_change(self):
        dtype = self._b_dtype.get()
        if dtype == 'landscape':
            vals = list_presets('landscape')
        elif dtype == 'parent_material':
            vals = list_presets('parent_material')
        else:
            vals = list_presets()
        self._b_preset_combo['values'] = vals
        if vals:
            self._b_preset.set(vals[0])

        is_generic = (dtype == 'generic')
        for w in self._b_sub_frame.winfo_children():
            try:
                w.configure(state='!disabled' if is_generic else 'disabled')
            except tk.TclError:
                pass
        if not is_generic:
            self._b_sub_mode.set('classify')
        self._on_sub_mode_change()

    def _on_sub_mode_change(self, _=None):
        dtype = self._b_dtype.get()
        sm = self._b_sub_mode.get()

        for w in (self._b_prefix_lbl, self._b_prefix):
            try: w.pack_forget()
            except: pass

        is_generic = (dtype == 'generic')
        if is_generic and sm == 'multi':
            self._b_prefix.pack(side='left', padx=2)
            self._b_prefix_lbl.pack(side='left')

        self._b_n_bands_entry = self._b_n_bands_entry if hasattr(self, '_b_n_bands_entry') else None
        self._auto_gen_fields()

    def _auto_gen_fields(self):
        dtype = self._b_dtype.get()
        pname = self._b_preset.get()
        preset = load_preset(pname)
        sm = self._b_sub_mode.get()
        self._b_field_text.config(state='normal')
        self._b_field_text.delete('1.0', 'end')

        if dtype == 'landscape':
            metrics = preset.get('default_metrics', ['PLAND', 'PD', 'LPI', 'AREA_MN', 'FRAC_MN'])
            full_names = generate_feature_names(preset, metrics=metrics)
            self._b_field_text.insert('1.0', f"# 景观字段: {len(full_names)} 个\n{chr(10).join(full_names)}")
        elif dtype == 'parent_material':
            mz = preset.get('mz_bands', {})
            nb = len(mz); self._b_n_bands.set(str(nb))
            lines = [f"# 母质字段: {nb} 波段"]
            for i in sorted(mz.keys(), key=int):
                lines.append(mz[str(i)])
            self._b_field_text.insert('1.0', '\n'.join(lines))
        elif sm == 'classify':
            nb = int(self._b_n_bands.get() or '1')
            self._b_field_text.insert('1.0', f"# 分类栅格: 请输入 {nb} 个字段名")
        elif sm == 'single':
            tif_count = len(self._b_tif_tree.get_children())
            self._b_n_bands.set('1')
            self._b_field_text.insert('1.0', f"# 单波段连续: 请输入 {tif_count} 个字段名")
        else:
            nb = int(self._b_n_bands.get() or '1')
            pfx = self._b_prefix.get().strip() or 'B'
            lines = [f"# 多波段连续: {nb} 波段, 前缀={pfx}"]
            for b in range(1, nb + 1):
                lines.append(f"{pfx}_B{b}")
            self._b_field_text.insert('1.0', '\n'.join(lines))

    # ━━ TIF 列表 ━━

    def _scan_tifs(self):
        d = self._b_tif_dir.get().strip()
        if not d or not os.path.isdir(d): return

        # 收集所有 .tif
        tifs = []
        for f in sorted(glob.glob(os.path.join(d, '*.tif'))):
            tifs.append(f)
        for rd, dirs, files in os.walk(d):
            for f in sorted(files):
                if f.endswith('.tif') and os.path.join(rd, f) not in tifs:
                    tifs.append(os.path.join(rd, f))

        # 保留手动添加的 TIF
        manual = []
        for item in self._b_tif_tree.get_children():
            vals = list(self._b_tif_tree.item(item, 'values'))
            fp = vals[4] if len(vals) > 4 else ''
            if fp and os.path.isfile(fp) and os.path.commonpath([os.path.abspath(fp), os.path.abspath(d)]) != os.path.abspath(d):
                manual.append(vals)

        self._b_tif_tree.delete(*self._b_tif_tree.get_children())
        scales_seen = set()
        for tf in tifs:
            base = os.path.basename(tf)
            scale = '-'
            pw = ProcessingWindow.from_filename(base)
            if pw:
                scale = pw.label
                scales_seen.add(scale)
            pfx = self._b_out.get().strip() or 'extracted'
            oname = f'{pfx}_{scale}' if scale != '-' else pfx
            self._b_tif_tree.insert('', 'end', values=('☐', base, scale, oname, tf))

        for vals in manual:
            self._b_tif_tree.insert('', 'end', values=vals)

        sorted_scales = sorted(scales_seen, key=lambda s: int(s.split('x')[0]) if 'x' in s else 0)
        self._b_scale_combo['values'] = sorted_scales
        if sorted_scales:
            self._b_scale_combo.set(sorted_scales[0])

        n_tifs = len(self._b_tif_tree.get_children())
        for t in self._b_targets:
            self._b_tif_states[t] = [False] * n_tifs
        self._refresh_tif_tree_for_target(self._active_target)
        self.log.log(f"TIF 扫描: {len(tifs)} 个文件, 尺度: {sorted_scales}")

    def _add_tif_files(self):
        paths = filedialog.askopenfilenames(title="选择TIF文件",
            filetypes=[("GeoTIFF", "*.tif"), ("All", "*.*")])
        if not paths: return
        for p in paths:
            base = os.path.basename(p)
            scale = '-'
            pw = ProcessingWindow.from_filename(base)
            if pw: scale = pw.label
            pfx = self._b_out.get().strip() or 'extracted'
            oname = f'{pfx}_{scale}' if scale != '-' else pfx
            self._b_tif_tree.insert('', 'end', values=('☐', base, scale, oname, p))

        n_tifs = len(self._b_tif_tree.get_children())
        for t in self._b_targets:
            if t in self._b_tif_states:
                self._b_tif_states[t].extend([False] * (n_tifs - len(self._b_tif_states[t])))
            else:
                self._b_tif_states[t] = [False] * n_tifs

    def _toggle_tif_check(self, event):
        region = self._b_tif_tree.identify_region(event.x, event.y)
        if region == 'cell' and self._b_tif_tree.identify_column(event.x) == '#1':
            item = self._b_tif_tree.identify_row(event.y)
            if item:
                vals = list(self._b_tif_tree.item(item, 'values'))
                vals[0] = '☑' if vals[0] == '☐' else '☐'
                self._b_tif_tree.item(item, values=vals)
                target = self._get_active_key()
                if target:
                    idx = self._b_tif_tree.index(item)
                    if idx < len(self._b_tif_states.get(target, [])):
                        self._b_tif_states[target][idx] = (vals[0] == '☑')

    def _set_all_checks(self, checked):
        target = self._get_active_key()
        for i, item in enumerate(self._b_tif_tree.get_children()):
            vals = list(self._b_tif_tree.item(item, 'values'))
            vals[0] = '☑' if checked else '☐'
            self._b_tif_tree.item(item, values=vals)
            if target and i < len(self._b_tif_states.get(target, [])):
                self._b_tif_states[target][i] = checked

    def _on_scale_check(self):
        sel_scale = self._b_scale_combo.get()
        if not sel_scale: return
        target = self._get_active_key()
        if not target: return
        for i, item in enumerate(self._b_tif_tree.get_children()):
            vals = list(self._b_tif_tree.item(item, 'values'))
            if vals[2] == sel_scale:
                vals[0] = '☑'
                if target in self._b_tif_states and i < len(self._b_tif_states[target]):
                    self._b_tif_states[target][i] = True
            self._b_tif_tree.item(item, values=vals)

    def _auto_out_names(self):
        pfx = self._b_out.get().strip() or 'extracted'
        for item in self._b_tif_tree.get_children():
            vals = list(self._b_tif_tree.item(item, 'values'))
            scale = vals[2]
            vals[3] = f'{pfx}_{scale}' if scale != '-' else pfx
            self._b_tif_tree.item(item, values=vals)

    def _edit_tif_row(self):
        sel = self._b_tif_tree.selection()
        if not sel: return
        item = sel[0]; vals = list(self._b_tif_tree.item(item, 'values'))
        dlg = EditRasterDialog(self.winfo_toplevel(),
            path=vals[4] if len(vals)>4 else vals[0],
            band=1,
            field_name=vals[3])
        res = dlg.wait_result()
        if res:
            p, b, n = res
            vals[0] = '☐' if vals[0] == '☐' else vals[0]
            vals[1] = os.path.basename(p)
            vals[3] = n
            if len(vals) > 4: vals[4] = p
            self._b_tif_tree.item(item, values=vals)

    def _remove_tif_row(self):
        sel_items = list(self._b_tif_tree.selection())
        if not sel_items: return
        indices = sorted([self._b_tif_tree.index(it) for it in sel_items], reverse=True)
        for idx in indices:
            self._b_tif_tree.delete(self._b_tif_tree.get_children()[idx])
            for t in self._b_tif_states:
                if idx < len(self._b_tif_states[t]):
                    self._b_tif_states[t].pop(idx)

    # ━━ 公用 ━━

    def _pick_dir(self, var):
        p = filedialog.askdirectory(title="选择目录")
        if p: var.set(p)

    # ━━ 批量执行 ━━

    def _run_batch(self):
        out = self.app_state.config.out_dir if self.app_state.config else ''
        if not out:
            messagebox.showwarning("配置", "请先设置输出目录"); return
        if not self._b_targets:
            messagebox.showwarning("配置", "请添加至少一个矢量文件"); return

        dtype = self._b_dtype.get()
        sm = self._b_sub_mode.get()
        lines = [l.strip() for l in self._b_field_text.get('1.0', 'end').split('\n')
                 if l.strip() and not l.startswith('#')]

        if dtype == 'parent_material':
            p = load_preset(self._b_preset.get())
            mz = p.get('mz_bands', {})
            if mz:
                lines = [mz[str(i)] for i in sorted(mz.keys(), key=int)]

        ow = self._b_overwrite.get()
        up = self._b_update.get()
        tif_dir = self._b_tif_dir.get().strip()

        all_tif_info = []
        for item in self._b_tif_tree.get_children():
            vals = list(self._b_tif_tree.item(item, 'values'))
            all_tif_info.append((vals[1], vals[2], vals[3], vals[4] if len(vals) > 4 else ''))

        def _resolve(fname, fp):
            if fp and os.path.isfile(fp): return fp
            tf = os.path.join(tif_dir, fname)
            if os.path.isfile(tf): return tf
            for rd, ds, fs in os.walk(tif_dir):
                if fname in fs: return os.path.join(rd, fname)
            return None

        tasks = []
        for target_path in self._b_targets:
            tif_states = self._b_tif_states.get(target_path, [False] * len(all_tif_info))
            tbase = os.path.basename(target_path)
            target_scale = None
            pw = ProcessingWindow.from_filename(tbase)
            if pw: target_scale = pw.label

            for i, (fname, scale, oname, fp) in enumerate(all_tif_info):
                if i >= len(tif_states) or not tif_states[i]:
                    continue
                if target_scale and scale != '-' and target_scale != scale:
                    continue

                tf = _resolve(fname, fp)
                if not tf:
                    self.log.log(f"[WARN] 未找到: {fname}", 'warn'); continue

                vec_name = os.path.splitext(tbase)[0]
                out_dir = os.path.join(out, 'Vector', f'{oname}_{vec_name}')
                out_path = os.path.join(out_dir, f'{oname}_{vec_name}.shp')
                if os.path.exists(out_path) and not ow and not up:
                    self.log.log(f"[SKIP] {out_path}"); continue

                rasters = []
                if dtype == 'landscape':
                    fn = lines[i] if i < len(lines) else os.path.splitext(fname)[0].replace('.', '_')[:10]
                    rasters.append({'path': tf, 'band': 1, 'field_name': fn, 'name': fname})
                elif dtype == 'parent_material':
                    if not lines: continue
                    for b in range(1, len(lines) + 1):
                        rasters.append({'path': tf, 'band': b, 'field_name': lines[b-1], 'name': f'{fname}_B{b}'})
                elif sm == 'classify':
                    if not lines: continue
                    for b in range(1, len(lines) + 1):
                        rasters.append({'path': tf, 'band': b, 'field_name': lines[b-1], 'name': f'{fname}_B{b}'})
                elif sm == 'single':
                    fn = lines[i] if i < len(lines) else f'Field{i+1}'
                    rasters.append({'path': tf, 'band': 1, 'field_name': fn, 'name': fname})
                else:
                    if not lines: continue
                    for b in range(1, len(lines) + 1):
                        rasters.append({'path': tf, 'band': b, 'field_name': lines[b-1], 'name': f'{fname}_B{b}'})

                os.makedirs(out_dir, exist_ok=True)
                tasks.append((target_path, f'{oname}_{vec_name}', out_path, rasters))

        if not tasks:
            self.log.log("无可用提取任务", 'warn'); return

        self.app_state.reset_cancel()

        def _batch_task(stop_event=None, progress_cb=None):
            from datetime import datetime
            from app.core.processors import RasterSampler
            self.log.log(f"\n{'='*50}")
            self.log.log(f"批量提取开始 ({len(tasks)} 个任务)  {datetime.now().strftime('%H:%M:%S')}")
            for ti, (tgt, label, out_p, rasters) in enumerate(tasks):
                if stop_event and stop_event.is_set():
                    self.log.log("⚠ 用户终止", 'warn'); break
                try:
                    params = {'target': tgt, 'rasters': rasters, 'method': '直接提取像元值', 'output': out_p}
                    if up and os.path.exists(out_p):
                        params['update_existing'] = True
                    proc = RasterSampler(params, log_func=self.log.log, stop_event=stop_event)
                    result = proc.run()
                    if result:
                        self.log.log(f"✓ {label} → {result}")
                except Exception as e:
                    import traceback
                    self.log.log(f"✗ {label}: {e}", 'error')
                    self.log.log(traceback.format_exc())
            self.log.log("批量提取完成")

        worker = TaskWorker(_batch_task,
            on_error=lambda e: self.log.log(f"✗ {e}", 'error'))
        worker.set_stop_event(self.app_state.stop_event)
        worker.start()

    def _on_stop(self):
        self.app_state.cancel_all()
        self.log.log("⚠ 已终止", 'warn')

    def _save_log(self):
        out = self.app_state.config.out_dir if self.app_state.config else ''
        if not out:
            messagebox.showwarning("提示", "请先设置输出目录"); return
        log_dir = os.path.join(out, 'log')
        os.makedirs(log_dir, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(log_dir, f'Output_Log_{ts}.txt')
        if self.app_state.log_manager:
            self.app_state.log_manager.save_to_file(log_path)
        self.log.log(f"日志已保存: {log_path}")
        messagebox.showinfo("提示", f"日志已保存至:\n{log_path}")

    # ── 状态读写 ──

    def get_state(self):
        return {
            'single_target': self._s_target_var.get(),
            'single_out': self._s_out.get(),
            'single_overwrite': self._s_overwrite.get(),
            'single_rasters': self._s_raster_list.get_rasters(),
            'batch_targets': self._b_targets,
            'batch_dtype': self._b_dtype.get(),
            'batch_preset': self._b_preset.get(),
            'batch_tif_dir': self._b_tif_dir.get(),
            'batch_out': self._b_out.get(),
            'batch_tif_states': {k: list(v) for k, v in self._b_tif_states.items()},
        }

    def set_state(self, state):
        if not state: return
        self._s_target_var.set(state.get('single_target', ''))
        self._s_out.set(state.get('single_out', 'sample_extracted.shp'))
        self._s_overwrite.set(state.get('single_overwrite', False))
        self._b_dtype.set(state.get('batch_dtype', 'landscape'))
        self._b_preset.set(state.get('batch_preset', 'lu_default'))
        self._b_tif_dir.set(state.get('batch_tif_dir', ''))
        self._b_out.set(state.get('batch_out', 'extracted'))
        # 恢复分矢量 TIF 勾选状态
        saved_states = state.get('batch_tif_states', {})
        if saved_states:
            self._b_tif_states = {k: list(v) for k, v in saved_states.items()}
