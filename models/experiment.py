# -*- coding: utf-8 -*-
"""
experiment.py — 模型实验与评估系统
====================================
统一实验接口: train/test split, cross-validation, metrics, 模型对比.

设计原则:
  - 不依赖 tkinter (纯业务逻辑)
  - sklearn 延迟导入
  - 结果统一为 dict 格式
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ExperimentConfig:
    """实验配置."""
    model_name: str           # 模型名称
    model_params: dict        # 模型超参数
    test_size: float = 0.2    # 测试集比例
    cv_folds: int = 5         # 交叉验证折数
    random_state: int = 42
    spatial_cv: bool = False  # 是否用空间 CV


@dataclass
class ExperimentResult:
    """单次实验结果."""
    model_name: str
    metrics: Dict[str, float]      # {'r2': ..., 'rmse': ..., 'mae': ...}
    cv_scores: Dict[str, list]     # 各折分数
    predictions: Optional[np.ndarray] = None
    feature_importance: Optional[Dict[str, float]] = None
    train_time: float = 0.0
    n_samples: int = 0
    n_features: int = 0


class ExperimentRunner:
    """模型实验运行器.

    支持: train/test split, K-fold CV, 空间 CV (预留), 多模型对比.

    Usage:
        runner = ExperimentRunner()
        result = runner.run(
            model_cls=RandomForestModel,
            params={'n_estimators': 100},
            X=X_train, y=y_train, X_test=X_test, y_test=y_test
        )

        # 多模型对比
        comparison = runner.compare([
            ('RF', RandomForestModel, {'n_estimators': 100}),
            ('RF-200', RandomForestModel, {'n_estimators': 200}),
        ], X_train, y_train, X_test, y_test)
    """

    @staticmethod
    def run(model_cls, params, X, y, X_test=None, y_test=None, coords=None):
        """执行单次实验.

        Args:
            model_cls: 模型类 (BaseModel 子类)
            params:    模型超参数
            X, y:      训练数据
            X_test, y_test: 测试数据 (None 则自动 split)
            coords:    空间坐标 (空间模型用)

        Returns:
            ExperimentResult.
        """
        from sklearn.model_selection import train_test_split
        from sklearn.model_selection import cross_val_score

        model = model_cls(params)

        # 自动 train/test split
        if X_test is None or y_test is None:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
        else:
            X_train, y_train = X, y

        import time
        t0 = time.time()
        model.fit(X_train, y_train, coords=coords)
        train_time = time.time() - t0

        metrics = model.evaluate(X_test, y_test, coords=coords)
        fi = model.get_feature_importance()

        return ExperimentResult(
            model_name=model_cls.__name__,
            metrics=metrics,
            cv_scores={},
            predictions=model.predict(X_test, coords=coords),
            feature_importance=fi,
            train_time=train_time,
            n_samples=len(X),
            n_features=X.shape[1],
        )

    @staticmethod
    def run_cv(model_cls, params, X, y, cv_folds=5, coords=None):
        """K-fold 交叉验证实验.

        Returns:
            ExperimentResult (含 cv_scores).
        """
        from sklearn.model_selection import KFold
        import time

        kf = KFold(n_splits=cv_folds, shuffle=True, random_state=42)

        cv_r2, cv_rmse, cv_mae = [], [], []
        t0 = time.time()

        for train_idx, val_idx in kf.split(X):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model = model_cls(params)
            model.fit(X_tr, y_tr, coords=coords)
            m = model.evaluate(X_val, y_val, coords=coords)
            cv_r2.append(m['r2'])
            cv_rmse.append(m['rmse'])
            cv_mae.append(m['mae'])

        train_time = time.time() - t0

        # 最后一个模型做全量评估
        final_model = model_cls(params)
        final_model.fit(X, y, coords=coords)
        final_metrics = final_model.evaluate(X, y, coords=coords)

        return ExperimentResult(
            model_name=model_cls.__name__,
            metrics=final_metrics,
            cv_scores={'r2': cv_r2, 'rmse': cv_rmse, 'mae': cv_mae},
            predictions=final_model.predict(X, coords=coords),
            feature_importance=final_model.get_feature_importance(),
            train_time=train_time,
            n_samples=len(X),
            n_features=X.shape[1],
        )

    @staticmethod
    def compare(experiments: List[tuple], X, y, X_test=None, y_test=None):
        """多模型对比实验.

        Args:
            experiments: [(name, model_cls, params), ...]
            X, y:        训练数据
            X_test, y_test: 测试数据

        Returns:
            list[ExperimentResult]: 每个模型的实验结果.
        """
        results = []
        for name, model_cls, params in experiments:
            result = ExperimentRunner.run(
                model_cls, params, X, y, X_test, y_test
            )
            result.model_name = name
            results.append(result)
        return results
