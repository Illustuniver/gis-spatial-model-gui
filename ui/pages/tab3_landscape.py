# -*- coding: utf-8 -*-
"""
tab3_landscape.py — 景观格局指数页
====================================
从原 datasets_gui.py 的 _build_tab3() + _build_tab3_calc() 迁移。
功能: 移动窗口景观格局指数计算 (Fragstats 命令行)。
"""

import os, re, sys, subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

from app.ui.widgets.file_picker import FilePicker
from app.ui.dialogs.preset_editor import PresetEditorDialog
from app.ui.dialogs.field_trunc import FieldTruncDialog
from app.utils.thread_worker import TaskWorker
from app.config.presets import (
    load_preset, list_presets, save_preset, get_class_map, generate_feature_names
)


class LandscapePage(ttk.Frame):
    """景观格局指数计算页面."""

    def __init__(self, master, app_state, log_manager):
        super().__init__(master)
        self.app_state = app_state
        self.log = log_manager

        # 内部状态变量
        self.t3_raster = tk.StringVar()
        self.t3_nodata = tk.StringVar(value="")
        self.t3_preset = tk.StringVar(value="lu_default")
        self.t3_fca_dir = tk.StringVar()
        self.t3_frag = tk.StringVar()
        self.t3_prefix = tk.StringVar(value="Landscape_Rasters")
        self.t3_overwrite = tk.BooleanVar(value=False)
        self.t3_metrics = {}
        self.t3_available_wins = {}  # {display_str: (win_int, fca_path)}

        self._build_ui()
        self._update_class_display()
        self._refresh_win_list()

    def _build_ui(self):
        f = self
        row = 0

        # LU 分类栅格
        ttk.Label(f, text="LU 分类栅格:").grid(row=row, column=0, sticky='w', pady=2)
        self._raster_picker = FilePicker(f, label_text="", mode="file",
            filetypes=[("GeoTIFF", "*.tif"), ("All", "*.*")])
        self._raster_picker.grid(row=row, column=1, columnspan=2, sticky='we', pady=2)
        self._raster_picker.bind('<<FileSelected>>', self._on_raster_selected)

        # nodata
        ttk.Label(f, text="nodata 值:").grid(row=row, column=3, sticky='w', pady=2, padx=(10, 0))
        self.t3_nodata_entry = ttk.Entry(f, textvariable=self.t3_nodata, width=6)
        self.t3_nodata_entry.grid(row=row, column=4, sticky='w', pady=2)
        ttk.Label(f, text="(自动读取, 可手动覆盖)", foreground="gray").grid(row=row, column=5, sticky='w', pady=2)
        row += 1

        # 预设
        ttk.Label(f, text="分类映射预设:").grid(row=row, column=0, sticky='w', pady=2)
        bar = ttk.Frame(f)
        bar.grid(row=row, column=1, columnspan=2, sticky='w', pady=2)
        self.t3_preset_combo = ttk.Combobox(bar, textvariable=self.t3_preset,
            values=list_presets(), width=20, state='readonly')
        self.t3_preset_combo.pack(side='left')
        self.t3_preset_combo.bind('<<ComboboxSelected>>', lambda e: self._update_class_display())
        ttk.Button(bar, text="+ 新建", command=self._new_preset).pack(side='left', padx=2)
        ttk.Button(bar, text="编辑", command=self._edit_preset).pack(side='left', padx=2)
        ttk.Button(bar, text="删除", command=self._delete_preset).pack(side='left', padx=2)
        ttk.Button(bar, text="10字符截断", command=self._show_truncation).pack(side='left', padx=(20, 2))
        row += 1

        # 映射表
        ttk.Label(f, text="映射表 (编码 → 类名):").grid(row=row, column=0, sticky='nw', pady=2)
        self.t3_class_text = scrolledtext.ScrolledText(f, width=65, height=5, state='disabled')
        self.t3_class_text.grid(row=row, column=1, columnspan=2, pady=2, sticky='w')

        # 截断预览
        self.t3_trunc_label = ttk.Label(f, text="10字符截断: (暂无)", foreground="gray")
        self.t3_trunc_label.grid(row=row + 1, column=1, columnspan=2, sticky='w', pady=2)
        row += 2

        # FCA 目录
        ttk.Label(f, text="FCA 文件夹:").grid(row=row, column=0, sticky='w', pady=2)
        if self.app_state.config:
            self.t3_fca_dir.set(self.app_state.config.fca_dir)
        self.t3_fca_entry = ttk.Entry(f, textvariable=self.t3_fca_dir, width=65)
        self.t3_fca_entry.grid(row=row, column=1, pady=2)
        ttk.Button(f, text="浏览", command=self._pick_fca_dir).grid(row=row, column=2)
        row += 1

        # 窗口
        ttk.Label(f, text="可用窗口:").grid(row=row, column=0, sticky='nw', pady=2)
        wf = ttk.Frame(f)
        wf.grid(row=row, column=1, columnspan=2, sticky='w')
        self.t3_win_listbox = tk.Listbox(wf, selectmode='extended', height=5, width=25, exportselection=False)
        self.t3_win_listbox.pack(side='left', fill='y')
        ttk.Scrollbar(wf, orient='vertical', command=self.t3_win_listbox.yview).pack(side='right', fill='y')
        self.t3_win_listbox.configure(yscrollcommand=ttk.Scrollbar(wf).set)
        ttk.Button(wf, text="刷新", command=self._refresh_win_list).pack(side='left', padx=5)
        row += 1

        # 指数
        ttk.Label(f, text="景观指数:").grid(row=row, column=0, sticky='nw', pady=2)
        mf = ttk.Frame(f); mf.grid(row=row, column=1, columnspan=2, sticky='w')
        for m in ['PLAND', 'PD', 'LPI', 'AREA_MN', 'FRAC_MN']:
            v = tk.BooleanVar(value=True)
            ttk.Checkbutton(mf, text=m, variable=v).pack(side='left', padx=5)
            self.t3_metrics[m] = v
        ttk.Button(mf, text="全选", command=lambda: self._toggle_metrics(True)).pack(side='left', padx=(20, 2))
        ttk.Button(mf, text="全不选", command=lambda: self._toggle_metrics(False)).pack(side='left')
        row += 1

        # Fragstats
        ttk.Label(f, text="Fragstats 路径:").grid(row=row, column=0, sticky='w', pady=2)
        if self.app_state.config:
            self.t3_frag.set(self.app_state.config.fragstats_exe)
        self._frag_picker = FilePicker(f, label_text="", mode="file",
            filetypes=[("EXE", "*.exe"), ("All", "*.*")])
        self._frag_picker.grid(row=row, column=1, columnspan=2, sticky='we', pady=2)
        self._frag_picker.bind('<<FileSelected>>', lambda e: self.t3_frag.set(self._frag_picker.get_path()))
        if self.t3_frag.get():
            self._frag_picker.set_path(self.t3_frag.get())
        row += 1

        # 输出
        ttk.Label(f, text="输出子目录:").grid(row=row, column=0, sticky='w', pady=2)
        ttk.Entry(f, textvariable=self.t3_prefix, width=25).grid(row=row, column=1, sticky='w', pady=2)
        ttk.Label(f, text="(位于输出目录下)", foreground="gray").grid(row=row, column=2, sticky='w', padx=5)
        row += 1

        ttk.Checkbutton(f, text="覆盖已有栅格", variable=self.t3_overwrite).grid(row=row, column=1, sticky='w')
        row += 1

        # 按钮
        bf = ttk.Frame(f)
        bf.grid(row=row, column=1, columnspan=2, sticky='w', pady=5)
        ttk.Button(bf, text="▶ 执行", command=self._on_run).pack(side='left', padx=2)
        ttk.Button(bf, text="■ 终止", command=self._on_stop).pack(side='left', padx=2)
        ttk.Button(bf, text="💾 保存日志", command=self._save_log).pack(side='left', padx=2)

        f.columnconfigure(1, weight=1)

    # ── 事件处理 ──

    def _on_raster_selected(self, event=None):
        p = self._raster_picker.get_path()
        self.t3_raster.set(p)
        if p and os.path.exists(p):
            try:
                import rasterio
                with rasterio.open(p) as src:
                    nd = src.nodata
                    self.t3_nodata.set(str(nd) if nd is not None else "")
                    self.log.log(f"LU raster nodata={nd}, size={src.width}x{src.height}")
            except Exception as e:
                self.t3_nodata.set("")
                self.log.log(f"[WARN] 读取 nodata 失败: {e}", 'warn')

    def _update_class_display(self):
        preset_name = self.t3_preset.get()
        try:
            preset = load_preset(preset_name)
            class_map = get_class_map(preset)
            lines = [f"{k}: {v}" for k, v in sorted(class_map.items(), key=lambda x: int(x[0]))]
            self.t3_class_text.config(state='normal')
            self.t3_class_text.delete('1.0', 'end')
            self.t3_class_text.insert('1.0', '\n'.join(lines))
            self.t3_class_text.config(state='disabled')

            # 截断预览
            full_names = generate_feature_names(preset)
            truncated = {}
            seen = {}
            for fn in full_names:
                t = fn[:10]
                if t in seen:
                    t = t[:8] + f"_{seen[t]}"
                    seen[t] = seen.get(t, 0) + 1
                else:
                    seen[t] = 1
                truncated[fn] = t
            preview = ', '.join(list(truncated.values())[:8])
            if len(truncated) > 8:
                preview += f' ... ({len(truncated)} total)'
            self.t3_trunc_label.config(text=f"10字符截断: {preview}", foreground="gray")
        except Exception as e:
            self.t3_class_text.config(state='normal')
            self.t3_class_text.delete('1.0', 'end')
            self.t3_class_text.insert('1.0', f'(加载失败: {e})')
            self.t3_class_text.config(state='disabled')

    def _new_preset(self):
        dlg = PresetEditorDialog(self.winfo_toplevel(), mode='new')
        result = dlg.wait_result()
        if result:
            name, data = result
            save_preset(name, data)
            self._refresh_presets()
            self.t3_preset.set(name)
            self._update_class_display()
            self.log.log(f"预设已保存: {name}")

    def _edit_preset(self):
        name = self.t3_preset.get()
        preset = load_preset(name)
        dlg = PresetEditorDialog(self.winfo_toplevel(), mode='edit',
                                 preset_name=name, preset_data=preset)
        result = dlg.wait_result()
        if result:
            _, data = result
            save_preset(name, data)
            self._update_class_display()
            self.log.log(f"预设 {name} 已保存")

    def _delete_preset(self):
        name = self.t3_preset.get()
        if name == 'lu_default':
            messagebox.showwarning("提示", "不能删除默认预设")
            return
        if not messagebox.askyesno("确认", f"确定删除预设 '{name}'？"):
            return
        import json
        p = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'processing', 'presets', f'{name}.json')
        p = os.path.normpath(p)
        if os.path.exists(p):
            os.remove(p)
        self._refresh_presets()
        self._update_class_display()
        self.log.log(f"预设 '{name}' 已删除")

    def _refresh_presets(self):
        self.t3_preset_combo['values'] = list_presets()

    def _show_truncation(self):
        preset = load_preset(self.t3_preset.get())
        full_names = generate_feature_names(preset)
        if not full_names:
            return
        dlg = FieldTruncDialog(self.winfo_toplevel(), field_names=full_names)
        dlg.wait_result()

    def _toggle_metrics(self, val):
        for v in self.t3_metrics.values():
            v.set(val)

    def _pick_fca_dir(self):
        p = filedialog.askdirectory(title="选择 FCA 模板文件夹")
        if p:
            self.t3_fca_dir.set(p)
            if self.app_state.config:
                self.app_state.config.fca_dir = p
                self.app_state.config.save()
            self._refresh_win_list()

    def _refresh_win_list(self):
        d = self.t3_fca_dir.get().strip()
        self.t3_win_listbox.delete(0, 'end')
        self.t3_available_wins.clear()
        if not d or not os.path.isdir(d):
            return
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.fca'):
                continue
            m = re.match(r'frag_(\d+)x\1\.fca', fn)
            if m:
                win = int(m.group(1))
                label = f"{win}×{win}"
                self.t3_win_listbox.insert('end', label)
                self.t3_available_wins[label] = (win, os.path.join(d, fn))
        self.log.log(f"FCA 文件夹: 找到 {len(self.t3_available_wins)} 个窗口")

    # ── 执行 ──

    def _on_run(self):
        lu_raster = self.t3_raster.get().strip()
        if not lu_raster:
            p = filedialog.askopenfilename(title="选择 LU 分类栅格",
                filetypes=[("GeoTIFF", "*.tif"), ("All", "*.*")])
            if not p:
                return
            self.t3_raster.set(p)
            lu_raster = p

        out_dir = self.app_state.config.out_dir if self.app_state.config else ''
        if not out_dir:
            messagebox.showwarning("配置", "请先设置输出目录")
            return

        frag_exe = self.t3_frag.get().strip()
        if not frag_exe:
            messagebox.showwarning("配置", "请先设置 Fragstats 可执行文件路径")
            return

        selected = self.t3_win_listbox.curselection()
        if not selected:
            messagebox.showwarning("配置", "请先选择要运行的窗口尺寸")
            return

        windows, fca_map = [], {}
        for idx in selected:
            label = self.t3_win_listbox.get(idx)
            if label in self.t3_available_wins:
                w, p = self.t3_available_wins[label]
                windows.append(w)
                fca_map[w] = p

        metrics = [m for m, v in self.t3_metrics.items() if v.get()]
        if not metrics:
            messagebox.showwarning("配置", "请至少勾选一个景观指数")
            return

        nodata_str = self.t3_nodata.get().strip()
        nodata_override = int(nodata_str) if nodata_str and nodata_str.lstrip('-').isdigit() else None

        prefix = self.t3_prefix.get().strip() or 'Landscape_Rasters'
        landscape_out = os.path.join(out_dir, prefix)

        params = {
            'lu_raster': lu_raster,
            'class_preset': self.t3_preset.get(),
            'windows': windows,
            'metrics': metrics,
            'out_dir': landscape_out,
            'fragstats_exe': frag_exe,
            'nodata_override': nodata_override,
            'fca_map': fca_map,
        }

        def _task(stop_event=None, progress_cb=None):
            from app.core.processors import LandscapeProcessor
            proc = LandscapeProcessor(params, log_func=self.log.log, stop_event=stop_event)
            result = proc.run()
            if result:
                self.log.log(f"✓ 景观指数计算完成 → {result}")
            return result

        self.app_state.reset_cancel()
        worker = TaskWorker(_task,
            on_error=lambda e: self.log.log(f"✗ 错误: {e}", 'error'))
        worker.set_stop_event(self.app_state.stop_event)
        worker.start()

    def _on_stop(self):
        """终止 Fragstats: 设置 stop_event + 跨平台进程终止."""
        self.app_state.cancel_all()
        # 跨平台: win32→taskkill /T /PID, 否则→terminate
        # 先从 LandscapeProcessor 获取进程句柄 (如果还在运行)
        import subprocess as _sp
        if sys.platform == 'win32':
            _sp.run(['taskkill', '/F', '/IM', 'frg_cmd.exe'], capture_output=True)
            _sp.run(['taskkill', '/F', '/IM', 'frg_gui.exe'], capture_output=True)
        else:
            _sp.run(['pkill', '-f', 'frg_cmd'], capture_output=True)
            _sp.run(['pkill', '-f', 'frg_gui'], capture_output=True)
        self.log.log("⚠ 已终止", 'warn')

    def _save_log(self):
        out_dir = self.app_state.config.out_dir if self.app_state.config else ''
        if not out_dir:
            messagebox.showwarning("提示", "请先设置输出目录")
            return
        log_dir = os.path.join(out_dir, 'log')
        os.makedirs(log_dir, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(log_dir, f'Output_Log_{ts}.txt')
        # 从 LogManager 保存
        if self.app_state.log_manager:
            self.app_state.log_manager.save_to_file(log_path)
        self.log.log(f"日志已保存: {log_path}")
        messagebox.showinfo("提示", f"日志已保存至:\n{log_path}")

    # ── 状态读写 ──

    def get_state(self):
        selected_metrics = [m for m, v in self.t3_metrics.items() if v.get()]
        return {
            'lu_raster': self.t3_raster.get(),
            'nodata': self.t3_nodata.get(),
            'preset': self.t3_preset.get(),
            'fca_dir': self.t3_fca_dir.get(),
            'fragstats_exe': self.t3_frag.get(),
            'prefix': self.t3_prefix.get(),
            'overwrite': self.t3_overwrite.get(),
            'metrics': selected_metrics,
        }

    def set_state(self, state):
        if not state:
            return
        self.t3_raster.set(state.get('lu_raster', ''))
        self.t3_nodata.set(state.get('nodata', ''))
        self.t3_preset.set(state.get('preset', 'lu_default'))
        self.t3_fca_dir.set(state.get('fca_dir', ''))
        self.t3_frag.set(state.get('fragstats_exe', ''))
        self.t3_prefix.set(state.get('prefix', 'Landscape_Rasters'))
        self.t3_overwrite.set(state.get('overwrite', False))
        selected = state.get('metrics', [])
        for m, v in self.t3_metrics.items():
            v.set(m in selected)
        self._update_class_display()
        self._refresh_win_list()
