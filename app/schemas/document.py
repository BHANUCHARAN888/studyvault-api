from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    title: str
    file_size: int
    created_at: datetime
    subject_id: int | None

    model_config = ConfigDict(from_attributes=True)
