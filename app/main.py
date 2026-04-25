import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.settings import settings
from app.routers import auth, quizzes, users, utils

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
swagger_security = HTTPBasic()


def verify_swagger_access(
    credentials: HTTPBasicCredentials = Depends(swagger_security),
) -> None:
    valid_username = secrets.compare_digest(
        credentials.username,
        settings.OPENAPI_SWAGGER_USERNAME,
    )
    valid_password = secrets.compare_digest(
        credentials.password,
        settings.OPENAPI_SWAGGER_PASSWORD,
    )
    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Swagger credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_json(_: None = Depends(verify_swagger_access)):
    return get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )


@app.get("/docs", include_in_schema=False)
async def swagger_ui(_: None = Depends(verify_swagger_access)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - Swagger UI",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc(_: None = Depends(verify_swagger_access)):
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - ReDoc",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_origin_regex=settings.CORS_ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(users.router)
app.include_router(utils.router)
