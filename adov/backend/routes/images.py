import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Path, UploadFile

from services.activity_log import log_event
from services.auth import get_current_user

logger = logging.getLogger(__name__)
from services.image_embedding.service import (
    ImageMessagePersistenceError,
    ImageProcessingDisabledError,
    ImageUploadValidationError,
    create_pending_image_message,
    process_image_message,
)

router = APIRouter()


@router.post("/api/trips/{trip_id}/messages/image")
async def send_image_message(
    background_tasks: BackgroundTasks,
    trip_id: str = Path(...),
    image: UploadFile = File(...),
    caption: str = Form(default=""),
    current_user: dict = Depends(get_current_user),
):
    image_bytes = await image.read()
    try:
        message = create_pending_image_message(
            trip_id=trip_id,
            sender_id=current_user["uid"],
            sender_name=current_user.get("name", ""),
            caption_text=caption,
            image_bytes=image_bytes,
            image_name=image.filename or "upload.png",
            image_mime_type=image.content_type or "image/png",
        )
    except (ImageUploadValidationError, ImageProcessingDisabledError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImageMessagePersistenceError as exc:
        logger.exception("image upload failed for trip=%s: %s", trip_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    log_event(
        "image_uploaded",
        trip_id=trip_id,
        user_id=current_user["uid"],
        filename=image.filename or "upload.png",
        mime_type=image.content_type or "image/png",
    )
    background_tasks.add_task(
        process_image_message,
        trip_id=trip_id,
        message_id=message["id"],
        image_bytes=image_bytes,
        image_mime_type=image.content_type or "image/png",
    )
    return message
