import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.routes import router
from .auth import router as auth_router
from .config import settings
from .errors import ERROR_CODES, violations

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
app = FastAPI(title="Kutayyib Automation API", version="1.0.0")
origins = settings().cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method in ("POST", "PUT", "DELETE", "PATCH")
        and origin
        and origin not in origins
    ):
        return JSONResponse(
            {"detail": "Origin not allowed", "code": ERROR_CODES["Origin not allowed"]},
            status_code=403,
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    logging.error(
        "Request failed: %s %s (%s)",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        {
            "code": ERROR_CODES[
                "The operation failed. Please try again or contact the administrator."
            ],
            "detail": "The operation failed. Please try again or contact the administrator.",
        },
        status_code=500,
    )


@app.get("/api/health")
def health():
    from sqlalchemy import text

    from .db import engine

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.exception_handler(StarletteHTTPException)
async def public_error(request, exc):
    return JSONResponse(
        {"detail": exc.detail, "code": ERROR_CODES.get(str(exc.detail), "UNKNOWN")},
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(
        {
            "detail": [
                {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                for e in exc.errors()
            ],
            "code": "VALIDATION_ERROR",
            "violations": violations(exc.errors()),
        },
        status_code=422,
    )
