# -*- coding: utf-8 -*-
"""
models/ — 模型插件层
=====================
提供统一的模型接口和注册机制。新增模型只需在 builtin/ 下加一个文件，
继承 BaseModel，加 @register_model 装饰器，即可自动注册可用。

导出:
    BaseModel            — 模型抽象基类
    register_model       — 模型注册装饰器
    ModelRegistry        — 注册中心类
    registry             — 全局单例
    get_model(name)      — 按名称获取模型
    list_models()        — 列出所有模型
    list_spatial_models() — 列出空间模型

Usage:
    from app.models import BaseModel, register_model, get_model

    @register_model("MyModel")
    class MyModel(BaseModel):
        ...
"""

from .base import BaseModel
from .registry import (
    register_model,
    ModelRegistry,
    registry,
    get_model,
    list_models,
    list_spatial_models,
)

__all__ = [
    'BaseModel',
    'register_model',
    'ModelRegistry',
    'registry',
    'get_model',
    'list_models',
    'list_spatial_models',
]
