# -*- coding: utf-8 -*-
"""
models/ — 模型插件层
=====================
统一模型接口 + JSON 驱动自动注册 + 实验系统。

核心导出:
    BaseModel         — 模型抽象基类
    register_model    — 装饰器注册
    ModelRegistry     — 注册中心单例
    ModelLoader       — JSON + importlib 动态加载器
    ExperimentRunner  — 实验与评估系统
    ExperimentConfig  — 实验配置
    ExperimentResult  — 实验结果

Usage:
    from app.models import ModelLoader
    loader = ModelLoader()
    loader.discover()
    model_cls = loader.get_model("Random Forest")
"""

from .base import BaseModel
from .registry import register_model, ModelRegistry, registry
from .model_loader import ModelLoader
from .experiment import ExperimentRunner, ExperimentConfig, ExperimentResult

__all__ = [
    'BaseModel',
    'register_model',
    'ModelRegistry',
    'registry',
    'ModelLoader',
    'ExperimentRunner',
    'ExperimentConfig',
    'ExperimentResult',
]
