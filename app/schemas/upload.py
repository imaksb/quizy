from pydantic import BaseModel, Field


class QuizImageUploadResponse(BaseModel):
    """Relative URL path stored on `Question.image_url` and served under `/uploads`."""

    image_url: str = Field(
        ...,
        description="Path like /uploads/<filename>.webp",
        max_length=2048,
    )
