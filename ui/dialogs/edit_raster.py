# -*- coding: utf-8 -*-
"""
edit_raster.py — 编辑栅格条目弹窗
===================================
从原 datasets_gui.py 的 _edit_raster() 抽取。
编辑栅格条目的路径、波段号、字段名。
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class EditRasterDialog(tk.Toplevel):
    """编辑栅格条目弹窗.

    Usage:
        dlg = EditRasterDialog(root, path='dem.tif', band=1, field_name='dem_mean')
        result = dlg.wait_result()  # => (path, band, field_name) 或 None
    """

    def __init__(self, master, path='', band=1, field_name='', mode='file'):
        """
        Args:
            master:     父窗口
            path:       初始文件路径
            band:       初始波段号 (1-99)
            field_name: 初始字段名
            mode:       'file' 选文件 / 'dir' 选目录
        """
        super().__init__(master)
        self.title("编辑栅格条目")
        self.geometry("500x190")
        self.transient(master)
        self.grab_set()
        self._result = None
        self._mode = mode

        # 居中
        self._center_on_parent(master)

        # ── UI ──
        ttk.Label(self, text="文件/目录路径:").pack(pady=(10, 0))

        path_frame = ttk.Frame(self)
        path_frame.pack(fill='x', padx=10)
        self._path_var = tk.StringVar(value=path)
        ttk.Entry(path_frame, textvariable=self._path_var, width=52).pack(side='left', padx=(0, 2))
        ttk.Button(path_frame, text="浏览", command=self._browse).pack(side='left')

        ttk.Label(self, text="波段号:").pack()
        self._band_var = tk.IntVar(value=int(band))
        ttk.Spinbox(self, from_=1, to=99, textvariable=self._band_var, width=8).pack()

        ttk.Label(self, text="属性表字段名:").pack()
        self._name_var = tk.StringVar(value=field_name)
        ttk.Entry(self, textvariable=self._name_var, width=30).pack()

        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side='left', padx=5)

        # 快捷键
        self.bind('<Return>', lambda e: self._on_ok())
        self.bind('<Escape>', lambda e: self.destroy())

    def _center_on_parent(self, master):
        """在父窗口居中."""
        self.update_idletasks()
        if master and master.winfo_toplevel() == master:
            x = master.winfo_rootx() + (master.winfo_width() - 500) // 2
            y = master.winfo_rooty() + (master.winfo_height() - 190) // 2
        else:
            x = (self.winfo_screenwidth() - 500) // 2
            y = (self.winfo_screenheight() - 190) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _browse(self):
        """浏览文件/目录."""
        if self._mode == 'dir':
            p = filedialog.askdirectory(title="选择 .adf 目录")
        else:
            p = filedialog.askopenfilename(
                title="选择栅格文件",
                filetypes=[("Raster", "*.tif;*.img"), ("All", "*.*")])
        if p:
            self._path_var.set(p)

    def _on_ok(self):
        """确定: 校验 + 返回结果."""
        path = self._path_var.get().strip()
        band = self._band_var.get()
        name = self._name_var.get().strip()

        if not path:
            messagebox.showwarning("校验", "路径不能为空", parent=self)
            return
        if band < 1 or band > 99:
            messagebox.showwarning("校验", "波段号必须在 1-99 之间", parent=self)
            return
        if not name:
            messagebox.showwarning("校验", "字段名不能为空", parent=self)
            return

        self._result = (path, band, name)
        self.destroy()

    def get_result(self):
        """获取结果 (非阻塞)."""
        return self._result

    def wait_result(self):
        """模态等待，返回结果或 None."""
        self.wait_window()
        return self._result
