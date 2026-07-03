# -*- coding: utf-8 -*-
"""
model_loader.py — JSON 驱动的模型动态加载器
=============================================
自动扫描 models/plugins/ 目录，从 model.json + model.py 加载模型。
替代旧 registry.auto_discover() 的硬编码 builtin/ 扫描。

加载流程:
  1. 扫描 plugins/ 下的每个子目录
  2. 读取 model.json 获取参数规格
  3. import model.py 触发 @register_model 装饰器
  4. 同时缓存 model.json 规格供 GUI 使用
"""

import os
import sys
import json
import importlib
import glob


class ModelLoader:
    """JSON + importlib 驱动的模型加载器.

    Usage:
        loader = ModelLoader()
        count = loader.discover()       # 扫描并加载所有模型
        specs = loader.list_specs()    # 获取所有 model.json 规格
        model_cls = loader.get_model('Random Forest')
    """

    def __init__(self, plugins_dir=None):
        self._plugins_dir = plugins_dir or os.path.join(
            os.path.dirname(__file__), 'plugins'
        )
        # {model_name: {'class': cls, 'spec': dict, 'path': str}}
        self._models = {}

    def discover(self):
        """扫描 plugins/ 目录，加载所有模型插件.

        Returns:
            int: 本次加载的模型数量.
        """
        before = len(self._models)

        if not os.path.isdir(self._plugins_dir):
            return 0

        entries = sorted(os.listdir(self._plugins_dir))
        for entry in entries:
            plugin_dir = os.path.join(self._plugins_dir, entry)
            if not os.path.isdir(plugin_dir) or entry.startswith('_'):
                continue

            json_path = os.path.join(plugin_dir, 'model.json')
            py_path = os.path.join(plugin_dir, 'model.py')

            if not os.path.isfile(json_path):
                continue

            # 1. 读取 model.json
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    spec = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARN] 跳过 '{entry}': model.json 无效 ({e})")
                continue

            model_name = spec.get('name', entry)

            # 2. 导入 model.py (触发 @register_model)
            if os.path.isfile(py_path):
                try:
                    mod_name = f"app.models.plugins.{entry}.model"
                    if mod_name in sys.modules:
                        importlib.reload(sys.modules[mod_name])
                    else:
                        importlib.import_module(mod_name)
                except Exception as e:
                    print(f"[WARN] 模型 '{model_name}' 导入失败: {e}")
                    continue

            # 3. 从 registry 获取已注册的类
            from .registry import registry
            model_cls = None
            try:
                model_cls = registry.get(model_name)
            except ValueError:
                # 尝试从 spec.name 匹配
                for name, cls in registry._models.items():
                    if name.lower() == model_name.lower():
                        model_cls = cls
                        break

            if model_cls is None:
                print(f"[WARN] 模型 '{model_name}': 未注册 (model.py 可能缺少 @register_model)")
                continue

            self._models[model_name] = {
                'class': model_cls,
                'spec': spec,
                'path': plugin_dir,
            }

        return len(self._models) - before

    def list_models(self):
        """列出所有已加载模型名称."""
        return sorted(self._models.keys())

    def list_specs(self):
        """列出所有模型规格 (供 GUI 使用).

        Returns:
            list[dict]: 每个模型规格, 含 name, type, params, description.
        """
        return [
            self._models[name]['spec']
            for name in sorted(self._models.keys())
        ]

    def get_spec(self, name):
        """获取模型 JSON 规格."""
        entry = self._models.get(name)
        return entry['spec'] if entry else None

    def get_model(self, name):
        """获取模型类."""
        entry = self._models.get(name)
        return entry['class'] if entry else None

    def get_default_params(self, name):
        """从 model.json 获取默认参数."""
        entry = self._models.get(name)
        if not entry:
            return {}
        return {p['name']: p['default'] for p in entry['spec'].get('params', [])}

    def get_param_specs(self, name):
        """获取参数规格列表 (供 GUI 自动生成面板).

        Returns:
            list[dict]: [{name, type, default, min, max, label, help}, ...]
        """
        entry = self._models.get(name)
        return entry['spec'].get('params', []) if entry else []
