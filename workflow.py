from langgraph.graph import StateGraph, END

from schema import ChatState
from nodes import process_input, ask_system, ask_subsystem, answer, router
from core import OracleCheckpointSaver

# ── Oracle DB 연결 정보 ────────────────────────────────────────────
DB_USER = "your_user"
DB_PASSWORD = "your_password"
DB_DSN = "host:1521/service_name"   # 예: "192.168.0.1:1521/ORCL"
# ──────────────────────────────────────────────────────────────────


def build_graph(checkpointer: OracleCheckpointSaver) -> StateGraph:
    builder = StateGraph(ChatState)

    builder.add_node("process_input", process_input)
    builder.add_node("ask_system", ask_system)
    builder.add_node("ask_subsystem", ask_subsystem)
    builder.add_node("answer", answer)

    builder.set_entry_point("process_input")

    builder.add_conditional_edges(
        "process_input",
        router,
        {
            "ask_system": "ask_system",
            "ask_subsystem": "ask_subsystem",
            "answer": "answer",
        },
    )

    builder.add_edge("ask_system", END)
    builder.add_edge("ask_subsystem", END)
    builder.add_edge("answer", END)

    return builder.compile(checkpointer=checkpointer)


def chat(graph, thread_id: str, user_message: str):
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config,
    )
    # 마지막 assistant 메시지 반환
    for msg in reversed(result["messages"]):
        if hasattr(msg, "role") and msg.role == "assistant":
            return msg.content
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            return msg["content"]
    return ""


if __name__ == "__main__":
    checkpointer = OracleCheckpointSaver(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
    )

    try:
        graph = build_graph(checkpointer)
        thread_id = "session-001"

        print("챗봇 시작. 종료하려면 'exit' 입력\n")

        # 첫 질문
        first_input = input("사용자: ").strip()
        if first_input.lower() == "exit":
            exit()

        # user_query를 첫 입력으로 별도 저장 (process_input에서 처리)
        response = chat(graph, thread_id, first_input)
        print(f"챗봇: {response}\n")

        while True:
            user_input = input("사용자: ").strip()
            if user_input.lower() == "exit":
                break
            response = chat(graph, thread_id, user_input)
            print(f"챗봇: {response}\n")

    finally:
        checkpointer.close()
