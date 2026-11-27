"""Shifts: shifts, end-of-shift reports and per-shift chat (REST + WebSocket).

Public API: `get_shift_in_tenant` (used by payroll to liquidate a shift) and
`Shift`/`ShiftStatus` (read-only ORM access for payroll and insights).
"""

from app.modules.shifts.models.shift import Shift, ShiftStatus
from app.modules.shifts.routers.chat import router as chat_router
from app.modules.shifts.routers.shift_reports import router as shift_reports_router
from app.modules.shifts.routers.shifts import router as shifts_router
from app.modules.shifts.services.shift import get_shift_in_tenant

__all__ = [
    "Shift",
    "ShiftStatus",
    "chat_router",
    "get_shift_in_tenant",
    "shift_reports_router",
    "shifts_router",
]
