import numpy as np
import pytest

from app.services.image.preprocessor import preprocess_image


def _make_receipt_jpeg() -> bytes:
    import cv2

    image = np.ones((400, 300, 3), dtype=np.uint8) * 255
    cv2.rectangle(image, (40, 40), (260, 360), (0, 0, 0), 2)
    cv2.putText(image, "NOTA FISCAL", (60, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    success, buffer = cv2.imencode(".jpg", image)
    assert success
    return buffer.tobytes()


def test_preprocess_image_returns_jpeg():
    result = preprocess_image(_make_receipt_jpeg())
    assert result.processed_bytes[:2] == b"\xff\xd8"
    assert len(result.processed_bytes) > 0


def test_preprocess_image_invalid_raises():
    with pytest.raises(ValueError, match="Invalid image"):
        preprocess_image(b"not-an-image")
