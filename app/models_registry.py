"""Imports every module's ORM models so they register on the shared `Base`.

Import this before configuring mappers or reading `Base.metadata`
(`app.main`, `alembic/env.py`). Cross-module `relationship()` targets are
strings, so all models must be loaded for SQLAlchemy to resolve them.
"""

from app.modules.automation.models import AutomationJob
from app.modules.identity.models.api_key import ApiKey
from app.modules.identity.models.audit_log import AuditLog
from app.modules.identity.models.tenant import Tenant
from app.modules.identity.models.user import User
from app.modules.notifications.models import Notification
from app.modules.payroll.models.exchange_rate import ExchangeRate
from app.modules.payroll.models.liquidation import Liquidation
from app.modules.payroll.models.monitor_salary import MonitorSalary
from app.modules.payroll.models.salary_advance_request import SalaryAdvanceRequest
from app.modules.payroll.models.split_config import SplitConfig
from app.modules.shifts.models.chat_message import ChatMessage
from app.modules.shifts.models.shift import Shift
from app.modules.shifts.models.shift_report import ShiftReport
from app.modules.studio.models.bio_template import BioTemplate
from app.modules.studio.models.macro import Macro
from app.modules.studio.models.room import Room
from app.modules.studio.models.tag import Tag
from app.modules.studio.models.technical_sheet import TechnicalSheet
from app.shared.orm import Base

__all__ = [
    "ApiKey",
    "AuditLog",
    "AutomationJob",
    "Base",
    "BioTemplate",
    "ChatMessage",
    "ExchangeRate",
    "Liquidation",
    "Macro",
    "MonitorSalary",
    "Notification",
    "Room",
    "SalaryAdvanceRequest",
    "Shift",
    "ShiftReport",
    "SplitConfig",
    "Tag",
    "TechnicalSheet",
    "Tenant",
    "User",
]
