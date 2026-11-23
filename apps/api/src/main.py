import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import settings
from src.database import engine, Base, init_db
from src.redis_client import init_redis, close_redis
from src.api.v1.router import v1_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing %s in %s mode", settings.APP_NAME, settings.ENVIRONMENT)
    # Initialize DB tables (with development fallback if postgres is offline)
    await init_db()
    # Initialize Redis connection
    await init_redis()
    yield
    # Shutdown
    logger.info("Shutting down %s", settings.APP_NAME)
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="Authentication and Codebase Intelligence API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Trace-Id", "X-CSRF-Token"]
)


# 2. Security Headers & Request Correlation Middleware
@app.middleware("http")
async def security_and_correlation_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.trace_id = trace_id

    response = await call_next(request)

    response.headers["X-Request-Id"] = request_id
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# 3. Standardized Error Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "HTTP_ERROR")
        message = detail.get("message", str(detail))
        details = detail.get("details", {})
    else:
        code = "HTTP_ERROR"
        message = str(detail)
        details = {}

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "retryable": exc.status_code in [429, 502, 503, 504],
                "trace_id": trace_id
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Invalid request parameters",
                "details": {"errors": exc.errors()},
                "retryable": False,
                "trace_id": trace_id
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    logger.exception("Unhandled server exception (trace_id=%s): %s", trace_id, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL",
                "message": "An unexpected server error occurred",
                "details": {},
                "retryable": True,
                "trace_id": trace_id
            }
        }
    )


# 4. Include Routers
app.include_router(v1_router)


# 5. Health Probes
@app.get("/healthz", tags=["Operations"])
async def healthz():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/readyz", tags=["Operations"])
async def readyz():
    return {"status": "ready"}
