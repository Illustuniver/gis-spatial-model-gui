# -*- coding: utf-8 -*-
"""
attribute_table.py — 属性表展示组件
=====================================
封装 ttk.Treeview 展示矢量属性表，支持: 列排序、右键菜单、字段增删。
为 Tab4 属性表管理页服务。

设计要点:
  - 大数据量(>1000行)限制预览，提示「仅展示前 N 行」
  - 数值列右对齐，文本列左对齐
  - 排序记住当前列+方向，再次点击反转
  - 几何列默认隐藏/置灰，不允许编辑删除
  - 右键菜单: 列标题右键 vs 行右键
"""

import tkinter as tk
from tkinter import ttk


class AttributeTable(ttk.Frame):
    """属性表展示组件.

    Usage:
        table = AttributeTable(master, height=15)
        table.pack(fill='both', expand=True)
        table.load_data(['ID', 'name', 'value'], [
            {'ID': 1, 'name': 'A', 'value': 3.14},
            {'ID': 2, 'name': 'B', 'value': 2.71},
        ])
    """

    # 预览上限
    MAX_PREVIEW_ROWS = 1000

    def __init__(self, master, height=15):
        """
        Args:
            master: 父容器
            height: Treeview 高度 (行数)
        """
        super().__init__(master)
        self._height = height
        self._fields = []          # 字段名列表
        self._records = []         # 完整记录列表
        self._total_count = 0      # 总记录数
        self._sort_col = None      # 当前排序列
        self._sort_reverse = False # 排序方向
        self._geometry_col = 'geometry'  # 几何列名
        self._col_menu_items = []  # 右键菜单项 [(label, callback), ...]
        self._row_menu_items = []

        # ── 容器: Treeview + 水平/垂直滚动条 ──
        self._container = ttk.Frame(self)
        self._container.pack(fill='both', expand=True)

        # Treeview (列稍后动态创建)
        self._tree = ttk.Treeview(
            self._container, show='headings', height=height)
        self._tree.pack(side='left', fill='both', expand=True)

        # 垂直滚动条
        self._vsb = ttk.Scrollbar(
            self._container, orient='vertical', command=self._tree.yview)
        self._vsb.pack(side='right', fill='y')
        self._tree.configure(yscrollcommand=self._vsb.set)

        # 水平滚动条
        self._hsb = ttk.Scrollbar(
            self, orient='horizontal', command=self._tree.xview)
        self._hsb.pack(side='bottom', fill='x')
        self._tree.configure(xscrollcommand=self._hsb.set)

        # 事件绑定
        self._tree.bind('<ButtonRelease-1>', self._on_column_click)
        self._tree.bind('<Button-3>', self._on_right_click)  # 右键

        # 总行数提示标签
        self._info_label = ttk.Label(
            self, text="", foreground="gray")
        self._info_label.pack(side='bottom', anchor='w', padx=5)

    # ── 数据加载 ──

    def load_data(self, fields, records):
        """加载属性表数据.

        Args:
            fields:  字段名列表 list[str]
            records: 记录列表 list[dict], 每条 {字段名: 值}
        """
        self._fields = list(fields)
        self._records = list(records)
        self._total_count = len(records)
        self._sort_col = None

        # 隐藏几何列
        display_fields = [f for f in self._fields if f != self._geometry_col]
        # 如果几何列是唯一列，保留它
        if not display_fields and self._fields:
            display_fields = self._fields

        # 重建 Treeview 列
        self._tree['columns'] = display_fields
        for col in display_fields:
            self._tree.heading(col, text=col)
            # 检测列类型决定对齐
            sample_vals = [r.get(col) for r in records[:20] if col in r]
            numeric = all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in sample_vals if v is not None
            )
            anchor = 'e' if numeric else 'w'
            self._tree.column(col, width=100, anchor=anchor, minwidth=60)

        # 填充行 (限制预览)
        preview_count = min(self._total_count, self.MAX_PREVIEW_ROWS)
        self._tree.delete(*self._tree.get_children())
        for i in range(preview_count):
            row = self._records[i]
            values = [row.get(f, '') for f in display_fields]
            self._tree.insert('', 'end', values=values)

        # 更新提示
        if self._total_count > self.MAX_PREVIEW_ROWS:
            self._info_label.configure(
                text=f"⚠ 仅展示前 {self.MAX_PREVIEW_ROWS} 行 (共 {self._total_count} 行), 操作全量生效")
        else:
            self._info_label.configure(text=f"共 {self._total_count} 行, {len(display_fields)} 字段")

    def clear(self):
        """清空表格."""
        self._fields.clear()
        self._records.clear()
        self._tree.delete(*self._tree.get_children())
        self._tree['columns'] = []
        self._info_label.configure(text="")

    # ── 排序 ──

    def _on_column_click(self, event):
        """列标题点击 → 排序."""
        region = self._tree.identify_region(event.x, event.y)
        if region != 'heading':
            return
        col = self._tree.identify_column(event.x)
        col_idx = int(col.replace('#', '')) - 1
        columns = self._tree['columns']
        if col_idx < 0 or col_idx >= len(columns):
            return
        field = columns[col_idx]
        # 切换排序方向
        if self._sort_col == field:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = field
            self._sort_reverse = False
        self.sort_by(field, self._sort_reverse)

    def sort_by(self, field_name, reverse=False):
        """按指定列排序.

        Args:
            field_name: 字段名
            reverse:    是否降序
        """
        if field_name not in self._fields:
            return

        # 检测数据类型
        sample_vals = [r.get(field_name) for r in self._records[:50] if field_name in r]
        numeric = all(
            isinstance(v, (int, float)) and not isinstance(v, bool)
            for v in sample_vals if v is not None
        )

        if numeric:
            key_fn = lambda r: (
                r.get(field_name) if isinstance(r.get(field_name), (int, float))
                else float('nan')
            )
        else:
            key_fn = lambda r: str(r.get(field_name, '')).lower()

        self._sort_col = field_name
        self._sort_reverse = reverse
        self._records.sort(key=key_fn, reverse=reverse)
        self.load_data(self._fields, self._records)

    # ── 右键菜单 ──

    def set_context_menu(self, col_menu_items=None, row_menu_items=None):
        """设置右键菜单项.

        Args:
            col_menu_items: 列标题右键菜单 [(label, callback), ...]
            row_menu_items: 行右键菜单 [(label, callback), ...]
        """
        self._col_menu_items = col_menu_items or []
        self._row_menu_items = row_menu_items or []

    def _on_right_click(self, event):
        """右键点击 → 弹出菜单."""
        region = self._tree.identify_region(event.x, event.y)
        if region == 'heading':
            # 列标题右键
            if not self._col_menu_items:
                return
            col = self._tree.identify_column(event.x)
            col_idx = int(col.replace('#', '')) - 1
            columns = self._tree['columns']
            if 0 <= col_idx < len(columns):
                self._selected_field = columns[col_idx]
                self._show_menu(event, self._col_menu_items)
        elif region == 'cell':
            # 有选中行时也可以弹菜单 (保留但非核心)
            pass

    def _show_menu(self, event, items):
        """弹出右键菜单."""
        menu = tk.Menu(self, tearoff=0)
        for label, callback in items:
            if label == '---':
                menu.add_separator()
            else:
                menu.add_command(label=label, command=callback)
        menu.post(event.x_root, event.y_root)

    # ── 字段操作 ──

    def add_column(self, field_name, field_type='str'):
        """添加一列 (在 Treeview 中显示).

        Args:
            field_name: 字段名
            field_type: 'int'/'float'/'str' (决定对齐方式)
        """
        if field_name in self._tree['columns']:
            return
        anchor = 'e' if field_type in ('int', 'float') else 'w'
        columns = list(self._tree['columns'])
        columns.append(field_name)
        self._tree['columns'] = columns
        self._tree.heading(field_name, text=field_name)
        self._tree.column(field_name, width=100, anchor=anchor)
        # 给已有行填充空值
        for item in self._tree.get_children():
            vals = list(self._tree.item(item, 'values'))
            vals.append('')
            self._tree.item(item, values=tuple(vals))

    def remove_column(self, field_name):
        """删除一列 (从 Treeview 中移除).

        Args:
            field_name: 字段名
        """
        columns = list(self._tree['columns'])
        if field_name not in columns:
            return
        idx = columns.index(field_name)
        columns.remove(field_name)
        # 重建列
        self._tree['columns'] = columns
        for item in self._tree.get_children():
            vals = list(self._tree.item(item, 'values'))
            if idx < len(vals):
                vals.pop(idx)
            self._tree.item(item, values=tuple(vals))

    def rename_column(self, old_name, new_name):
        """重命名一列.

        Args:
            old_name: 原字段名
            new_name: 新字段名
        """
        columns = list(self._tree['columns'])
        if old_name not in columns:
            return
        idx = columns.index(old_name)
        columns[idx] = new_name
        self._tree['columns'] = columns
        self._tree.heading(new_name, text=new_name)
        # 保持原有列属性
        self._tree.column(new_name, width=100, anchor=self._tree.column(old_name).get('anchor', 'w'))

    # ── 选择 ──

    def get_selected_fields(self):
        """获取右键点击时选中的字段名.

        Returns:
            str | None.
        """
        return getattr(self, '_selected_field', None)

    def get_selected_records(self):
        """获取选中的行数据.

        Returns:
            list[dict]: 选中行的记录列表.
        """
        selected = []
        for item in self._tree.selection():
            vals = self._tree.item(item, 'values')
            columns = self._tree['columns']
            rec = {columns[i]: vals[i] for i in range(min(len(columns), len(vals)))}
            selected.append(rec)
        return selected

    def get_fields(self):
        """获取当前显示的字段列表."""
        return list(self._tree['columns'])

    def get_row_count(self):
        """获取总行数."""
        return self._total_count

    def refresh(self):
        """刷新显示 (重新 load_data)."""
        if self._fields and self._records:
            self.load_data(self._fields, self._records)
