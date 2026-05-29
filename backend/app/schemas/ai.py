from datetime import datetime

from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str


class ConversationOut(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
