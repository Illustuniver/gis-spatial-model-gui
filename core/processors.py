# -*- coding: utf-8 -*-
"""
processors.py — 处理器 re-export 层
=====================================
不修改原 scripts/processing/processors.py，
通过 sys.path 注入直接 re-export 三个处理器类。
后续所有页面从 app.core.processors 导入，不直接依赖原文件路径。

导出类:
    VectorJoinProcessor   — 矢量提取矢量 (空间连接)
    RasterSampler         — 矢量提取栅格 (点/面采样)
    LandscapeProcessor    — 景观格局指数移动窗口计算
"""

import sys
import os

# ── 路径: app/core/ → ../../scripts/processing/ ──
_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'scripts', 'processing'
))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# 同时确保 raster_utils.py 所在目录也在路径中
# (processors.py 内部 import raster_utils，需要能找到)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from processors import (  # noqa: E402, F401
    VectorJoinProcessor,
    RasterSampler,
    LandscapeProcessor,
)

__all__ = [
    'VectorJoinProcessor',
    'RasterSampler',
    'LandscapeProcessor',
]
