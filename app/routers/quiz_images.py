import os
import uuid
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from app.core.settings import settings
from app.dependencies.user_validation import CurrentAdminUser
from app.schemas.upload import QuizImageUploadResponse

router = APIRouter(prefix="/quiz-images", tags=["quiz-images"])

ALLOWED_SUFFIX = ".webp"
CHUNK_SIZE = 256 * 1024
WEBP_RIFF = b"RIFF"
WEBP_MAGIC = b"WEBP"

@router.post(
    "",
    response_model=QuizImageUploadResponse,
    summary="Upload a quiz question image (admin only)",
)
async def upload_quiz_image(
    _auth: CurrentAdminUser,
    file: UploadFile = File(...),
) -> QuizImageUploadResponse:
    del _auth

    filename = (file.filename or "").strip().lower()
    if not filename.endswith(ALLOWED_SUFFIX):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {ALLOWED_SUFFIX} uploads are allowed",
        )

    content_type = (file.content_type or "").lower()
    if content_type and not (
        content_type in ("image/webp", "application/octet-stream")
        or content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content-Type must be an image type (WebP expected)",
        )

    try:
        first_chunk = await file.read(CHUNK_SIZE)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error reading file stream"
        ) from e

    if len(first_chunk) < 12 or first_chunk[0:4] != WEBP_RIFF or first_chunk[8:12] != WEBP_MAGIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file data: Must be a valid WebP image",
        )

    upload_dir = Path(settings.QUIZ_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    unique = f"{uuid.uuid4().hex}{ALLOWED_SUFFIX}"
    dest = upload_dir / unique

    written = len(first_chunk)
    if written > settings.QUIZ_UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large",
        )

    try:
        with dest.open("wb") as buffer:
            buffer.write(first_chunk)
            
            # Докачуємо решту
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.QUIZ_UPLOAD_MAX_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File too large",
                    )
                buffer.write(chunk)
                
    except Exception():
        dest.unlink(missing_ok=True)
        raise

    prefix = settings.quiz_uploads_url_base.strip("/")
    url_path = f"/{prefix}/{unique}" if prefix else f"/{unique}"

    return QuizImageUploadResponse(image_url=url_path)
