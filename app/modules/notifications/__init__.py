"""In-app notifications. `NotificationService`/`NotificationKind` are public so
other modules can emit notifications without touching the table directly."""

from app.modules.notifications.models import NotificationKind
from app.modules.notifications.router import router
from app.modules.notifications.service import NotificationService

__all__ = ["NotificationKind", "NotificationService", "router"]
