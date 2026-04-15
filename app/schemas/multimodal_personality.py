"""Schemas for the standalone multimodal personality analysis API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "running", "completed", "failed"]


class MultimodalUploadRequest(BaseModel):
    """Upload metadata for a multimodal personality analysis task."""

    video_path: str = Field(..., description="Local path or uploaded path of the source video.")
    session_id: Optional[int] = Field(default=None, description="Optional link to an assessment session.")
    original_filename: Optional[str] = Field(default=None, description="Original filename if the video was uploaded.")


class MultimodalRunRequest(BaseModel):
    """Run request for a prepared multimodal personality task."""

    task_id: str = Field(..., description="Task identifier returned by the upload endpoint.")
    force_restart: bool = Field(default=False, description="Whether to restart a completed or failed task.")


class BigFiveScores(BaseModel):
    """Big Five personality score payload."""

    openness: float = 0.0
    conscientiousness: float = 0.0
    extraversion: float = 0.0
    agreeableness: float = 0.0
    neuroticism: float = 0.0


class MultimodalTaskResponse(BaseModel):
    """Common task response shape for the multimodal API."""

    task_id: str
    status: TaskStatus
    message: str
    video_path: str
    session_id: Optional[int] = None
    model_version: str = "scaffold-v1"
    scores: Optional[BigFiveScores] = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MultimodalHealthResponse(BaseModel):
    """Health response for the multimodal subsystem."""

    status: Literal["ok"]
    module: str
    model_ready: bool
    task_count: int
    system_tools: dict[str, bool] = Field(default_factory=dict)
