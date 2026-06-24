import logging

from fastapi import Header, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import get_settings

logger = logging.getLogger(__name__)


async def verify_cloud_tasks_request(
    request: Request,
    authorization: str | None = Header(default=None),
    x_cloudtasks_queuename: str | None = Header(default=None, alias="X-CloudTasks-QueueName"),
) -> None:
    settings = get_settings()

    if not settings.cloud_tasks_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cloud Tasks is disabled",
        )

    if not x_cloudtasks_queuename:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Cloud Tasks headers",
        )

    allowed_queues = {
        settings.cloud_tasks_invoice_queue,
        settings.cloud_tasks_email_queue,
    }
    if x_cloudtasks_queuename not in allowed_queues:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Cloud Tasks queue",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = authorization.removeprefix("Bearer ").strip()
    audience = str(request.url)

    try:
        id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)
    except Exception as exc:
        logger.warning("Cloud Tasks OIDC verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid task token",
        ) from exc
