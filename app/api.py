from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent_service import stream_run

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatStreamRequest(BaseModel):
    message: str
    thread_id: str | None = None
    max_turns: int = 30


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream(req: ChatStreamRequest, request: Request):
    return StreamingResponse(
        stream_run(
            agent=None,
            user_input=req.message,
            thread_id=req.thread_id,
            max_turns=req.max_turns,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
        },
    )