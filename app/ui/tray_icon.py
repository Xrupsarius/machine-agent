import logging
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, QSize

from app.core.event_bus import EventBus

log = logging.getLogger(__name__)


def _build_icon(color: str = "#3B82F6", size: int = 22) -> QIcon:
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window, event_bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self._window = window
        self._event_bus = event_bus
        self._muted = False

        self.setIcon(_build_icon())
        self.setToolTip("Machine Agent")
        self._build_menu()
        self.activated.connect(self._on_activated)
        log.info("TrayIcon initialized")

    def _build_menu(self) -> None:
        menu = QMenu()

        self._action_open = menu.addAction("Открыть")
        self._action_open.triggered.connect(self._on_open)

        menu.addSeparator()

        self._action_mute = menu.addAction("Выключить микрофон")
        self._action_mute.triggered.connect(self._on_mute_toggle)

        self._action_logs = menu.addAction("Показать логи")
        self._action_logs.triggered.connect(self._on_show_logs)

        menu.addSeparator()

        action_quit = menu.addAction("Выход")
        action_quit.triggered.connect(self._on_quit)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_open()

    def _on_open(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        log.info("Window opened from tray")

    def _on_mute_toggle(self) -> None:
        self._muted = not self._muted
        self._action_mute.setText(
            "Включить микрофон" if self._muted else "Выключить микрофон"
        )
        self._event_bus.publish("tray.mute", {"muted": self._muted})
        log.info(f"Microphone {'muted' if self._muted else 'unmuted'}")

    def _on_show_logs(self) -> None:
        logs_path = Path("logs").resolve()
        try:
            subprocess.Popen(["xdg-open", str(logs_path)])
        except Exception as e:
            log.error(f"Cannot open logs dir: {e}")

    def _on_quit(self) -> None:
        log.info("Quit from tray")
        QApplication.quit()

    @property
    def is_muted(self) -> bool:
        return self._muted
