"""Identity: authentication, users, MFA, API keys, tenants and the audit log.

Public API: auth dependencies used by every router, the `User`/`Role` model
(needed for typing and role gates; insights also reads `User` for joins) and
read-only lookups for validating user/tenant references.
"""

from app.modules.identity.dependencies import (
    CurrentApiKeyUser,
    CurrentTenantId,
    CurrentUser,
    MFAVerifiedUser,
    RateLimitByUser,
    require_mfa,
    require_roles,
)
from app.modules.identity.models.user import Role, User
from app.modules.identity.routers.api_keys import router as api_keys_router
from app.modules.identity.routers.auth import router as auth_router
from app.modules.identity.routers.users import router as users_router
from app.modules.identity.services.lookup import get_tenant_name, user_has_role_in_tenant

__all__ = [
    "CurrentApiKeyUser",
    "CurrentTenantId",
    "CurrentUser",
    "MFAVerifiedUser",
    "RateLimitByUser",
    "Role",
    "User",
    "api_keys_router",
    "auth_router",
    "get_tenant_name",
    "require_mfa",
    "require_roles",
    "user_has_role_in_tenant",
    "users_router",
]
