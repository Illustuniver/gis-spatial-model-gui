# -*- coding: utf-8 -*-
"""
data_preview.py — 数据预览器
==============================
提供矢量/栅格数据的快速预览能力，供 UI 预览面板使用。

设计原则:
  - 栅格缩略图优先读 overviews，没有则用降采样读取 (out_shape)，避免全量加载
  - 大栅格 (>10000×10000) 限制读取分辨率，不卡 UI
  - 矢量预览只取前 N 行，不全量加载
  - 返回值统一用字典，UI 层不关心 geopandas/rasterio 内部结构

零 tkinter 依赖，纯数据层。
"""

import sys
import os
import numpy as np

# 路径注入
_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'scripts', 'processing'
))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import rasterio
import geopandas as gpd


class DataPreviewer:
    """数据预览器 — 提供矢量/栅格的基本信息和预览数据.

    所有方法都是静态方法，无状态。
    """

    # 大栅格阈值 (像素): 超过此尺寸限制读取分辨率
    LARGE_RASTER_THRESHOLD = 10000 * 10000

    @staticmethod
    def get_vector_info(vector_path):
        """获取矢量文件基本信息.

        Args:
            vector_path: 矢量文件路径 (SHP/GeoJSON)

        Returns:
            dict 或 None (失败时):
                {
                    'path': str,        文件路径
                    'format': str,      格式 (ESRI Shapefile / GeoJSON)
                    'crs': str,         CRS 字符串
                    'record_count': int, 要素数量
                    'field_count': int,  属性字段数 (不含几何)
                    'fields': list[str], 属性字段名列表
                    'geometry_type': str, 几何类型
                    'bounds': list[float], [minx, miny, maxx, maxy]
                }
        """
        try:
            gdf = gpd.read_file(vector_path)
            fields = [c for c in gdf.columns if c != gdf.geometry.name]

            # 推断格式
            fmt = 'Unknown'
            ext = os.path.splitext(vector_path)[1].lower()
            if ext == '.shp':
                fmt = 'ESRI Shapefile'
            elif ext in ('.geojson', '.json'):
                fmt = 'GeoJSON'
            elif ext == '.gpkg':
                fmt = 'GeoPackage'

            geom_types = gdf.geometry.geom_type.unique().tolist()
            geom_type_str = ', '.join(geom_types) if geom_types else 'Unknown'

            return {
                'path': vector_path,
                'format': fmt,
                'crs': str(gdf.crs) if gdf.crs else '未定义',
                'record_count': len(gdf),
                'field_count': len(fields),
                'fields': fields,
                'geometry_type': geom_type_str,
                'bounds': gdf.total_bounds.tolist(),  # [minx, miny, maxx, maxy]
            }
        except Exception as e:
            return None

    @staticmethod
    def get_raster_info(raster_path):
        """获取栅格文件基本信息.

        Args:
            raster_path: 栅格文件路径 (GeoTIFF)

        Returns:
            dict 或 None (失败时):
                {
                    'path': str,
                    'crs': str,
                    'width': int,        列数
                    'height': int,       行数
                    'band_count': int,   波段数
                    'resolution': (float, float),  (x_res, y_res)
                    'nodata': float|None,
                    'dtype': str,        数据类型
                    'bounds': list[float],
                    'pixel_count': int,  像元总数
                }
        """
        try:
            with rasterio.open(raster_path) as src:
                return {
                    'path': raster_path,
                    'crs': str(src.crs) if src.crs else '未定义',
                    'width': src.width,
                    'height': src.height,
                    'band_count': src.count,
                    'resolution': src.res,  # (x_res, y_res)
                    'nodata': src.nodata,
                    'dtype': src.dtypes[0] if src.dtypes else 'unknown',
                    'bounds': list(src.bounds),
                    'pixel_count': src.width * src.height,
                }
        except Exception as e:
            return None

    @staticmethod
    def get_vector_preview(vector_path, limit=50):
        """获取矢量属性表预览数据 (前 N 行).

        Args:
            vector_path: 矢量文件路径
            limit:       最大返回行数 (默认 50)

        Returns:
            dict 或 None (失败时):
                {
                    'fields': list[str],     字段名列表 (含几何)
                    'records': list[dict],   记录列表，每条为 {field: value}
                    'total_count': int,      总记录数
                }
        """
        try:
            gdf = gpd.read_file(vector_path)
            # 只取前 limit 行
            sample = gdf.head(limit)
            # 将几何列转为 WKT 字符串，便于显示
            geom_col = gdf.geometry.name
            cols = list(sample.columns)
            records = []
            for _, row in sample.iterrows():
                rec = {}
                for col in cols:
                    val = row[col]
                    if col == geom_col and hasattr(val, 'wkt'):
                        rec[col] = val.wkt
                    else:
                        rec[col] = val
                records.append(rec)

            return {
                'fields': cols,
                'records': records,
                'total_count': len(gdf),
            }
        except Exception as e:
            return None

    @staticmethod
    def get_raster_thumbnail(raster_path, size=200):
        """生成栅格缩略图.

        策略:
          1. 优先使用 rasterio overviews (概览层)
          2. 没有 overviews 则用 out_shape 降采样读取
          3. 大栅格 (>10000x10000) 强制限制输出尺寸

        Args:
            raster_path: 栅格文件路径
            size:        缩略图最长边像素数 (默认 200)

        Returns:
            numpy.ndarray (shape: (H, W)) 或 None (失败时).
            值归一化到 0-255 的 uint8.
        """
        try:
            with rasterio.open(raster_path) as src:
                w, h = src.width, src.height

                # 计算输出尺寸: 等比缩放，最长边 = size
                if w >= h:
                    out_w = size
                    out_h = max(1, int(h * size / w))
                else:
                    out_h = size
                    out_w = max(1, int(w * size / h))

                # 策略 1: 使用 overviews
                if src.overviews(1):
                    # 找最接近目标尺寸的 overview 层级
                    overviews = sorted(src.overviews(1))
                    target_scale = min(out_w, out_h)
                    best_ovr = overviews[0]
                    for ovr in overviews:
                        if ovr >= target_scale:
                            best_ovr = ovr
                            break
                    # 读 overview
                    arr = src.read(1, out_shape=(best_ovr, best_ovr))
                else:
                    # 策略 2: 降采样读取 (out_shape 参数)
                    arr = src.read(1, out_shape=(out_h, out_w))

                # 归一化到 0-255
                arr = arr.astype(np.float32)
                finite_mask = np.isfinite(arr)
                if finite_mask.any():
                    vmin = np.nanmin(arr[finite_mask])
                    vmax = np.nanmax(arr[finite_mask])
                    if vmax - vmin > 1e-8:
                        arr = (arr - vmin) / (vmax - vmin) * 255.0
                    else:
                        arr[:] = 128
                arr = np.clip(arr, 0, 255).astype(np.uint8)

                # NaN → 0
                arr[~np.isfinite(arr)] = 0

                return arr

        except Exception as e:
            return None
