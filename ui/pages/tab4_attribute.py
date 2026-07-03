# -*- coding: utf-8 -*-
"""
tab4_attribute.py — 属性表管理页【新增核心功能】
==================================================
加载矢量 → 展示属性表 → 增删改字段 → 保存。

底层对接 AttributeManager，界面复用 AttributeTable 组件。
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from app.core.attribute_manager import AttributeManager
from app.core.data_preview import DataPreviewer
from app.ui.widgets.attribute_table import AttributeTable
from app.ui.widgets.log_panel import LogPanel
from app.ui.dialogs.add_field import AddFieldDialog


class AttributePage(ttk.Frame):
    """属性表管理页面."""

    def __init__(self, master, app_state, log_manager):
        super().__init__(master)
        self.app_state = app_state
        self.log = log_manager
        self._am = None          # AttributeManager 实例
        self._modified = False   # 未保存标记
        self._original_title = "属性表管理"

        self._build_ui()

    def _build_ui(self):
        """三栏布局: 顶部工具栏 | 左属性表 | 右侧信息面板."""
        # ── 顶部工具栏 ──
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', padx=5, pady=(5, 0))
        ttk.Button(toolbar, text="加载矢量", command=self._on_load).pack(side='left', padx=2)
        ttk.Button(toolbar, text="保存", command=self._on_save).pack(side='left', padx=2)
        ttk.Button(toolbar, text="另存为", command=self._on_save_as).pack(side='left', padx=2)
        ttk.Separator(toolbar, orient='vertical').pack(side='left', padx=5, fill='y')
        ttk.Button(toolbar, text="+ 添加字段", command=self._on_add_field).pack(side='left', padx=2)
        ttk.Button(toolbar, text="- 删除字段", command=self._on_delete_field).pack(side='left', padx=2)
        ttk.Button(toolbar, text="重命名", command=self._on_rename_field).pack(side='left', padx=2)
        ttk.Button(toolbar, text="类型转换", command=self._on_convert_type).pack(side='left', padx=2)
        ttk.Button(toolbar, text="刷新", command=self._on_refresh).pack(side='left', padx=(10, 2))

        # ── 主体: 属性表 + 信息面板 ──
        body = ttk.PanedWindow(self, orient='horizontal')
        body.pack(fill='both', expand=True, padx=5, pady=5)

        # 左侧属性表
        self._table = AttributeTable(body, height=18)
        body.add(self._table, weight=3)

        # 右键菜单
        self._table.set_context_menu(col_menu_items=[
            ("删除字段", self._on_delete_field),
            ("重命名", self._on_rename_field),
            ("类型转换", self._on_convert_type),
            ("---", lambda: None),
            ("查看统计", self._on_show_stats),
        ])

        # 点击列标题 → 更新右侧统计
        self._table._tree.bind('<ButtonRelease-1>', self._on_table_click, add='+')

        # 右侧信息面板
        info_frame = ttk.Frame(body)
        body.add(info_frame, weight=1)

        # 矢量基本信息
        info1 = ttk.LabelFrame(info_frame, text="矢量信息", padding=5)
        info1.pack(fill='x', padx=3, pady=3)
        self._info_text = tk.Text(info1, height=8, width=25, state='disabled', wrap='word')
        self._info_text.pack(fill='both', expand=True)

        # 选中字段统计
        info2 = ttk.LabelFrame(info_frame, text="字段统计", padding=5)
        info2.pack(fill='x', padx=3, pady=3)
        self._stats_text = tk.Text(info2, height=10, width=25, state='disabled', wrap='word')
        self._stats_text.pack(fill='both', expand=True)

        # ── 内嵌小日志 ──
        self._mini_log = LogPanel(self, title="操作日志", height=4)
        self._mini_log.pack(fill='x', padx=5, pady=3)

    # ━━ 加载 ━━

    def _on_load(self):
        path = filedialog.askopenfilename(
            title="加载矢量文件",
            filetypes=[("Shapefile", "*.shp"), ("GeoJSON", "*.geojson"), ("All", "*.*")])
        if not path:
            return
        self._load_vector(path)

    def _load_vector(self, path):
        try:
            self._am = AttributeManager(path, log_func=self._mini_log.append)
            self._am.load()
            self._modified = False
            self._refresh_table()
            self._refresh_vector_info()
            self.app_state.current_vector = path
            self._mini_log.append(f"加载成功: {os.path.basename(path)} ({self._am.get_record_count()} 行)")
            self.log.log(f"[属性表] 加载: {path}")
        except Exception as e:
            messagebox.showerror("错误", f"加载失败:\n{e}")
            self.log.log(f"[属性表] 加载失败: {e}", 'error')

    def _refresh_table(self):
        if not self._am or not self._am.is_loaded():
            return
        fields = self._am.get_fields()
        # 加上几何列 (用于右击参考，但显示时隐藏)
        all_fields = fields + ['geometry']
        records = self._am.get_records()
        self._table.load_data(all_fields, records)

    def _refresh_vector_info(self):
        if not self._am:
            return
        info = DataPreviewer.get_vector_info(self._am.get_path())
        if info:
            text = (
                f"文件: {os.path.basename(info['path'])}\n"
                f"格式: {info['format']}\n"
                f"CRS: {info['crs'][:40]}...\n"
                f"记录数: {info['record_count']}\n"
                f"字段数: {info['field_count']}\n"
                f"几何类型: {info['geometry_type']}\n"
                f"范围: [{info['bounds'][0]:.1f}, {info['bounds'][1]:.1f}, "
                f"{info['bounds'][2]:.1f}, {info['bounds'][3]:.1f}]"
            )
            self._info_text.config(state='normal')
            self._info_text.delete('1.0', 'end')
            self._info_text.insert('1.0', text)
            self._info_text.config(state='disabled')

    # ━━ 增删改 ━━

    def _on_add_field(self):
        if not self._am or not self._am.is_loaded():
            messagebox.showwarning("提示", "请先加载矢量")
            return
        dlg = AddFieldDialog(self.winfo_toplevel(),
            existing_fields=self._am.get_fields())
        res = dlg.wait_result()
        if res:
            name, ftype, default = res
            ok = self._am.add_field(name, ftype, default)
            if ok:
                self._table.add_column(name, ftype)
                self._mark_modified()
                self._mini_log.append(f"添加字段: {name} ({ftype})")

    def _on_delete_field(self):
        if not self._am or not self._am.is_loaded():
            return
        field = self._table.get_selected_fields()
        if not field:
            # 尝试从点击的列获取
            sel = self._table._tree.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选中一个字段（点击列标题）")
                return
            # 从选中的列取
            cols = self._table._tree['columns']
            if not cols:
                return
            field = cols[0]  # fallback

        if field == 'geometry':
            messagebox.showwarning("提示", "不能删除几何列")
            return

        if not messagebox.askyesno("确认", f"确定删除字段 '{field}'？\n此操作不可撤销。"):
            return

        ok = self._am.delete_field(field)
        if ok:
            self._table.remove_column(field)
            self._mark_modified()
            self._mini_log.append(f"删除字段: {field}")

    def _on_rename_field(self):
        if not self._am:
            return
        field = self._table.get_selected_fields()
        if not field:
            messagebox.showwarning("提示", "请右键列标题选择要重命名的字段")
            return
        new_name = simpledialog.askstring("重命名字段",
            f"将 '{field}' 重命名为:", parent=self)
        if not new_name or new_name == field:
            return
        ok = self._am.rename_field(field, new_name)
        if ok:
            self._table.rename_column(field, new_name)
            self._mark_modified()
            self._mini_log.append(f"重命名: {field} → {new_name}")

    def _on_convert_type(self):
        if not self._am:
            return
        field = self._table.get_selected_fields()
        if not field:
            messagebox.showwarning("提示", "请右键列标题选择要转换的字段")
            return

        # 类型选择
        win = tk.Toplevel(self)
        win.title("类型转换")
        win.geometry("250x120")
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text=f"将 '{field}' 转换为:").pack(pady=10)
        type_var = tk.StringVar(value="str")
        ttk.Combobox(win, textvariable=type_var,
            values=["int", "float", "str"], state='readonly', width=10).pack()
        def _do_convert():
            new_type = type_var.get()
            win.destroy()
            if new_type in ('int',) and self._am.get_field_type(field) == 'float':
                if not messagebox.askyesno("精度警告",
                    f"float → int 将丢失小数部分.\n确定转换？"):
                    return
            ok = self._am.convert_field_type(field, new_type)
            if ok:
                self._refresh_table()
                self._mark_modified()
                self._mini_log.append(f"类型转换: {field} → {new_type}")
            else:
                messagebox.showerror("错误", f"类型转换失败，请查看日志")
        ttk.Button(win, text="确定", command=_do_convert).pack()
        win.bind('<Return>', lambda e: _do_convert())

    # ━━ 统计 ━━

    def _on_show_stats(self):
        if not self._am:
            return
        field = self._table.get_selected_fields()
        if not field:
            return
        self._update_stats(field)

    def _update_stats(self, field):
        if not self._am:
            return
        stats = self._am.get_field_stats(field)
        text = f"字段: {field}\n"
        if stats:
            text += (
                f"类型: {stats['type']}\n"
                f"有效值: {stats['count']}\n"
                f"空值: {stats['null_count']}\n"
                f"均值: {stats['mean']}\n"
                f"标准差: {stats['std']}\n"
                f"最小值: {stats['min']}\n"
                f"最大值: {stats['max']}\n"
                f"Q25: {stats['q25']}\n"
                f"中位数: {stats['median']}\n"
                f"Q75: {stats['q75']}"
            )
        else:
            ft = self._am.get_field_type(field)
            if ft == 'str':
                # 文本字段统计
                import pandas as pd
                series = self._am._gdf[field]
                unique = series.nunique()
                nulls = series.isna().sum()
                text += f"类型: str\n唯一值: {unique}\n空值: {nulls}"
            else:
                text += "非数值字段, 无法统计"
        self._stats_text.config(state='normal')
        self._stats_text.delete('1.0', 'end')
        self._stats_text.insert('1.0', text)
        self._stats_text.config(state='disabled')

    def _on_table_click(self, event):
        """点击属性表时更新统计."""
        region = self._table._tree.identify_region(event.x, event.y)
        if region == 'heading':
            col = self._table._tree.identify_column(event.x)
            col_idx = int(col.replace('#', '')) - 1
            columns = self._table._tree['columns']
            if 0 <= col_idx < len(columns):
                self._update_stats(columns[col_idx])

    # ━━ 保存 ━━

    def _on_save(self):
        if not self._am:
            return
        path = self._am.get_path()
        saved = self._am.save(path, overwrite=True)
        if saved:
            self._modified = False
            self._mini_log.append(f"保存成功: {os.path.basename(saved)}")

    def _on_save_as(self):
        if not self._am:
            return
        path = filedialog.asksaveasfilename(
            title="另存为",
            defaultextension=".shp",
            filetypes=[("Shapefile", "*.shp"), ("GeoJSON", "*.geojson")])
        if not path:
            return
        saved = self._am.save(path, overwrite=True)
        if saved:
            self._modified = False
            self._mini_log.append(f"另存为: {os.path.basename(saved)}")

    def _on_refresh(self):
        if self._am:
            self._refresh_table()
            self._refresh_vector_info()

    def _mark_modified(self):
        self._modified = True

    # ── 状态读写 ──

    def get_state(self):
        return {'current_vector': self._am.get_path() if self._am else ''}

    def set_state(self, state):
        if not state:
            return
        path = state.get('current_vector', '')
        if path and os.path.exists(path):
            self._load_vector(path)
