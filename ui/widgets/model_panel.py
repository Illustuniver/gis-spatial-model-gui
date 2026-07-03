# -*- coding: utf-8 -*-
"""
model_panel.py — 模型参数面板 (model.json 驱动自动生成)
===========================================================
根据 model.json 中的 params 规格自动生成输入控件:
  - int    → Spinbox (带 min/max/step)
  - float  → Scale/Slider (带 min/max/resolution)
  - str    → Entry / Combobox
  - bool   → Checkbutton

零硬编码模型逻辑，完全由 manifest 驱动。
"""

import tkinter as tk
from tkinter import ttk


class ModelParameterPanel(ttk.LabelFrame):
    """模型参数自动生成面板.

    Usage:
        panel = ModelParameterPanel(root, "Random Forest")
        panel.load_specs(model_loader.get_param_specs("Random Forest"))
        params = panel.get_params()  # → {'n_estimators': 100, ...}
    """

    WIDGET_BUILDERS = {}

    def __init__(self, master, model_name="", title="模型参数"):
        super().__init__(master, text=title, padding=5)
        self._model_name = model_name
        self._widgets = {}   # {param_name: tk.Variable}
        self._specs = []     # 原始参数规格

    def load_specs(self, param_specs):
        """从 model.json 加载参数规格，自动生成控件.

        Args:
            param_specs: list[dict] from model.json params 节.
        """
        # 清除旧控件
        for w in self.winfo_children():
            w.destroy()
        self._widgets.clear()
        self._specs = param_specs

        if not param_specs:
            ttk.Label(self, text="(无参数)", foreground="gray").pack(pady=5)
            return

        for i, spec in enumerate(param_specs):
            self._build_param_row(i, spec)

    def _build_param_row(self, row, spec):
        """根据规格构建一行参数控件."""
        name = spec['name']
        ptype = spec.get('type', 'str')
        label = spec.get('label', name)
        default = spec.get('default', self._type_default(ptype))

        # 标签
        lbl = ttk.Label(self, text=label, width=18, anchor='e')
        lbl.grid(row=row, column=0, sticky='e', padx=(5, 2), pady=2)

        # 控件
        if ptype == 'int':
            self._build_int(row, name, spec, default)
        elif ptype == 'float':
            self._build_float(row, name, spec, default)
        elif ptype == 'bool':
            self._build_bool(row, name, spec, default)
        else:
            self._build_string(row, name, spec, default)

        # 帮助文本
        help_text = spec.get('help', '')
        if help_text:
            help_lbl = ttk.Label(self, text="?", foreground="gray", font=("", 8))
            help_lbl.grid(row=row, column=2, padx=2)
            self._create_tooltip(help_lbl, help_text)

        # 滚动区
        if row > 8:
            self._make_scrollable()

    def _build_int(self, row, name, spec, default):
        var = tk.IntVar(value=int(default))
        spin = ttk.Spinbox(
            self, textvariable=var,
            from_=spec.get('min', 0),
            to=spec.get('max', 9999),
            increment=spec.get('step', 1),
            width=8,
        )
        spin.grid(row=row, column=1, sticky='w', pady=2)
        self._widgets[name] = var

    def _build_float(self, row, name, spec, default):
        var = tk.DoubleVar(value=float(default))
        min_val = spec.get('min', 0.0)
        max_val = spec.get('max', 1.0)

        # Scale + Entry 组合
        scale = ttk.Scale(
            self, variable=var, from_=min_val, to=max_val,
            orient='horizontal', length=120
        )
        scale.grid(row=row, column=1, sticky='w', pady=2)

        entry = ttk.Entry(self, textvariable=var, width=6)
        entry.grid(row=row, column=2, sticky='w', padx=2)

        self._widgets[name] = var

    def _build_bool(self, row, name, spec, default):
        var = tk.BooleanVar(value=bool(default))
        cb = ttk.Checkbutton(self, variable=var)
        cb.grid(row=row, column=1, sticky='w', pady=2)
        self._widgets[name] = var

    def _build_string(self, row, name, spec, default):
        var = tk.StringVar(value=str(default))
        choices = spec.get('choices', [])
        if choices:
            cb = ttk.Combobox(self, textvariable=var, values=choices,
                              state='readonly', width=15)
            cb.grid(row=row, column=1, sticky='w', pady=2)
        else:
            entry = ttk.Entry(self, textvariable=var, width=18)
            entry.grid(row=row, column=1, sticky='w', pady=2)
        self._widgets[name] = var

    def get_params(self):
        """获取当前参数值.

        Returns:
            dict: {param_name: value}.
        """
        result = {}
        for name, var in self._widgets.items():
            val = var.get()
            # int/float 类型保持
            result[name] = val
        return result

    def set_params(self, params):
        """设置参数值 (如从工程文件恢复).

        Args:
            params: {param_name: value}.
        """
        for name, var in self._widgets.items():
            if name in params:
                try:
                    var.set(params[name])
                except tk.TclError:
                    pass

    def reset_defaults(self):
        """重置为 model.json 中的默认值."""
        for spec in self._specs:
            name = spec['name']
            if name in self._widgets:
                try:
                    self._widgets[name].set(spec['default'])
                except tk.TclError:
                    pass

    def _type_default(self, ptype):
        defaults = {'int': 0, 'float': 0.0, 'bool': False, 'str': ''}
        return defaults.get(ptype, '')

    def _create_tooltip(self, widget, text):
        """简易 tooltip (鼠标悬停提示)."""
        def _enter(event):
            self._tip = tk.Toplevel(widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_geometry(f"+{event.x_root+15}+{event.y_root+10}")
            label = ttk.Label(self._tip, text=text, background="#ffffe0",
                              relief='solid', borderwidth=1, wraplength=250)
            label.pack()

        def _leave(event):
            if hasattr(self, '_tip'):
                self._tip.destroy()
                del self._tip

        widget.bind('<Enter>', _enter)
        widget.bind('<Leave>', _leave)

    def _make_scrollable(self):
        """参数过多时启用滚动 (预留)."""
        pass
