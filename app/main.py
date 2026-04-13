from fastapi import FastAPI
from app.routers import auth, quizzes, users, utils

app = FastAPI()

app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(users.router)
app.include_router(utils.router)
