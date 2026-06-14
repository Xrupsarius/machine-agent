import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        if handler not in self._handlers[event]:
            self._handlers[event].append(handler)
            log.debug(f"Subscribed {handler.__name__} to '{event}'")

    def unsubscribe(self, event: str, handler: Callable) -> None:
        if handler in self._handlers[event]:
            self._handlers[event].remove(handler)
            log.debug(f"Unsubscribed {handler.__name__} from '{event}'")

    def publish(self, event: str, data: Any = None) -> None:
        log.debug(f"Event '{event}' published, data={data}")
        for handler in list(self._handlers[event]):
            try:
                handler(data)
            except Exception as e:
                log.error(f"Handler {handler.__name__} failed on event '{event}': {e}")

    def clear(self) -> None:
        self._handlers.clear()
