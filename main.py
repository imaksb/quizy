from fastapi import FastAPI
from app.routers import utils

app = FastAPI()

app.include_router(utils.router)
