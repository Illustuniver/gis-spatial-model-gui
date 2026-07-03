# -*- coding: utf-8 -*-
"""
Random Forest — 模型插件
==========================
基于 scikit-learn RandomForestRegressor.
从同目录 model.json 读取参数规格，支持 UI 自动生成。
"""

import json
import os
import numpy as np

from ...base import BaseModel
from ...registry import register_model

# 加载 model.json
_JSON_PATH = os.path.join(os.path.dirname(__file__), 'model.json')
with open(_JSON_PATH, 'r', encoding='utf-8') as _f:
    _SPEC = json.load(_f)


@register_model(_SPEC['name'])
class RandomForestModel(BaseModel):
    """Random Forest 回归模型.

    Usage:
        model = RandomForestModel({'n_estimators': 200, 'max_depth': 15})
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        metrics = model.evaluate(X_test, y_test)
    """

    @classmethod
    def get_json_spec(cls):
        """返回 model.json 规格 (供 GUI 自动生成参数面板)."""
        return _SPEC

    @classmethod
    def get_default_params(cls):
        """从 model.json 提取默认参数字典."""
        return {p['name']: p['default'] for p in _SPEC.get('params', [])}

    def __init__(self, params=None):
        merged = self.get_default_params()
        if params:
            merged.update(params)
        super().__init__(merged)

    def fit(self, X, y, coords=None):
        from sklearn.ensemble import RandomForestRegressor
        import pandas as pd

        self._feature_names = (
            list(X.columns) if isinstance(X, pd.DataFrame)
            else [f'X{i}' for i in range(X.shape[1])]
        )

        self._model = RandomForestRegressor(
            n_estimators=int(self._params['n_estimators']),
            max_depth=int(self._params['max_depth']) if self._params.get('max_depth') else None,
            min_samples_split=int(self._params.get('min_samples_split', 2)),
            min_samples_leaf=int(self._params.get('min_samples_leaf', 1)),
            random_state=int(self._params.get('random_state', 42)),
            n_jobs=-1,
        )
        self._model.fit(X, y)
        return self

    def predict(self, X, coords=None):
        if not hasattr(self, '_model'):
            raise RuntimeError("模型未训练，请先调用 fit()")
        return self._model.predict(X)

    def get_params(self):
        return dict(self._params)

    def set_params(self, params):
        self._params.update(params)
        return self

    def get_feature_importance(self):
        if not hasattr(self, '_model'):
            return None
        return {
            name: float(imp)
            for name, imp in zip(self._feature_names, self._model.feature_importances_)
        }

    def get_param_grid(self):
        return {
            'n_estimators': [50, 100, 200, 300],
            'max_depth': [5, 10, 15, 20, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
        }
