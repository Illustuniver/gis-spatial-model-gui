# -*- coding: utf-8 -*-
"""
state.py — AppState 全局状态容器 (三层拆分)
===============================================
分层设计:
  第一层: 基础设施 - config, log_manager, stop_event (常驻, 不序列化)
  第二层: 工程状态 - project (ProjectSnapshot, 参与 .dsproj 序列化)
  第三层: 运行时状态 - running, current_vector (短暂, 不持久化)

设计原则:
  - 单例模式: 整个应用只有一个 AppState 实例
  - 页面间通信只走 AppState, 不直接互相引用
  - 工程序列化统一走 ProjectSnapshot.to_dict()/from_dict()
"""

import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any


@dataclass
class ProjectSnapshot:
    """工程状态快照 — 纯数据类, 参与 .dsproj 序列化.

    MainWindow 的 _save_project() / _load_project() 直接调用
    to_dict() / from_dict(), 不再走 AppState 的死代码.
    """
    ref_raster: str = ''
    out_dir: str = ''
    fragstats_exe: str = ''
    fca_dir: str = ''
    tabs_data: Dict[str, dict] = field(default_factory=dict)
    model_config: Dict[str, Any] = field(default_factory=dict)
    model_selection: str = ''     # 当前选中的模型名
    saved_at: str = ''

    def to_dict(self) -> dict:
        """导出为字典 (保存工程时调用)."""
        return {
            'version': '1.0',
            'saved_at': self.saved_at,
            'global': {
                'ref_raster': self.ref_raster,
                'out_dir': self.out_dir,
                'fragstats_exe': self.fragstats_exe,
                'fca_dir': self.fca_dir,
            },
            'tabs': self.tabs_data,
            'model_config': self.model_config,
            'model_selection': self.model_selection,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ProjectSnapshot':
        """从字典加载 (打开工程时调用). 所有字段用 .get() 向下兼容."""
        g = data.get('global', {})
        return cls(
            ref_raster=g.get('ref_raster', ''),
            out_dir=g.get('out_dir', ''),
            fragstats_exe=g.get('fragstats_exe', ''),
            fca_dir=g.get('fca_dir', ''),
            tabs_data=data.get('tabs', {}),
            model_config=data.get('model_config', {}),
            model_selection=data.get('model_selection', ''),
            saved_at=data.get('saved_at', ''),
        )


class AppState:
    """三层全局应用状态容器.

    Usage:
        state = AppState()
        state.config = app_config
        state.log_manager = log_manager

        # 工程序列化
        state.project = ProjectSnapshot.from_dict(data)
        d = state.project.to_dict()
    """

    def __init__(self):
        # ── 第一层: 基础设施 ──
        self.config = None       # AppConfig 实例
        self.log_manager = None  # LogManager 实例
        self.stop_event = threading.Event()

        # ── 第二层: 工程状态 ──
        self.project = ProjectSnapshot()

        # ── 第三层: 运行时状态 ──
        self.running = False
        self.current_vector: Optional[str] = None
        self.current_raster_list: List[dict] = []

    def log(self, msg, level='info'):
        """便捷日志: 如果 log_manager 存在则调用."""
        if self.log_manager:
            self.log_manager.log(msg, level)

    def reset(self):
        """重置运行时状态 (不影响 config 和 log_manager)."""
        self.stop_event.clear()
        self.project = ProjectSnapshot()
        self.current_vector = None
        self.current_raster_list.clear()
        self.running = False

    def cancel_all(self):
        """设置全局取消标志."""
        self.stop_event.set()

    def reset_cancel(self):
        """重置取消标志."""
        self.stop_event.clear()
