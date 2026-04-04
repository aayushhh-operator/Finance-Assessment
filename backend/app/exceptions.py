from __future__ import annotations


class AppError(Exception):
    def __init__(
        self,
        detail: str | dict[str, object],
        *,
        status_code: int,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(str(detail))
        self.detail = detail
        self.status_code = status_code
        self.headers = headers or {}


class BadRequestError(AppError):
    def __init__(self, detail: str | dict[str, object]) -> None:
        super().__init__(detail, status_code=400)


class AuthenticationError(AppError):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            detail,
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(detail, status_code=403)


class NotFoundError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=404)


class ConflictError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=400)
