import uuid
from typing import Annotated

from fastapi import Depends

from app.core.dependencies import CurrentUser


async def _get_current_tenant_id(user: CurrentUser) -> uuid.UUID:
    return user.tenant_id


CurrentTenantId = Annotated[uuid.UUID, Depends(_get_current_tenant_id)]
