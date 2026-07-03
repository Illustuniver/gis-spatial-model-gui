# -*- coding: utf-8 -*-
"""
add_field.py — 添加字段弹窗【新增】
====================================
用于在属性表中添加新字段。
校验: 字段名非空、不重名、类型与默认值匹配、SHP 10 字符警告。
"""

import tkinter as tk
from tkinter import ttk, messagebox


class AddFieldDialog(tk.Toplevel):
    """添加属性表字段弹窗.

    Usage:
        dlg = AddFieldDialog(root, existing_fields=['ID', 'name'])
        result = dlg.wait_result()  # => (field_name, field_type, default_value) 或 None
    """

    # SHP 字段名限制
    SHP_FIELD_MAX_LEN = 10

    def __init__(self, master, existing_fields=None):
        """
        Args:
            master:          父窗口
            existing_fields: 已有字段名列表，用于重名校验
        """
        super().__init__(master)
        self.title("添加字段")
        self.geometry("350x210")
        self.transient(master)
        self.grab_set()
        self._result = None
        self._existing = set(existing_fields or [])

        self._center_on_parent(master)

        # ── UI ──
        ttk.Label(self, text="字段名:").pack(pady=(10, 0))
        self._name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._name_var, width=30).pack(padx=10)

        ttk.Label(self, text="字段类型:").pack(pady=(8, 0))
        self._type_var = tk.StringVar(value="float")
        ttk.Combobox(self, textvariable=self._type_var,
                     values=["float", "int", "str"], state='readonly', width=12).pack()

        ttk.Label(self, text="默认值 (可选):").pack(pady=(8, 0))
        self._default_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._default_var, width=30).pack(padx=10)

        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side='left', padx=5)

        self.bind('<Return>', lambda e: self._on_ok())
        self.bind('<Escape>', lambda e: self.destroy())

    def _center_on_parent(self, master):
        self.update_idletasks()
        if master and master.winfo_toplevel() == master:
            x = master.winfo_rootx() + (master.winfo_width() - 350) // 2
            y = master.winfo_rooty() + (master.winfo_height() - 210) // 2
        else:
            x = (self.winfo_screenwidth() - 350) // 2
            y = (self.winfo_screenheight() - 210) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _on_ok(self):
        """确定: 三层校验."""
        name = self._name_var.get().strip()
        ftype = self._type_var.get()
        default_str = self._default_var.get().strip()

        # 1. 字段名非空
        if not name:
            messagebox.showwarning("校验", "字段名不能为空", parent=self)
            return

        # 2. 不重名
        if name in self._existing:
            messagebox.showwarning("校验",
                f"字段名 '{name}' 已存在, 请使用其他名称", parent=self)
            return

        # 3. SHP 长度警告 (不阻止)
        if len(name) > self.SHP_FIELD_MAX_LEN:
            ok = messagebox.askyesno("SHP 兼容性",
                f"字段名 '{name}' 超过 {self.SHP_FIELD_MAX_LEN} 字符.\n"
                f"SHP 格式保存时将被截断.\n\n是否继续?", parent=self)
            if not ok:
                return

        # 4. 类型与默认值匹配
        default_value = None
        if default_str:
            if ftype == 'int':
                try:
                    default_value = int(default_str)
                except ValueError:
                    messagebox.showwarning("校验",
                        f"默认值 '{default_str}' 不是合法整数", parent=self)
                    return
            elif ftype == 'float':
                try:
                    default_value = float(default_str)
                except ValueError:
                    messagebox.showwarning("校验",
                        f"默认值 '{default_str}' 不是合法数字", parent=self)
                    return
            else:
                default_value = default_str

        self._result = (name, ftype, default_value)
        self.destroy()

    def get_result(self):
        return self._result

    def wait_result(self):
        self.wait_window()
        return self._result
