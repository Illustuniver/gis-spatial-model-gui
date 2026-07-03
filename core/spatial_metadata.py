# -*- coding: utf-8 -*-
"""
spatial_metadata.py — 空间元数据统一抽象
============================================
提供三个处理器共享的基础数据类，统一 CRS/范围/窗口等概念。

设计原则:
  - 纯数据类, 零依赖 (仅 dataclass + Optional)
  - 不修改 scripts/processing/ 下任何文件
  - 供 app/ 内部使用, 消除重复的正则和参数散落
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SpatialExtent:
    """空间元数据统一容器.

    封装栅格/矢量的核心空间属性, 供 Validator/Previewer/处理器共享.
    """
    crs: str = ''            # CRS 字符串
    width: int = 0           # 列数 (栅格) 或 0 (矢量)
    height: int = 0          # 行数 (栅格) 或 0 (矢量)
    resolution: tuple = ()   # (x_res, y_res) — 栅格专用
    nodata: Optional[float] = None
    bounds: tuple = ()       # (minx, miny, maxx, maxy)

    @classmethod
    def from_raster(cls, path: str) -> Optional['SpatialExtent']:
        """从 GeoTIFF 读取空间元数据."""
        try:
            import rasterio
            with rasterio.open(path) as src:
                return cls(
                    crs=str(src.crs) if src.crs else '',
                    width=src.width,
                    height=src.height,
                    resolution=src.res,
                    nodata=src.nodata,
                    bounds=tuple(src.bounds),
                )
        except Exception:
            return None

    @classmethod
    def from_vector(cls, path: str) -> Optional['SpatialExtent']:
        """从矢量文件读取空间元数据."""
        try:
            import geopandas as gpd
            gdf = gpd.read_file(path)
            return cls(
                crs=str(gdf.crs) if gdf.crs else '',
                bounds=tuple(gdf.total_bounds),
            )
        except Exception:
            return None

    def to_profile(self) -> dict:
        """转为 rasterio profile 格式."""
        return {
            'crs': self.crs,
            'width': self.width,
            'height': self.height,
            'transform': None,
        }


@dataclass
class ProcessingWindow:
    """移动窗口处理单元.

    统一 Tab2 (文件名正则) 和 Tab3 (核大小) 的"尺度"概念.
    """
    size: int           # 窗口像素大小 (如 3, 5, 160)
    label: str          # 显示标签 (如 "3x3", "160x160")

    def __post_init__(self):
        if not self.label:
            self.label = f"{self.size}x{self.size}"

    @classmethod
    def parse(cls, label: str) -> Optional['ProcessingWindow']:
        """从标签解析窗口, 如 "3x3" → ProcessingWindow(3)."""
        m = re.match(r'(\d+)\s*[xX×]\s*\1', label)
        if m:
            return cls(size=int(m.group(1)), label=label)
        return None

    @classmethod
    def from_filename(cls, filename: str) -> Optional['ProcessingWindow']:
        """从文件名中提取窗口尺寸, 如 "pland_3x3.tif" → ProcessingWindow(3).

        Tab2 的 3 处正则均可替换为此方法.
        """
        m = re.search(r'(\d+)\s*[xX×]\s*\1', filename)
        if m:
            size = int(m.group(1))
            return cls(size=size, label=f"{size}x{size}")
        return None

    @classmethod
    def from_fca_filename(cls, filename: str) -> Optional['ProcessingWindow']:
        """从 FCA 文件名提取窗口, 如 "frag_60x60.fca" → ProcessingWindow(60)."""
        m = re.match(r'frag_(\d+)x\1\.fca', filename)
        if m:
            size = int(m.group(1))
            return cls(size=size, label=f"{size}x{size}")
        return None
