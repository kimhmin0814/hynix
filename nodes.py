from schema import ChatState


def process_input(state: ChatState) -> dict:
    """
    Human 메시지 수를 기준으로 state를 순차적으로 채움.
      1번째 Human 메시지: user_query 저장 (질문)
      2번째 Human 메시지: system 저장
      3번째 Human 메시지: subsystem 저장
    """
    messages = state["messages"]
    last_msg = messages[-1].content

    # Human 메시지만 카운트 (type 또는 role 기준)
    human_count = sum(
        1 for m in messages
        if getattr(m, "type", None) == "human"
        or (isinstance(m, dict) and m.get("role") == "user")
    )

    if human_count == 1:
        return {"user_query": last_msg}
    elif human_count == 2:
        return {"system": last_msg}
    elif human_count == 3:
        return {"subsystem": last_msg}

    return {}


def ask_system(state: ChatState) -> dict:
    return {
        "messages": [{"role": "assistant", "content": "어떤 시스템을 원하나요? (예: gmaster)"}]
    }


def ask_subsystem(state: ChatState) -> dict:
    return {
        "messages": [{"role": "assistant", "content": "어떤 서브시스템을 원하시나요? (예: common)"}]
    }


def answer(state: ChatState) -> dict:
    system = state["system"]
    subsystem = state["subsystem"]
    query = state["user_query"]
    content = f"{system} -> {subsystem} -> {query}에 대해 알려드리겠습니다."
    return {
        "messages": [{"role": "assistant", "content": content}]
    }


def router(state: ChatState) -> str:
    """현재 state를 보고 다음 노드를 결정"""
    if not state.get("system"):
        return "ask_system"
    if not state.get("subsystem"):
        return "ask_subsystem"
    return "answer"
