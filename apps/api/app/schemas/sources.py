from pydantic import BaseModel, HttpUrl


class WebSourceCreateRequest(BaseModel):
    url: HttpUrl
    session_id: str | None = None


class WebSourceUpdateRequest(BaseModel):
    url: HttpUrl
