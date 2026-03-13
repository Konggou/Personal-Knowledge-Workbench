from pydantic import BaseModel, Field


class SessionMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=6000)
    deep_research: bool = False


class SessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
