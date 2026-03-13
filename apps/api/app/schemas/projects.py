from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=240)
    default_external_policy: Literal["local_only", "allow_external"] = "allow_external"
