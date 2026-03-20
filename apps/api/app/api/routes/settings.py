from fastapi import APIRouter

from app.schemas.settings import ModelSettingsUpdateRequest
from app.services.settings_service import SettingsService

router = APIRouter()
service = SettingsService()


@router.get("/settings/models")
def get_model_settings() -> dict:
    return {"item": service.get_model_settings()}


@router.put("/settings/models")
def update_model_settings(payload: ModelSettingsUpdateRequest) -> dict:
    return {"item": service.update_model_settings(payload)}
