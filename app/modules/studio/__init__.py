"""Studio: rooms, tags, technical sheets, bio templates and macros.

Public API: `Platform` (shared enum), `room_is_active_in_tenant` (used by
shifts), `MacroService`/`MacroResponse` (used by the extension) and `Room`
(read-only ORM access for insights aggregates).
"""

from app.modules.studio.models.room import Platform, Room
from app.modules.studio.routers.bio_templates import router as bio_templates_router
from app.modules.studio.routers.macros import router as macros_router
from app.modules.studio.routers.rooms import router as rooms_router
from app.modules.studio.routers.tags import router as tags_router
from app.modules.studio.routers.technical_sheets import router as technical_sheets_router
from app.modules.studio.schemas.macro import MacroResponse
from app.modules.studio.services.macro import MacroService
from app.modules.studio.services.room import room_is_active_in_tenant

__all__ = [
    "MacroResponse",
    "MacroService",
    "Platform",
    "Room",
    "bio_templates_router",
    "macros_router",
    "room_is_active_in_tenant",
    "rooms_router",
    "tags_router",
    "technical_sheets_router",
]
