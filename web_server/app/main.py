from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import json
import asyncio
import uuid
import os


from aio_pika import Message, connect

from typing import MutableMapping

from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractIncomingMessage,
    AbstractQueue,
)

HOST = os.environ["RABBITMQ_HOST"]
USERNAME = os.environ["RABBITMQ_USERNAME"]
PASSWORD = os.environ["RABBITMQ_PASSWORD"]


class TextRequest(BaseModel):
    text: str


class TextResponse(BaseModel):
    tag: str
    keywords: list[str] = []


class TextRequestBatch(BaseModel):
    texts: list[str]


class TextResponseBatch(BaseModel):
    response: list[TextResponse]


class FibonacciRpcClient:
    connection: AbstractConnection

    channel: AbstractChannel

    callback_queue: AbstractQueue

    def __init__(self) -> None:
        self.futures: MutableMapping[str, asyncio.Future] = {}

    async def connect(self) -> "FibonacciRpcClient":
        self.connection = await connect(f"amqp://{USERNAME}:{PASSWORD}@{HOST}/")

        self.channel = await self.connection.channel()

        self.callback_queue = await self.channel.declare_queue(exclusive=True)

        await self.callback_queue.consume(self.on_response, no_ack=True)

        return self

    async def on_response(self, message: AbstractIncomingMessage) -> None:
        if message.correlation_id is None:
            print(f"Bad message {message!r}")

            return

        future: asyncio.Future = self.futures.pop(message.correlation_id)

        future.set_result(message.body)

    async def call(self, n: str):
        correlation_id = str(uuid.uuid4())

        loop = asyncio.get_running_loop()

        future = loop.create_future()

        self.futures[correlation_id] = future

        await self.channel.default_exchange.publish(
            Message(
                str(n).encode(),
                content_type="text/plain",
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
            ),
            routing_key="rpc_queue",
        )

        return await future


app = FastAPI(title="no tox tribe", description="API теггирования текстов")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def app_startup():
    global fibonacci_rpc
    fibonacci_rpc = await FibonacciRpcClient().connect()


@app.get("/", tags=["HTML"], response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/process", tags=["API"], response_model=TextResponse)
async def process(request: TextRequest):
    req_body = request.model_dump_json()
    response = await fibonacci_rpc.call(req_body)
    return response.decode()


@app.post("/processBatch", tags=["API"], response_model=TextResponseBatch)
async def processBatch(request: TextRequestBatch):
    responses = []
    for req in request.dict()["texts"]:
        mini_req = {"text": req}
        responses.append(
            json.loads((await fibonacci_rpc.call(json.dumps(mini_req))).decode())
        )
    return TextResponseBatch(response=responses)
