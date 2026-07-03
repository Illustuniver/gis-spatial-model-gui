# -*- coding: utf-8 -*-
"""
attribute_manager.py — 属性表管理核心
========================================
封装矢量属性表的所有操作: 加载、字段增删、重命名、类型转换、统计信息、保存。

设计原则:
  - 内存操作，延迟写盘: 所有修改在内存 GeoDataFrame 上进行，save() 才写文件
  - SHP 字段名兼容: 保存时自动检查字段名长度 (>10 字符给警告)
  - 类型转换容错: int↔float↔str 安全转换，失败不破坏数据
  - 字段名冲突处理: 重名自动加后缀 _1
  - 几何列保护: 自动跳过 geometry 列，不允许删除
  - 日志回调: 关键操作走 log_func，和三个 Processor 一致的接口风格

零 tkinter 依赖。
"""

import sys
import os
import numpy as np
import pandas as pd
import geopandas as gpd

# --- SHP 字段名 10 字符限制 ---
SHP_FIELD_NAME_MAX_LEN = 10


class AttributeManager:
    """属性表管理器 — 封装矢量属性表的所有操作.

    Usage:
        am = AttributeManager('data.shp', log_func=print)
        am.load()
        am.add_field('elevation', 'float', default_value=0.0)
        am.rename_field('old_name', 'new_name')
        stats = am.get_field_stats('elevation')
        am.save('output.shp')
    """

    def __init__(self, vector_path, log_func=None):
        """
        Args:
            vector_path: 矢量文件路径 (SHP / GeoJSON)
            log_func:    日志回调函数 (callable(msg) 或 None)
        """
        self._path = vector_path
        self._log = log_func or (lambda msg: None)
        self._gdf = None          # GeoDataFrame (所有修改都在内存中进行)
        self._loaded = False
        self._modified = False    # 是否有未保存的修改
        self._geometry_col = None # 几何列名

    # ── 基础 I/O ──

    def load(self):
        """加载矢量文件到内存.

        Returns:
            self (链式调用).
        """
        self._log(f"加载矢量: {self._path}")
        self._gdf = gpd.read_file(self._path)
        self._geometry_col = self._gdf.geometry.name
        self._loaded = True
        self._modified = False
        self._log(f"  要素数: {len(self._gdf)}, 字段数: {len(self.get_fields())}")
        return self

    def is_loaded(self):
        """是否已加载数据."""
        return self._loaded and self._gdf is not None

    def is_modified(self):
        """是否有未保存的修改."""
        return self._modified

    # ── 字段查询 ──

    def get_fields(self):
        """获取所有属性字段名列表 (不含几何列).

        Returns:
            list[str]: 字段名列表.
        """
        if not self.is_loaded():
            return []
        return [c for c in self._gdf.columns if c != self._geometry_col]

    def _get_all_columns(self):
        """获取所有列名 (含几何列)."""
        if not self.is_loaded():
            return []
        return list(self._gdf.columns)

    def get_field_type(self, field_name):
        """获取字段数据类型.

        Args:
            field_name: 字段名

        Returns:
            str: 'int' / 'float' / 'str' / 'geometry' / 'unknown'.
        """
        if not self.is_loaded():
            return 'unknown'
        if field_name not in self._gdf.columns:
            return 'unknown'
        dtype = self._gdf[field_name].dtype
        if field_name == self._geometry_col:
            return 'geometry'
        # pandas nullable 类型 (Int64, Float64 等) 需优先判断
        if pd.api.types.is_integer_dtype(dtype):
            return 'int'
        if pd.api.types.is_float_dtype(dtype):
            return 'float'
        if pd.api.types.is_string_dtype(dtype) or dtype == object:
            # 检查是否实际存的是字符串
            sample = self._gdf[field_name].dropna()
            if len(sample) > 0:
                first = sample.iloc[0]
                if isinstance(first, str):
                    return 'str'
            return 'str'
        return 'unknown'

    def get_records(self, limit=None):
        """获取属性表记录.

        Args:
            limit: 最大返回行数 (None = 全部)

        Returns:
            list[dict]: 记录列表，每条为 {字段名: 值}.
        """
        if not self.is_loaded():
            return []
        gdf = self._gdf.head(limit) if limit else self._gdf
        records = []
        geom_col = self._geometry_col
        for _, row in gdf.iterrows():
            rec = {}
            for col in gdf.columns:
                val = row[col]
                if col == geom_col and hasattr(val, 'wkt'):
                    rec[col] = val.wkt
                else:
                    rec[col] = val
            records.append(rec)
        return records

    def get_record_count(self):
        """获取总记录数."""
        if not self.is_loaded():
            return 0
        return len(self._gdf)

    # ── 字段增删 ──

    def add_field(self, field_name, field_type='float', default_value=None):
        """添加新字段.

        Args:
            field_name:    新字段名
            field_type:    字段类型 ('int' / 'float' / 'str')
            default_value: 默认填充值 (None 则用类型默认: int→0, float→0.0, str→'')

        Returns:
            bool: 是否成功.
        """
        if not self.is_loaded():
            self._log("[ERROR] 未加载数据，无法添加字段")
            return False

        # 字段名冲突处理: 重名自动加后缀 _1
        original = field_name
        suffix = 1
        while field_name in self._gdf.columns:
            field_name = f"{original}_{suffix}"
            suffix += 1
        if field_name != original:
            self._log(f"[WARN] 字段名冲突, 自动改为: {field_name}")

        # 确定默认填充值
        if default_value is None:
            type_defaults = {'int': 0, 'float': 0.0, 'str': ''}
            default_value = type_defaults.get(field_type, '')

        # 类型映射
        dtype_map = {'int': 'int64', 'float': 'float64', 'str': 'object'}
        dtype = dtype_map.get(field_type, 'object')

        try:
            self._gdf[field_name] = default_value
            # 尝试转换类型
            if field_type == 'int':
                self._gdf[field_name] = self._gdf[field_name].astype('int64')
            elif field_type == 'float':
                self._gdf[field_name] = self._gdf[field_name].astype('float64')
            else:
                self._gdf[field_name] = self._gdf[field_name].astype('object')
                self._gdf[field_name] = self._gdf[field_name].apply(
                    lambda x: str(x) if x is not None else ''
                )
            self._modified = True
            self._log(f"添加字段: '{field_name}' (类型: {field_type}, 默认值: {default_value})")
            return True
        except Exception as e:
            self._log(f"[ERROR] 添加字段失败: {e}")
            # 回滚: 删除刚添加的列
            if field_name in self._gdf.columns:
                self._gdf.drop(columns=[field_name], inplace=True)
            return False

    def delete_field(self, field_name):
        """删除单个字段.

        几何列自动保护，不允许删除。

        Args:
            field_name: 要删除的字段名

        Returns:
            bool: 是否成功.
        """
        if not self.is_loaded():
            self._log("[ERROR] 未加载数据，无法删除字段")
            return False

        # 几何列保护
        if field_name == self._geometry_col:
            self._log(f"[WARN] 不允许删除几何列: '{field_name}'")
            return False

        if field_name not in self._gdf.columns:
            self._log(f"[WARN] 字段不存在: '{field_name}'")
            return False

        try:
            self._gdf.drop(columns=[field_name], inplace=True)
            self._modified = True
            self._log(f"删除字段: '{field_name}'")
            return True
        except Exception as e:
            self._log(f"[ERROR] 删除字段失败: {e}")
            return False

    def delete_fields(self, field_names):
        """批量删除字段.

        Args:
            field_names: 要删除的字段名列表

        Returns:
            int: 实际删除的字段数量.
        """
        count = 0
        for name in field_names:
            if self.delete_field(name):
                count += 1
        return count

    def rename_field(self, old_name, new_name):
        """重命名字段.

        Args:
            old_name: 原字段名
            new_name: 新字段名

        Returns:
            bool: 是否成功.
        """
        if not self.is_loaded():
            self._log("[ERROR] 未加载数据，无法重命名字段")
            return False

        # 几何列保护
        if old_name == self._geometry_col:
            self._log(f"[WARN] 不允许重命名几何列: '{old_name}'")
            return False

        if old_name not in self._gdf.columns:
            self._log(f"[WARN] 字段不存在: '{old_name}'")
            return False

        # 新名称冲突
        if new_name in self._gdf.columns and new_name != old_name:
            # 自动加后缀
            base = new_name
            suffix = 1
            while new_name in self._gdf.columns:
                new_name = f"{base}_{suffix}"
                suffix += 1
            self._log(f"[WARN] 字段名冲突, 自动改为: {new_name}")

        try:
            self._gdf.rename(columns={old_name: new_name}, inplace=True)
            self._modified = True
            self._log(f"重命名字段: '{old_name}' → '{new_name}'")
            return True
        except Exception as e:
            self._log(f"[ERROR] 重命名字段失败: {e}")
            return False

    def fill_field(self, field_name, value):
        """批量填充字段值.

        Args:
            field_name: 字段名
            value:      填充值

        Returns:
            int: 填充的记录数量, -1 表示失败.
        """
        if not self.is_loaded():
            self._log("[ERROR] 未加载数据，无法填充字段")
            return -1

        if field_name not in self._gdf.columns:
            self._log(f"[WARN] 字段不存在: '{field_name}'")
            return -1

        try:
            self._gdf[field_name] = value
            self._modified = True
            self._log(f"填充字段: '{field_name}' = {value}")
            return len(self._gdf)
        except Exception as e:
            self._log(f"[ERROR] 填充字段失败: {e}")
            return -1

    # ── 类型转换 ──

    def convert_field_type(self, field_name, new_type):
        """将字段转换为指定类型.

        安全规则:
          - int → float: 直接转 (无损)
          - float → int: 警告精度丢失，四舍五入后转
          - str → int/float: 尝试 pd.to_numeric，失败返回 False
          - int/float → str: 直接转

        Args:
            field_name: 字段名
            new_type:   目标类型 ('int' / 'float' / 'str')

        Returns:
            bool: 是否成功.
        """
        if not self.is_loaded():
            self._log("[ERROR] 未加载数据，无法转换类型")
            return False

        if field_name not in self._gdf.columns:
            self._log(f"[WARN] 字段不存在: '{field_name}'")
            return False

        if field_name == self._geometry_col:
            self._log(f"[WARN] 不允许转换几何列类型")
            return False

        old_type = self.get_field_type(field_name)
        self._log(f"类型转换: '{field_name}' ({old_type} → {new_type})")

        try:
            if new_type == 'int':
                if old_type == 'float':
                    self._log(f"  [WARN] float → int 将丢失小数部分 (四舍五入)")
                    self._gdf[field_name] = self._gdf[field_name].round(0).astype('Int64')  # nullable int
                elif old_type == 'str':
                    self._gdf[field_name] = self._gdf[field_name].replace('', np.nan)
                    self._gdf[field_name] = pd.to_numeric(
                        self._gdf[field_name], errors='coerce'
                    ).round(0).astype('Int64')
                else:
                    self._gdf[field_name] = self._gdf[field_name].astype('Int64')

            elif new_type == 'float':
                if old_type == 'str':
                    self._gdf[field_name] = self._gdf[field_name].replace('', np.nan)
                    self._gdf[field_name] = pd.to_numeric(
                        self._gdf[field_name], errors='coerce'
                    ).astype('float64')
                else:
                    self._gdf[field_name] = self._gdf[field_name].astype('float64')

            elif new_type == 'str':
                self._gdf[field_name] = self._gdf[field_name].astype('object')
                self._gdf[field_name] = self._gdf[field_name].apply(
                    lambda x: str(x) if pd.notna(x) else ''
                )

            else:
                self._log(f"[ERROR] 不支持的类型: {new_type}")
                return False

            self._modified = True
            self._log(f"  转换成功: '{field_name}' → {new_type}")
            return True

        except Exception as e:
            self._log(f"[ERROR] 类型转换失败: {e}")
            return False

    # ── 数值统计 ──

    def get_field_stats(self, field_name):
        """获取数值字段的统计信息.

        Args:
            field_name: 字段名 (必须是数值类型: int 或 float)

        Returns:
            dict 或 None (失败/非数值):
                {
                    'field': str,      字段名
                    'type': str,       类型
                    'count': int,      有效值数量 (非空)
                    'null_count': int, 空值数量
                    'mean': float,     均值
                    'std': float,      标准差
                    'min': float,      最小值
                    'max': float,      最大值
                    'q25': float,      25% 分位数
                    'median': float,   中位数
                    'q75': float,      75% 分位数
                }
        """
        if not self.is_loaded():
            return None

        if field_name not in self._gdf.columns:
            self._log(f"[WARN] 字段不存在: '{field_name}'")
            return None

        ft = self.get_field_type(field_name)
        if ft not in ('int', 'float'):
            self._log(f"[WARN] 非数值字段无法统计: '{field_name}' (类型: {ft})")
            return None

        series = self._gdf[field_name]
        null_mask = series.isna()
        valid = series[~null_mask]

        if len(valid) == 0:
            return {
                'field': field_name,
                'type': ft,
                'count': 0,
                'null_count': len(series),
                'mean': float('nan'),
                'std': float('nan'),
                'min': float('nan'),
                'max': float('nan'),
                'q25': float('nan'),
                'median': float('nan'),
                'q75': float('nan'),
            }

        return {
            'field': field_name,
            'type': ft,
            'count': len(valid),
            'null_count': int(null_mask.sum()),
            'mean': round(float(valid.mean()), 4),
            'std': round(float(valid.std()), 4),
            'min': round(float(valid.min()), 4),
            'max': round(float(valid.max()), 4),
            'q25': round(float(valid.quantile(0.25)), 4),
            'median': round(float(valid.median()), 4),
            'q75': round(float(valid.quantile(0.75)), 4),
        }

    # ── 保存 ──

    def save(self, output_path=None, overwrite=False):
        """保存修改后的矢量文件.

        SHP 字段名兼容:
          - 保存前检查字段名是否超过 10 字符
          - 有超长的发警告 (不自动截断，保留用户控制权)

        Args:
            output_path: 输出路径 (None = 覆盖原文件)
            overwrite:   是否允许覆盖已有文件

        Returns:
            str: 实际保存的文件路径, None 表示失败.
        """
        if not self.is_loaded():
            self._log("[ERROR] 未加载数据，无法保存")
            return None

        if output_path is None:
            output_path = self._path

        # 确保输出路径有正确的扩展名
        if not output_path.lower().endswith(('.shp', '.geojson', '.gpkg')):
            output_path += '.shp'

        # 确保目录存在 (复用 raster_utils 的 ensure_dir)
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # 检查是否覆盖
        if os.path.exists(output_path) and not overwrite:
            self._log(f"[WARN] 文件已存在: {output_path} (如需覆盖请设 overwrite=True)")
            return None

        # SHP 字段名长度检查
        is_shp = output_path.lower().endswith('.shp')
        if is_shp:
            long_fields = []
            for col in self._gdf.columns:
                if col != self._geometry_col and len(col) > SHP_FIELD_NAME_MAX_LEN:
                    long_fields.append(col)
            if long_fields:
                self._log(f"[WARN] SHP 字段名限制: 以下 {len(long_fields)} 个字段超过 {SHP_FIELD_NAME_MAX_LEN} 字符 (将自动截断):")
                for f in long_fields:
                    self._log(f"  '{f}' ({len(f)} 字符) → '{f[:SHP_FIELD_NAME_MAX_LEN]}'")

        try:
            self._gdf.to_file(output_path, encoding='utf-8')
            self._log(f"保存成功: {output_path} ({len(self._gdf)} 要素, {len(self.get_fields())} 属性字段)")
            # 更新内部路径和修改标记
            if output_path != self._path:
                self._path = output_path
            self._modified = False
            return output_path
        except Exception as e:
            self._log(f"[ERROR] 保存失败: {e}")
            return None

    # ── 辅助 ──

    def get_path(self):
        """获取当前矢量文件路径."""
        return self._path

    def get_crs(self):
        """获取当前 CRS (字符串)."""
        if not self.is_loaded():
            return ''
        return str(self._gdf.crs) if self._gdf.crs else ''
