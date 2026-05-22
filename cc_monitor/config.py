"""配置加载"""
import os
import yaml
from pathlib import Path

_project_root = Path(__file__).parent.parent
_config = {}


def load_config(path: str = None) -> dict:
    global _config
    if path is None:
        path = os.path.join(_project_root, "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f) or {}
    return _config


def get_config(key: str, default=None):
    return _config.get(key, default)


def get_project_root() -> Path:
    return _project_root
