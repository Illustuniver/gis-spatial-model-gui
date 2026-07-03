# -*- coding: utf-8 -*-
"""
registry.py — 模型注册中心
============================
自动发现、注册、管理所有模型，提供统一的获取接口。

设计原则:
  - 装饰器注册: @register_model("名称") 一行完成注册
  - 自动发现: auto_discover() 扫描 models/builtin/ 自动 import
  - 单例模式: 全局只有一个 ModelRegistry 实例
  - 容错扫描: 某个模型缺依赖时跳过并打日志，不崩掉
  - 重复处理: 后注册覆盖先注册，打 warn 日志，不报错

零 tkinter 依赖，纯 Python 标准库实现。
"""

import os
import sys
import importlib
import importlib.util


# ── 装饰器: @register_model(name) ──

def register_model(name):
    """模型注册装饰器.

    用法:
        @register_model("Random Forest")
        class RandomForestModel(BaseModel):
            ...

    Args:
        name: 模型显示名称 (如 "Random Forest", "XGBoost", "GWR")

    Returns:
        装饰器函数.
    """
    def decorator(cls):
        # 延迟注册: 等 registry 实例初始化后再注册
        # 但如果 registry 已存在，直接注册
        if _registry_instance is not None:
            _registry_instance.register(name, cls)
        else:
            # 推入待注册队列，等 init_registry() 时统一处理
            _pending_registry.append((name, cls))
        return cls
    return decorator


# ── 待注册队列 (在 registry 单例创建前使用) ──

_pending_registry = []  # type: list[tuple[str, type]]
_registry_instance = None  # 单例引用


# ── 注册中心单例 ──

class ModelRegistry:
    """模型注册中心 (单例).

    管理所有已注册的模型类，提供按名称获取、列表查询、自动发现等功能。
    全局通过 registry 单例访问，不直接实例化。
    """

    def __init__(self):
        self._models = {}  # {name: model_class}

    def register(self, name, model_class):
        """注册一个模型.

        重复注册: 后注册覆盖先注册，打印 warn 日志.

        Args:
            name:        模型名称 (str)
            model_class: 模型类 (BaseModel 子类)
        """
        if name in self._models:
            old = self._models[name].__name__
            new = model_class.__name__
            print(f"[WARN] 模型名冲突: '{name}' ({old} → {new}), 后者覆盖")
        self._models[name] = model_class

    def get(self, name):
        """按名称获取模型类.

        Args:
            name: 模型名称.

        Returns:
            模型类 (BaseModel 子类).

        Raises:
            ValueError: 模型不存在, 附带可用模型列表.
        """
        if name not in self._models:
            available = sorted(self._models.keys())
            raise ValueError(
                f"模型 '{name}' 未注册.\n"
                f"可用模型 ({len(available)}): {', '.join(available)}"
            )
        return self._models[name]

    def list_models(self):
        """列出所有可用模型名称.

        Returns:
            list[str]: 模型名列表.
        """
        return sorted(self._models.keys())

    def list_spatial_models(self):
        """列出所有空间模型.

        Returns:
            list[str]: 空间模型名列表.
        """
        return [name for name, cls in self._models.items()
                if getattr(cls, 'is_spatial', lambda: False)(cls)]

    def list_non_spatial_models(self):
        """列出所有非空间模型.

        Returns:
            list[str]: 非空间模型名列表.
        """
        return [name for name, cls in self._models.items()
                if not getattr(cls, 'is_spatial', lambda: False)(cls)]

    def auto_discover(self, extra_dirs=None):
        """自动扫描模型目录，导入 .py 文件触发注册.

        扫描 builtin/ 目录 + 可选的外部插件目录.
        import 失败 (缺依赖) 时跳过并打日志，不崩掉.

        Args:
            extra_dirs: 额外的插件目录列表 (list[str] 或 None).

        Returns:
            int: 本次新发现的模型数量.
        """
        before_count = len(self._models)

        # 收集所有扫描目录
        dirs = [os.path.join(os.path.dirname(__file__), 'builtin')]
        if extra_dirs:
            dirs.extend(extra_dirs)

        for scan_dir in dirs:
            if not os.path.isdir(scan_dir):
                continue

            # 扫描 .py 文件 (排除 __init__)
            py_files = [
                f for f in os.listdir(scan_dir)
                if f.endswith('.py') and not f.startswith('_')
            ]
            # 确定包名
            is_builtin = scan_dir == dirs[0]
            pkg_prefix = 'app.models.builtin' if is_builtin else None

            for py_file in sorted(py_files):
                module_name = py_file[:-3]
                if pkg_prefix:
                    full_name = f"{pkg_prefix}.{module_name}"
                else:
                    # 外部目录: 用文件路径作为模块名
                    full_name = module_name
                    # 确保外部目录在 sys.path 中
                    if scan_dir not in sys.path:
                        sys.path.insert(0, scan_dir)

                try:
                    if full_name in sys.modules:
                        importlib.reload(sys.modules[full_name])
                    else:
                        importlib.import_module(full_name)
                except Exception as e:
                    print(f"[WARN] 跳过模型 '{module_name}': {e}")
                    continue

        new_count = len(self._models) - before_count
        return new_count

    @property
    def count(self):
        """已注册模型数量."""
        return len(self._models)


# ── 全局单例 ──

registry = ModelRegistry()
_registry_instance = registry


# ── 处理待注册队列 ──

for _name, _cls in _pending_registry:
    registry.register(_name, _cls)
_pending_registry.clear()


# ── 门面函数 ──

def get_model(name):
    """获取模型的便捷函数.

    Args:
        name: 模型名称.

    Returns:
        模型类.
    """
    return registry.get(name)


def list_models():
    """列出所有可用模型的便捷函数."""
    return registry.list_models()


def list_spatial_models():
    """列出所有空间模型的便捷函数."""
    return registry.list_spatial_models()
