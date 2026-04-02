from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, engine, sync_database_schema
from app.routers import auth, dashboard, transactions, users

settings = get_settings()
app = FastAPI(title=settings.project_name)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    sync_database_schema()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"] if part != "body")
        errors.append({"field": field or "request", "message": error["msg"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Finance Backend API is running"}


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(transactions.router, prefix=settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
