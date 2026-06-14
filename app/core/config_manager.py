import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, path: str = "config.yaml") -> None:
        self._path = Path(path)
        self._config: dict = {}
        self.reload()

    def reload(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}
        log.info(f"Config loaded from {self._path}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def all(self) -> dict:
        return dict(self._config)
