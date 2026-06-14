import logging
from typing import Any

log = logging.getLogger(__name__)


class ServiceNotFoundError(Exception):
    pass


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        if name in self._services:
            log.warning(f"Service '{name}' overwritten in registry")
        self._services[name] = service
        log.debug(f"Service '{name}' registered ({type(service).__name__})")

    def get(self, name: str) -> Any:
        if name not in self._services:
            raise ServiceNotFoundError(f"Service '{name}' not found in registry")
        return self._services[name]

    def has(self, name: str) -> bool:
        return name in self._services

    def all_names(self) -> list[str]:
        return list(self._services.keys())
