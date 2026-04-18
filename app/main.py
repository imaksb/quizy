from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.routers import auth, quizzes, users, utils

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_ADMIN_URL,
        settings.FRONTEND_CLIENT_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(users.router)
app.include_router(utils.router)
