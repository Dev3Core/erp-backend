class ServiceError(Exception):
    """Domain error raised by service layer; mapped to HTTPException in routes."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class NotFoundError(ServiceError):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail, status_code=404)


class ForbiddenError(ServiceError):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail, status_code=403)


class ConflictError(ServiceError):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(detail, status_code=409)


class ValidationError(ServiceError):
    def __init__(self, detail: str = "Invalid input"):
        super().__init__(detail, status_code=422)
