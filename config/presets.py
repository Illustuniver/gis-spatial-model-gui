# -*- coding: utf-8 -*-
"""
presets.py — 预设管理门面
==========================
封装原 landscape_config.py 的所有函数，提供统一的预设管理接口。
支持景观/母质/通用等多种预设类型的扩展。

直接 re-export:
    load_preset, save_preset, list_presets, get_class_map,
    get_exclude_values, get_metrics, generate_feature_names

新增:
    list_preset_categories() — 列出所有预设分类
"""

import sys
import os

# 确保能 import 原 landscape_config
_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'scripts', 'processing'
))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import landscape_config as _lc
from landscape_config import (  # noqa: F401 — re-export
    load_preset,
    save_preset,
    list_presets,
    get_class_map,
    get_exclude_values,
    get_metrics,
    generate_feature_names,
)


def list_preset_categories():
    """列出所有预设分类.

    Returns:
        list[str]: 分类名列表，如 ['landscape', 'parent_material']
    """
    categories = set()
    master_path = os.path.join(_lc.PRESETS_DIR, 'master_presets.json')
    if os.path.exists(master_path):
        try:
            import json
            with open(master_path, 'r', encoding='utf-8') as f:
                master = json.load(f)
            categories.update(master.keys())
        except Exception:
            pass
    # 扫描独立 JSON 文件: 文件名即分类
    for fn in os.listdir(_lc.PRESETS_DIR):
        if fn.endswith('.json') and not fn.startswith('_') and fn != 'master_presets.json':
            name = fn.replace('.json', '')
            # 检查是否属于 master_presets 中的某类
            categories.add('general' if name not in categories else name)
    return sorted(categories)
