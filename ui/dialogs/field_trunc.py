# -*- coding: utf-8 -*-
"""
field_trunc.py — 字段截断预览弹窗
==================================
从原 datasets_gui.py 的 _truncate_field_names() 抽取。
展示完整字段名 → 10 字符截断名（SHP 兼容）的映射。

截断规则 (严格对齐原逻辑):
  1. 取前 10 个字符
  2. 重名时截断到 8 字符 + _序号 (序号从 1 递增)
  3. 确保全局唯一
"""

import tkinter as tk
from tkinter import ttk, scrolledtext


class FieldTruncDialog(tk.Toplevel):
    """字段截断预览弹窗.

    Usage:
        names = ['Farmland_PLAND', 'Farmland_PD', 'Forest_PLAND']
        dlg = FieldTruncDialog(root, field_names=names)
        dlg.wait_result()  # 纯展示, 返回 None
    """

    def __init__(self, master, field_names=None):
        """
        Args:
            master:      父窗口
            field_names: 完整字段名列表 list[str]
        """
        super().__init__(master)
        self.title("10字符截断映射表")
        self.geometry("550x420")
        self.transient(master)
        self.grab_set()

        self._center_on_parent(master)
        self._build_ui(field_names or [])

        self.bind('<Escape>', lambda e: self.destroy())

    def _center_on_parent(self, master):
        self.update_idletasks()
        if master and master.winfo_toplevel() == master:
            x = master.winfo_rootx() + (master.winfo_width() - 550) // 2
            y = master.winfo_rooty() + (master.winfo_height() - 420) // 2
        else:
            x = (self.winfo_screenwidth() - 550) // 2
            y = (self.winfo_screenheight() - 420) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _build_ui(self, field_names):
        """构建 UI: 说明 + 文本框 + 关闭按钮."""
        ttk.Label(self, text="完整名 → 10字符截断名 (SHP兼容)").pack(pady=5)

        # 生成截断映射 (严格对齐原 _truncate_field_names 逻辑)
        trunc_map = {}
        seen = {}
        for fn in field_names:
            t = fn[:10]
            if t in seen:
                t = t[:8] + f"_{seen[t]}"
                seen[t] = seen.get(t, 0) + 1
            else:
                seen[t] = 1
            trunc_map[fn] = t

        # 格式化为文本
        lines = []
        for fn, t in trunc_map.items():
            lines.append(f"{fn:30s} → {t}")

        result = '\n'.join(lines)

        st = scrolledtext.ScrolledText(self, width=60, height=18)
        st.pack(padx=10, pady=5, fill='both', expand=True)
        st.insert('1.0', result)
        st.config(state='disabled')

        ttk.Button(self, text="关闭", command=self.destroy).pack(pady=8)

    def get_result(self):
        return None

    def wait_result(self):
        self.wait_window()
        return None
