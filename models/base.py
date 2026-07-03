# -*- coding: utf-8 -*-
"""
base.py — 模型抽象基类
=======================
定义所有模型必须实现的统一接口。新增模型只需继承此类并实现抽象方法，
加 @register_model 装饰器即可自动注册。

设计原则:
  - 接口最小化: 只定义核心方法，不包含具体模型细节
  - coords=None 是空间模型的扩展参数，非空间模型直接忽略
  - 第三方依赖延迟导入 (sklearn/xgboost 等在方法内部 import)
  - 超参数统一用字典 params 传递，不拆成几十个形参
"""

from abc import ABC, abstractmethod


class BaseModel(ABC):
    """模型抽象基类.

    所有模型 (RF, XGBoost, GWR, MGWR, GeoXGBoost 等) 都继承此类，
    并实现四个核心抽象方法: fit, predict, get_params, set_params.

    Usage:
        @register_model("Random Forest")
        class RandomForestModel(BaseModel):
            def __init__(self, params=None):
                super().__init__(params or {'n_estimators': 100})
            def fit(self, X, y, coords=None):
                ...
            def predict(self, X, coords=None):
                ...
            def get_params(self):
                ...
            def set_params(self, params):
                ...
    """

    def __init__(self, params=None):
        """
        Args:
            params: 超参数字典 (dict). 子类可提供默认值.
                    例: {'n_estimators': 100, 'max_depth': 6}
        """
        self._params = params or {}

    # ── 四个核心抽象方法 (子类必须实现) ──

    @abstractmethod
    def fit(self, X, y, coords=None):
        """训练模型.

        Args:
            X:      特征矩阵 (pd.DataFrame 或 np.ndarray)
            y:      目标变量 (pd.Series 或 np.ndarray)
            coords: 空间坐标数组 shape=(n, 2), 空间模型用, 非空间模型忽略.

        Returns:
            self (支持链式调用).
        """
        ...

    @abstractmethod
    def predict(self, X, coords=None):
        """预测.

        Args:
            X:      特征矩阵
            coords: 空间坐标 (空间模型用)

        Returns:
            np.ndarray: 预测值.
        """
        ...

    @abstractmethod
    def get_params(self):
        """获取当前超参数.

        Returns:
            dict: 超参数字典.
        """
        ...

    @abstractmethod
    def set_params(self, params):
        """设置超参数.

        Args:
            params: 超参数字典 (部分更新).

        Returns:
            self.
        """
        ...

    # ── 有默认实现的方法 (子类可选覆盖) ──

    def evaluate(self, X, y, coords=None):
        """评估模型 — 返回 R², RMSE, MAE.

        默认实现: 内部调用 predict() 后用 sklearn 计算指标.

        Args:
            X:      特征矩阵
            y:      真实值
            coords: 空间坐标 (空间模型用)

        Returns:
            dict: {'r2': float, 'rmse': float, 'mae': float}
        """
        # sklearn 延迟导入 — 避免没装 sklearn 导致整个基类不可用
        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
        import numpy as np

        y_pred = self.predict(X, coords=coords)
        y_true = np.asarray(y).ravel()
        y_pred = np.asarray(y_pred).ravel()

        mse = mean_squared_error(y_true, y_pred)
        return {
            'r2': r2_score(y_true, y_pred),
            'rmse': float(np.sqrt(mse)),
            'mae': mean_absolute_error(y_true, y_pred),
        }

    def get_feature_importance(self):
        """获取特征重要性.

        默认返回 None. 树模型 (RF/XGBoost) 子类可覆盖.

        Returns:
            dict | None: {feature_name: importance_value} 或 None.
        """
        return None

    def get_param_grid(self):
        """返回超参数搜索空间，用于网格搜索 / 贝叶斯优化.

        子类覆盖此方法定义参数搜索范围.

        Returns:
            dict: 参数名 → 候选值列表.
            例: {'n_estimators': [50, 100, 200], 'max_depth': [3, 6, 9]}
        """
        return {}

    def is_spatial(self):
        """是否为空间模型.

        默认返回 False. 空间模型 (GWR/MGWR/GeoXGBoost) 子类覆盖.

        Returns:
            bool.
        """
        return False

    @staticmethod
    def get_metadata():
        """返回模型元数据 (用于注册中心展示和插件管理).

        子类可覆盖以提供版本/作者/依赖信息.

        Returns:
            dict: {'name': str, 'version': str, 'author': str, 'deps': list}.
        """
        return {
            'name': '',
            'version': '1.0',
            'author': '',
            'deps': [],
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(params={self.get_params()})>"
