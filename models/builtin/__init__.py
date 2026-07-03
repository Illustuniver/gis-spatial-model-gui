# -*- coding: utf-8 -*-
"""
builtin/ — 内置模型实现目录
=============================
每个模型一个 .py 文件，类上加 @register_model 装饰器自动注册。

示例 (后续实现 RF 时):
    # random_forest.py
    from app.models import BaseModel, register_model

    @register_model("Random Forest")
    class RandomForestModel(BaseModel):
        ...
"""
