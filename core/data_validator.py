# -*- coding: utf-8 -*-
"""
data_validator.py — 输入数据自动校验
======================================
运行前自动检查数据问题，提前发现错误，不跑到一半报错。

设计原则 (对标 GeoXGBoost 博主):
  - 所有方法返回 (bool, str)，不抛异常，UI 直接拿结果打日志
  - CRS 比对复用 raster_utils._crs_match，不自己重写
  - 空间重叠只比 bounds，够用来预警，不做精确拓扑相交
  - validate_all() 统一返回问题列表 [{level, msg}]，UI 直接遍历渲染

纯静态工具类，零 tkinter 依赖，零状态。
"""

import sys
import os

# 路径注入: 确保能找到 scripts/processing/ 下的 raster_utils
_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'scripts', 'processing'
))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import rasterio
import geopandas as gpd
from raster_utils import _crs_match


class DataValidator:
    """输入数据自动校验器.

    所有方法都是静态方法或类方法，无状态，可随意调用。
    每个校验方法返回 (bool, str): (是否通过, 描述信息).
    """

    # 问题级别常量
    LEVEL_WARN = 'warn'    # 警告: 不阻止运行，仅提示
    LEVEL_ERROR = 'error'  # 错误: 建议阻止运行

    @staticmethod
    def check_crs_match(vector_path, raster_path):
        """检查矢量与栅格 CRS 是否一致.

        Args:
            vector_path: 矢量文件路径 (SHP/GeoJSON)
            raster_path: 栅格文件路径 (GeoTIFF)

        Returns:
            (bool, str): (是否匹配, 详细信息)
        """
        try:
            gdf = gpd.read_file(vector_path)
            with rasterio.open(raster_path) as src:
                raster_crs = src.crs
            if _crs_match(gdf.crs, raster_crs):
                return True, "CRS 一致"
            else:
                return False, f"CRS 不一致: 矢量={gdf.crs}, 栅格={raster_crs}"
        except Exception as e:
            return False, f"CRS 检查失败: {e}"

    @staticmethod
    def check_crs_match_vectors(vec1_path, vec2_path):
        """检查两个矢量 CRS 是否一致.

        Args:
            vec1_path: 矢量 1 路径
            vec2_path: 矢量 2 路径

        Returns:
            (bool, str): (是否匹配, 详细信息)
        """
        try:
            gdf1 = gpd.read_file(vec1_path)
            gdf2 = gpd.read_file(vec2_path)
            if _crs_match(gdf1.crs, gdf2.crs):
                return True, "CRS 一致"
            else:
                return False, f"CRS 不一致: 矢量1={gdf1.crs}, 矢量2={gdf2.crs}"
        except Exception as e:
            return False, f"CRS 检查失败: {e}"

    @staticmethod
    def check_spatial_overlap(vector_path, raster_path):
        """检查矢量与栅格空间范围是否有重叠.

        只比较 bounds，不做精确拓扑相交——够用来预警。

        Args:
            vector_path: 矢量文件路径
            raster_path: 栅格文件路径

        Returns:
            (bool, str): (是否重叠, 详细信息)
        """
        try:
            gdf = gpd.read_file(vector_path)
            with rasterio.open(raster_path) as src:
                raster_bounds = src.bounds  # (left, bottom, right, top)

            vec_bounds = gdf.total_bounds  # (minx, miny, maxx, maxy)

            # bounds 是否有交集
            overlap_x = (vec_bounds[0] < raster_bounds[2]) and (vec_bounds[2] > raster_bounds[0])
            overlap_y = (vec_bounds[1] < raster_bounds[3]) and (vec_bounds[3] > raster_bounds[1])

            if overlap_x and overlap_y:
                return True, "空间范围重叠"
            else:
                return False, (
                    f"空间范围不重叠: "
                    f"矢量 ({vec_bounds[0]:.2f},{vec_bounds[1]:.2f}) → "
                    f"({vec_bounds[2]:.2f},{vec_bounds[3]:.2f}), "
                    f"栅格 ({raster_bounds[0]:.2f},{raster_bounds[1]:.2f}) → "
                    f"({raster_bounds[2]:.2f},{raster_bounds[3]:.2f})"
                )
        except Exception as e:
            return False, f"空间重叠检查失败: {e}"

    @staticmethod
    def check_field_exists(vector_path, field_name):
        """检查矢量中是否存在指定字段.

        Args:
            vector_path: 矢量文件路径
            field_name:  要检查的字段名

        Returns:
            (bool, str): (是否存在, 详细信息)
        """
        try:
            gdf = gpd.read_file(vector_path)
            if field_name in gdf.columns:
                return True, f"字段 '{field_name}' 存在"
            else:
                cols = [c for c in gdf.columns if c != gdf.geometry.name][:10]
                return False, f"字段 '{field_name}' 不存在, 可用字段: {cols}"
        except Exception as e:
            return False, f"字段检查失败: {e}"

    @staticmethod
    def check_raster_valid(raster_path):
        """检查栅格文件是否可以正常打开读取.

        Args:
            raster_path: 栅格文件路径

        Returns:
            (bool, str): (是否有效, 详细信息)
        """
        try:
            if not os.path.exists(raster_path):
                return False, f"栅格文件不存在: {raster_path}"
            with rasterio.open(raster_path) as src:
                info = f"有效: {src.width}x{src.height}, {src.count} 波段, CRS={src.crs}"
                return True, info
        except Exception as e:
            return False, f"栅格无效: {e}"

    @staticmethod
    def check_vector_valid(vector_path):
        """检查矢量文件是否可以正常打开读取.

        Args:
            vector_path: 矢量文件路径

        Returns:
            (bool, str): (是否有效, 详细信息)
        """
        try:
            if not os.path.exists(vector_path):
                return False, f"矢量文件不存在: {vector_path}"
            gdf = gpd.read_file(vector_path)
            fields = [c for c in gdf.columns if c != gdf.geometry.name]
            return True, f"有效: {len(gdf)} 要素, {len(fields)} 个属性字段, CRS={gdf.crs}"
        except Exception as e:
            return False, f"矢量无效: {e}"

    @staticmethod
    def check_nodata_reasonable(raster_path):
        """检查栅格 nodata 值是否合理.

        常见不合理情况: nodata=None 但有明显填充值, 或 nodata 值在正常数据范围内.

        Args:
            raster_path: 栅格文件路径

        Returns:
            (bool, str): (是否合理, 详细信息)
        """
        try:
            with rasterio.open(raster_path) as src:
                nodata = src.nodata
                dtype = src.dtypes[0]

            if nodata is None:
                return True, "nodata 未设置 (注意: 可能有隐藏填充值)"

            # 检查 nodata 是否在数据类型范围内
            import numpy as np
            dtype_info = np.iinfo(dtype) if np.issubdtype(np.dtype(dtype), np.integer) else None
            if dtype_info:
                if nodata < dtype_info.min or nodata > dtype_info.max:
                    return False, f"nodata={nodata} 超出数据类型 {dtype} 范围"
            return True, f"nodata={nodata} (合理)"
        except Exception as e:
            return False, f"nodata 检查失败: {e}"

    @classmethod
    def validate_all(cls, target_vector, raster_list=None, source_vector=None):
        """全量校验，返回问题列表.

        Args:
            target_vector: 目标矢量路径 (必填)
            raster_list:   栅格路径列表 (可选, 用于矢→栅场景)
            source_vector: 源矢量路径 (可选, 用于矢→矢场景)

        Returns:
            list[dict]: 问题列表，每项:
                {'level': 'warn'|'error', 'msg': '问题描述'}
        """
        problems = []

        # 1. 目标矢量有效性
        ok, info = cls.check_vector_valid(target_vector)
        if not ok:
            problems.append({'level': cls.LEVEL_ERROR, 'msg': f"目标矢量无效: {info}"})
        else:
            problems.append({'level': 'info', 'msg': f"目标矢量: {info}"})

        # 2. 源矢量 (矢→矢场景)
        if source_vector:
            ok, info = cls.check_vector_valid(source_vector)
            if not ok:
                problems.append({'level': cls.LEVEL_ERROR, 'msg': f"源矢量无效: {info}"})
            else:
                problems.append({'level': 'info', 'msg': f"源矢量: {info}"})
                # CRS 一致性
                match, info = cls.check_crs_match_vectors(target_vector, source_vector)
                if not match:
                    problems.append({'level': cls.LEVEL_WARN, 'msg': f"矢量 CRS: {info}"})

        # 3. 栅格列表
        if raster_list:
            for raster_path in raster_list:
                ok, info = cls.check_raster_valid(raster_path)
                if not ok:
                    problems.append({'level': cls.LEVEL_ERROR, 'msg': f"栅格无效 [{os.path.basename(raster_path)}]: {info}"})
                    continue

                problems.append({'level': 'info', 'msg': f"栅格 [{os.path.basename(raster_path)}]: {info}"})

                # CRS 一致性
                match, info = cls.check_crs_match(target_vector, raster_path)
                if not match:
                    problems.append({'level': cls.LEVEL_WARN, 'msg': f"CRS [{os.path.basename(raster_path)}]: {info}"})

                # 空间重叠
                overlap, info = cls.check_spatial_overlap(target_vector, raster_path)
                if not overlap:
                    problems.append({'level': cls.LEVEL_WARN, 'msg': f"范围 [{os.path.basename(raster_path)}]: {info}"})

                # nodata
                ok, info = cls.check_nodata_reasonable(raster_path)
                if not ok:
                    problems.append({'level': cls.LEVEL_WARN, 'msg': f"nodata [{os.path.basename(raster_path)}]: {info}"})

        return problems
