"""Compatibility shim: `arq app.workers.tasks.WorkerSettings` is referenced by
.docker/compose*.yml. The worker lives in `app.modules.automation`."""

from app.modules.automation import WorkerSettings

__all__ = ["WorkerSettings"]
