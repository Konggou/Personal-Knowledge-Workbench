from pydantic import BaseModel, Field


class LLMSettingsView(BaseModel):
    base_url: str
    model: str
    timeout_seconds: float
    has_api_key: bool
    api_key_preview: str | None = None


class EmbeddingSettingsView(BaseModel):
    model_name: str
    dimension: int
    allow_downloads: bool


class RerankerSettingsView(BaseModel):
    backend: str
    model_name: str
    remote_url: str
    remote_timeout_seconds: float
    top_n: int
    allow_downloads: bool


class ModelSettingsResponse(BaseModel):
    llm: LLMSettingsView
    embedding: EmbeddingSettingsView
    reranker: RerankerSettingsView


class LLMSettingsUpdate(BaseModel):
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    timeout_seconds: float = Field(gt=0)
    api_key: str | None = None
    clear_api_key: bool = False


class EmbeddingSettingsUpdate(BaseModel):
    model_name: str = Field(min_length=1)
    dimension: int = Field(gt=0)
    allow_downloads: bool


class RerankerSettingsUpdate(BaseModel):
    backend: str = Field(pattern="^(rule|cross_encoder_local|cross_encoder_remote)$")
    model_name: str = ""
    remote_url: str = ""
    remote_timeout_seconds: float = Field(gt=0)
    top_n: int = Field(gt=0)
    allow_downloads: bool


class ModelSettingsUpdateRequest(BaseModel):
    llm: LLMSettingsUpdate
    embedding: EmbeddingSettingsUpdate
    reranker: RerankerSettingsUpdate
