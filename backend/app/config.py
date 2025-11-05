from pathlib import Path
from typing import Any

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

  gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
  backend_port: int = Field(8000, alias="BACKEND_PORT")
  static_dir: Path = Field(Path("./static"), alias="STATIC_DIR")
  frame_sample_rate: int = Field(2, alias="FRAME_SAMPLE_RATE")
  max_video_duration: int = Field(300, alias="MAX_VIDEO_DURATION")

  @validator("static_dir", pre=True)
  def _ensure_path(cls, value: Any) -> Path:
    return Path(value).resolve()


settings = Settings()


def ensure_directories() -> None:
  settings.static_dir.mkdir(parents=True, exist_ok=True)

