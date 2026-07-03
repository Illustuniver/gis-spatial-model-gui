# -*- coding: utf-8 -*-
"""
project_io.py — 工程文件读写管理
==================================
支持 .dsproj 格式 (JSON) 的工程文件保存/加载/校验。

设计原则 (对标 GeoXGBoost 博主):
  - 向下兼容: 所有字段用 .get() 读取，缺省自动填充
  - 版本管理: 工程文件包含 version 字段，便于未来升级
  - 完整性校验: 加载时检查必要结构

零 tkinter 依赖，纯 Python 标准库实现。
"""

import os
import json
from datetime import datetime


class ProjectManager:
    """工程文件管理器.

    工程文件格式 (.dsproj):
        {
            "version": "1.0",
            "saved_at": "2026-07-02 18:00:00",
            "global": {
                "ref_raster": "...",
                "out_dir": "...",
                "fragstats_exe": "...",
                "fca_dir": "..."
            },
            "tab1_vector_join": { ... },
            "tab2_raster_sample": { ... },
            "tab3_landscape": { ... },
            "tab4_attribute": { ... },    # v2.0 新增
            "model_config": { ... }       # v2.0 新增 (预留)
        }
    """

    CURRENT_VERSION = '1.0'

    def save(self, path, state_dict):
        """保存工程文件.

        Args:
            path:        保存路径 (自动加 .dsproj 后缀)
            state_dict:  状态字典 (通常由 AppState.to_dict() 生成)

        Returns:
            str: 实际保存的文件路径.
        """
        # 确保路径以 .dsproj 结尾
        if not path.lower().endswith('.dsproj'):
            path += '.dsproj'

        # 注入元数据
        data = {
            'version': self.CURRENT_VERSION,
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        data.update(state_dict)

        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return path

    def load(self, path):
        """加载工程文件.

        向下兼容规则:
          - 旧版本缺少的字段自动用默认值填充
          - 不存在的 tab 自动给空字典
          - version 字段缺失时默认为 '1.0'

        Args:
            path: 工程文件路径 (.dsproj).

        Returns:
            dict: 状态字典.

        Raises:
            FileNotFoundError: 文件不存在.
            ValueError: JSON 格式错误或结构损坏.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"工程文件不存在: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 校验: 必须有基本结构
        if not isinstance(data, dict):
            raise ValueError("工程文件格式错误: 根不是字典")

        # 向下兼容: 用 .get() 逐字段读取，缺省自动填充
        state = {
            'version': data.get('version', '1.0'),
            'saved_at': data.get('saved_at', ''),
            'global': {
                'ref_raster':    data.get('global', {}).get('ref_raster', ''),
                'out_dir':       data.get('global', {}).get('out_dir', ''),
                'fragstats_exe': data.get('global', {}).get('fragstats_exe', ''),
                'fca_dir':       data.get('global', {}).get('fca_dir', ''),
            },
            'tab1_vector_join':    data.get('tab1_vector_join', {}),
            'tab2_raster_sample':  data.get('tab2_raster_sample', {}),
            'tab3_landscape':      data.get('tab3_landscape', {}),
            'tab4_attribute':      data.get('tab4_attribute', {}),
            'model_config':        data.get('model_config', {}),
        }

        return state

    def validate(self, data):
        """校验工程文件版本和完整性.

        Args:
            data: 从 load() 返回的状态字典.

        Returns:
            (bool, str): (是否有效, 提示信息).
        """
        if not isinstance(data, dict):
            return False, "数据格式错误: 不是字典"

        # 检查必要顶层键
        required_sections = ['global', 'tab1_vector_join', 'tab2_raster_sample', 'tab3_landscape']
        for section in required_sections:
            if section not in data:
                return False, f"缺少必要节: {section}"

        # 版本兼容性警告 (不阻止加载)
        version = data.get('version', '1.0')
        if version != self.CURRENT_VERSION:
            return True, f"版本 {version} → {self.CURRENT_VERSION} (兼容模式)"

        return True, "OK"
