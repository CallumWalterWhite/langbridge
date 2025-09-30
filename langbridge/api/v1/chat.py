from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .datasources import _to_camel

ChatRole = Literal['system', 'user', 'assistant']


class ChatSession(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, frozen=True)


class ChatSessionResponse(BaseModel):
    session_id: str = Field(alias='sessionId')


class ChatMessage(BaseModel):
    id: str
    session_id: str = Field(alias='sessionId')
    role: ChatRole
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, frozen=True)


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessagePair(BaseModel):
    user: ChatMessage
    assistant: ChatMessage


router = APIRouter(prefix='/chat', tags=['chat'])


_CHAT_SESSIONS: Dict[str, ChatSession] = {}
_CHAT_MESSAGES: Dict[str, List[ChatMessage]] = {}


def _ensure_session(session_id: str) -> ChatSession:
    session = _CHAT_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chat session not found')
    return session


def _add_system_message(session_id: str, content: str) -> None:
    message = ChatMessage(
        id=str(uuid4()),
        sessionId=session_id,
        role='system',
        content=content,
    )
    _CHAT_MESSAGES.setdefault(session_id, []).append(message)


def _generate_stub_reply(content: str) -> str:
    snippet = content.strip()
    if len(snippet) > 120:
        snippet = snippet[:117] + '...'
    return (
        "Thanks for sharing! I'm a placeholder assistant right now. "
        f"You said: \"{snippet}\". Replace me with your real model integration."
    )


@router.get('/sessions', response_model=List[ChatSession])
async def list_chat_sessions() -> List[ChatSession]:
    return list(_CHAT_SESSIONS.values())


@router.post('/sessions', response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session() -> ChatSessionResponse:
    identifier = str(uuid4())
    session = ChatSession(id=identifier)
    _CHAT_SESSIONS[identifier] = session
    _CHAT_MESSAGES[identifier] = []
    _add_system_message(identifier, 'This is a stub conversation. Connect your LLM to generate real responses.')
    return ChatSessionResponse(session_id=identifier)


@router.get('/sessions/{session_id}/messages', response_model=List[ChatMessage])
async def list_chat_messages(session_id: str) -> List[ChatMessage]:
    _ensure_session(session_id)
    return list(_CHAT_MESSAGES.get(session_id, []))


@router.post('/sessions/{session_id}/messages', response_model=ChatMessagePair, status_code=status.HTTP_201_CREATED)
async def create_chat_message(session_id: str, payload: ChatMessageCreate) -> ChatMessagePair:
    if not payload.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Message content is required')

    _ensure_session(session_id)

    user_message = ChatMessage(
        id=str(uuid4()),
        sessionId=session_id,
        role='user',
        content=payload.content.strip(),
    )
    _CHAT_MESSAGES.setdefault(session_id, []).append(user_message)

    assistant_message = ChatMessage(
        id=str(uuid4()),
        sessionId=session_id,
        role='assistant',
        content=_generate_stub_reply(payload.content),
    )
    _CHAT_MESSAGES[session_id].append(assistant_message)

    return ChatMessagePair(user=user_message, assistant=assistant_message)
