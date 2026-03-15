from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver  # 테스트용 (운영 시 OracleCheckpointSaver로 교체)
from workflow import build_graph

graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer)
    yield


app = FastAPI(
    title="하이닉스 챗봇 API",
    description="시스템/서브시스템 기반 매뉴얼 조회 챗봇",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    thread_id: str  # 세션 ID (같은 대화는 같은 thread_id 사용)
    message: str    # 사용자 입력

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"thread_id": "session-001", "message": "설비 삭제방법에 대해 알려줘"}
            ]
        }
    }


class ChatResponse(BaseModel):
    thread_id: str
    bot_message: str
    state: dict


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    result = graph.invoke(
        {"messages": [{"role": "user", "content": req.message}]},
        config,
    )

    # invoke 후 get_state로 전체 state 가져와서 마지막 AI 메시지 추출
    config = {"configurable": {"thread_id": req.thread_id}}
    snapshot = graph.get_state(config)
    all_messages = snapshot.values.get("messages", [])

    bot_msg = ""
    for msg in reversed(all_messages):
        if getattr(msg, "type", None) == "ai":
            bot_msg = msg.content
            break

    state_values = snapshot.values
    return ChatResponse(
        thread_id=req.thread_id,
        bot_message=bot_msg,
        state={
            "user_query": state_values.get("user_query"),
            "system": state_values.get("system"),
            "subsystem": state_values.get("subsystem"),
        },
    )


@app.get("/state/{thread_id}")
def get_state(thread_id: str):
    """현재 대화 state 확인용"""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if not snapshot or not snapshot.values:
        return {"thread_id": thread_id, "state": None, "message": "해당 thread_id의 state가 없습니다."}
    values = snapshot.values
    return {
        "thread_id": thread_id,
        "state": {
            "user_query": values.get("user_query"),
            "system": values.get("system"),
            "subsystem": values.get("subsystem"),
            "message_count": len(values.get("messages", [])),
        }
    }


@app.delete("/chat/{thread_id}")
def reset_session(thread_id: str):
    """대화 초기화 (새 세션 시작하려면 새 thread_id 사용하거나 여기서 리셋)"""
    # Oracle checkpointer는 thread_id로 구분되므로 새 thread_id 사용 권장
    return {"message": f"{thread_id} 세션을 초기화하려면 새로운 thread_id를 사용하세요."}


@app.get("/health")
def health():
    return {"status": "ok"}
