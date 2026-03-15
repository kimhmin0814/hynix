from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]  # 대화 이력 (append 방식)
    system: Optional[str]                    # 예: gmaster
    subsystem: Optional[str]                 # 예: common
    user_query: Optional[str]                # 원래 사용자 질문
