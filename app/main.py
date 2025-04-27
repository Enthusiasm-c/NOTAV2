__all__ = ["app"]

from fastapi import FastAPI

app = FastAPI(title="Invoice Processing Backend MVP")

# Можно добавить роуты для тестирования (mock GPT):
from .routers import gpt_ocr, gpt_parsing

@app.get("/")
async def root():
    return {"msg": "Invoice Processing System is running"}
