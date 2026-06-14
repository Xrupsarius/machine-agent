import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    def file_handler(filename: str) -> logging.Handler:
        h = logging.handlers.RotatingFileHandler(
            logs_dir / filename, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        h.setFormatter(fmt)
        return h

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler("system.log"))

    logging.getLogger("agent").addHandler(file_handler("agent.log"))
    logging.getLogger("actions").addHandler(file_handler("actions.log"))

    error_handler = file_handler("errors.log")
    error_handler.setLevel(logging.ERROR)
    root.addHandler(error_handler)
