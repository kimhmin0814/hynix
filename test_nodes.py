"""
Oracle DB 없이 노드 로직만 검증하는 테스트 스크립트
"""
from langchain_core.messages import HumanMessage
from schema import ChatState
from nodes import process_input, ask_system, ask_subsystem, answer, router


def simulate(turns: list[str]):
    """대화 턴을 순서대로 시뮬레이션"""
    state: ChatState = {
        "messages": [],
        "system": None,
        "subsystem": None,
        "user_query": None,
    }

    for user_text in turns:
        print(f"사용자: {user_text}")

        # 사용자 메시지 추가
        state["messages"].append(HumanMessage(content=user_text))

        # process_input → state 업데이트
        update = process_input(state)
        state.update(update)

        # router → 다음 노드 결정
        next_node = router(state)

        # 해당 노드 실행
        if next_node == "ask_system":
            result = ask_system(state)
        elif next_node == "ask_subsystem":
            result = ask_subsystem(state)
        else:
            result = answer(state)

        bot_msg = result["messages"][0]["content"]
        print(f"챗봇: {bot_msg}")
        print(f"  [state] user_query={state['user_query']}, system={state['system']}, subsystem={state['subsystem']}")
        print()


if __name__ == "__main__":
    simulate([
        "설비 삭제방법에 대해 알려줘",
        "gmaster",
        "common",
    ])
