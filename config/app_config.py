# -*- coding: utf-8 -*-
"""
app_config.py — 全局 GUI 配置管理
==================================
从原 datasets_gui.py 的 GlobalConfig 迁移并增强。
管理: 参考栅格路径、输出目录、Fragstats 路径、FCA 模板目录、最近工程列表。
配置文件保持和原文件同位置: scripts/processing/presets/_gui_config.json
"""

import os
import sys
import json


class AppConfig:
    """全局 GUI 配置管理器.

    配置项:
        ref_raster      — 参考栅格路径 (GeoTIFF)
        out_dir         — 默认输出目录
        fragstats_exe   — Fragstats 可执行文件路径
        fca_dir         — FCA 模板文件夹
        recent_projects — 最近工程列表 (最多 10 个)
    """

    def __init__(self):
        # 配置文件路径: 和原 GlobalConfig 同位置
        self.config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'scripts', 'processing',
            'presets', '_gui_config.json'
        )
        # 规范化绝对路径
        self.config_path = os.path.normpath(os.path.abspath(self.config_path))

        # 默认值
        self.ref_raster = ''
        self.out_dir = ''
        self.fragstats_exe = ''
        self.fca_dir = ''
        self.recent_projects = []  # type: list[str]

        # 自动探测 Fragstats
        self._auto_detect_fragstats()

        # 从文件加载 (覆盖默认值)
        self.load()

    def _auto_detect_fragstats(self):
        """自动探测 Fragstats 可执行文件路径 (运行时探测，不硬编码)."""
        # 1. 先尝试 PATH 中的命令
        import shutil
        found = shutil.which('frg_cmd') or shutil.which('frg_cmd.exe')
        if found:
            self.fragstats_exe = found
            return
        # 2. 扫描常见安装路径
        candidates = []
        if sys.platform == 'win32':
            for drive in ['C:', 'D:']:
                candidates.append(os.path.join(drive, 'Program Files', 'Fragstats 4.2', 'frg_cmd.exe'))
                candidates.append(os.path.join(drive, 'Program Files', 'Fragstats 4.2', 'frg_gui.exe'))
        else:
            candidates.extend(['/usr/local/bin/frg_cmd', '/opt/fragstats/frg_cmd'])
        for candidate in candidates:
            if os.path.isfile(candidate):
                self.fragstats_exe = candidate
                return

    def load(self):
        """从 JSON 文件加载配置."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.ref_raster = data.get('ref_raster', self.ref_raster)
            self.out_dir = data.get('out_dir', self.out_dir)
            self.fragstats_exe = data.get('fragstats_exe', self.fragstats_exe)
            self.fca_dir = data.get('fca_dir', self.fca_dir)
            # 向下兼容: 旧配置没有 recent_projects 字段
            self.recent_projects = data.get('recent_projects', [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # 首次运行尚无配置文件, 用默认值

    def save(self):
        """保存配置到 JSON 文件."""
        config_dir = os.path.dirname(self.config_path)
        os.makedirs(config_dir, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump({
                'ref_raster': self.ref_raster,
                'out_dir': self.out_dir,
                'fragstats_exe': self.fragstats_exe,
                'fca_dir': self.fca_dir,
                'recent_projects': self.recent_projects,
            }, f, indent=2, ensure_ascii=False)

    def add_recent_project(self, path):
        """添加一个工程到最近列表 (去重, 保持最新在最前, 最多 10 个).

        Args:
            path: 工程文件路径 (.dsproj)
        """
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        if len(self.recent_projects) > 10:
            self.recent_projects = self.recent_projects[:10]
        self.save()
