# -*- coding: utf-8 -*-
"""
preset_editor.py — 预设编辑弹窗
=================================
从原 datasets_gui.py 的 _new_preset() 和 _edit_class_map() 合并抽取。
支持新建和编辑两种模式。

校验规则 (严格对齐原逻辑):
  - 预设名称不能为空
  - 分类映射每行格式: 编码: 类别名 (支持冒号前后空格)
  - 排除值必须都是数字
  - 至少勾选一个指数

返回值格式与 landscape_config 完全一致:
    {"name": str, "description": str, "classes": {str: str},
     "exclude_values": [int,...], "default_metrics": [str,...]}

注意: 不直接调用 save_preset, 只返回数据, 保存由调用方决定。
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox


class PresetEditorDialog(tk.Toplevel):
    """预设编辑弹窗 (新建/编辑).

    Usage:
        # 新建
        dlg = PresetEditorDialog(root, mode='new')
        name, data = dlg.wait_result()

        # 编辑
        dlg = PresetEditorDialog(root, mode='edit', preset_name='lu_default',
                                 preset_data=existing_data)
        name, data = dlg.wait_result()
    """

    # 默认可用指标
    AVAILABLE_METRICS = ['PLAND', 'PD', 'LPI', 'AREA_MN', 'FRAC_MN']

    def __init__(self, master, mode='new', preset_name=None, preset_data=None):
        """
        Args:
            master:      父窗口
            mode:        'new' | 'edit'
            preset_name: 编辑模式下的预设名 (新建为 None)
            preset_data: 编辑模式下的预设数据字典 (新建为 None)
        """
        super().__init__(master)
        self._mode = mode
        self._result = None
        self._preset_data = preset_data or {}

        if mode == 'new':
            self.title("新建分类映射预设")
            self.geometry("500x530")
        else:
            self.title(f"编辑分类映射 — {preset_name or ''}")
            self.geometry("500x550")

        self.transient(master)
        self.grab_set()

        self._center_on_parent(master)
        self._build_ui(preset_name)

        self.bind('<Return>', lambda e: self._on_save())
        self.bind('<Escape>', lambda e: self.destroy())

    def _center_on_parent(self, master):
        self.update_idletasks()
        w, h = 500, 530
        if master and master.winfo_toplevel() == master:
            x = master.winfo_rootx() + (master.winfo_width() - w) // 2
            y = master.winfo_rooty() + (master.winfo_height() - h) // 2
        else:
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _build_ui(self, preset_name):
        """构建 UI."""
        # ── 预设名称 ──
        ttk.Label(self, text="预设名称:").pack(pady=(10, 0))
        self._name_var = tk.StringVar(value=preset_name or '')
        name_entry = ttk.Entry(self, textvariable=self._name_var, width=30)
        name_entry.pack(pady=2)
        if self._mode == 'edit':
            name_entry.configure(state='readonly')

        # ── 分类映射 ──
        ttk.Label(self, text="分类映射 (编码: 类别名称, 一行一个):").pack(pady=(10, 0))
        self._class_text = scrolledtext.ScrolledText(self, width=50, height=12)
        self._class_text.pack(padx=10, pady=5, fill='both', expand=True)

        # 填充已有数据
        if self._mode == 'edit' and self._preset_data:
            classes = self._preset_data.get('classes', {})
            lines = []
            for k, v in sorted(classes.items(), key=lambda x: int(x[0])):
                lines.append(f"{k}: {v}")
            self._class_text.insert('1.0', '\n'.join(lines))
        else:
            # 默认模板
            self._class_text.insert('1.0',
                "1: Farmland\n2: Orchard\n3: Forest\n4: Grassland\n"
                "5: Residential\n6: Road\n7: Commercial\n8: Construction\n9: Water")

        # ── 排除值 ──
        ttk.Label(self, text="排除值 (逗号分隔):").pack()
        excl_default = '0,255'
        if self._mode == 'edit':
            excl_vals = self._preset_data.get('exclude_values', [0])
            excl_default = ','.join(str(x) for x in excl_vals)
        self._excl_var = tk.StringVar(value=excl_default)
        ttk.Entry(self, textvariable=self._excl_var, width=25).pack(pady=2)

        # ── 默认指数 ──
        ttk.Label(self, text="默认指数:").pack(pady=(5, 0))
        mf = ttk.Frame(self)
        mf.pack(pady=2)
        self._metric_vars = {}
        default_metrics = self._preset_data.get('default_metrics', self.AVAILABLE_METRICS) if self._mode == 'edit' else self.AVAILABLE_METRICS
        for m in self.AVAILABLE_METRICS:
            v = tk.BooleanVar(value=(m in default_metrics))
            ttk.Checkbutton(mf, text=m, variable=v).pack(side='left', padx=4)
            self._metric_vars[m] = v

        # ── 按钮 ──
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="保存", command=self._on_save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side='left', padx=5)

    def _on_save(self):
        """保存: 校验 + 组装数据返回."""
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("校验", "请输入预设名称", parent=self)
            return

        # 解析分类映射
        classes = {}
        raw_lines = self._class_text.get('1.0', 'end').strip().split('\n')
        for line in raw_lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            k, v = line.split(':', 1)
            k = k.strip()
            v = v.strip()
            if not k or not v:
                continue
            # 编码必须是整数
            try:
                int(k)
            except ValueError:
                messagebox.showwarning("校验",
                    f"分类编码必须是整数: '{k}'", parent=self)
                return
            classes[k] = v

        if not classes:
            messagebox.showwarning("校验", "请至少添加一个分类映射", parent=self)
            return

        # 解析排除值
        excl_strs = [x.strip() for x in self._excl_var.get().split(',') if x.strip()]
        exclude_vals = []
        for s in excl_strs:
            try:
                exclude_vals.append(int(s))
            except ValueError:
                messagebox.showwarning("校验",
                    f"排除值必须是数字: '{s}'", parent=self)
                return

        # 收集勾选的指数
        metrics = [m for m, v in self._metric_vars.items() if v.get()]
        if not metrics:
            messagebox.showwarning("校验", "请至少勾选一个默认指数", parent=self)
            return

        # 组装数据 (格式与 landscape_config 完全一致)
        data = {
            'name': name,
            'description': self._preset_data.get('description', ''),
            'classes': classes,
            'exclude_values': exclude_vals,
            'default_metrics': metrics,
        }

        # 编辑模式保留其他字段 (如 mz_bands 等)
        for key in self._preset_data:
            if key not in data:
                data[key] = self._preset_data[key]

        self._result = (name, data)
        self.destroy()

    def get_result(self):
        return self._result

    def wait_result(self):
        self.wait_window()
        return self._result
