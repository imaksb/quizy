from fastapi import FastAPI
from app.routers import utils, users, auth

app = FastAPI()

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(utils.router)
