from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import asyncio

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/process", response_class=HTMLResponse)
async def process(request: Request):
    print(request.body)
    await asyncio.sleep(5)
    return '{"tags": ["hello"], "keywords": ["sosi", "bibu", "privki"]}'
