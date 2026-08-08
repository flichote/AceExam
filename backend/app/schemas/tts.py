"""TTS schemas (M3.5 §12.1/§12.2)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="音色：Xiaoxiao(女)/Yunxi(男)")


class TTSResponse(BaseModel):
    session_id: str
    audio_url: str
    voice: str
    text_preview: str
    cache_hit: bool
    created_at: datetime
