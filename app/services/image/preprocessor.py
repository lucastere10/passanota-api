import cv2
import numpy as np

from app.services.image.types import PreprocessResult

MAX_DIMENSION = 2000
JPEG_QUALITY = 85


def _order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = points.sum(axis=1)
    rect[0] = points[np.argmin(s)]
    rect[2] = points[np.argmax(s)]
    diff = np.diff(points, axis=1)
    rect[1] = points[np.argmin(diff)]
    rect[3] = points[np.argmax(diff)]
    return rect


def _find_document_contour(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    image_area = image.shape[0] * image.shape[1]
    for contour in contours[:10]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and cv2.contourArea(contour) > image_area * 0.1:
            return approx.reshape(4, 2).astype(np.float32)
    return None


def _warp_perspective(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    rect = _order_points(points)
    width_a = np.linalg.norm(rect[2] - rect[3])
    width_b = np.linalg.norm(rect[1] - rect[0])
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(rect[1] - rect[2])
    height_b = np.linalg.norm(rect[0] - rect[3])
    max_height = int(max(height_a, height_b))

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def _resize_max_dimension(image: np.ndarray, max_dim: int = MAX_DIMENSION) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_dim:
        return image
    scale = max_dim / longest
    new_size = (int(width * scale), int(height * scale))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def _encode_jpeg(image: np.ndarray, quality: int = JPEG_QUALITY) -> bytes:
    success, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        raise ValueError("Failed to encode image as JPEG")
    return buffer.tobytes()


def preprocess_image(image_bytes: bytes) -> PreprocessResult:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid image data")

    contour = _find_document_contour(image)
    if contour is not None:
        warped = _warp_perspective(image, contour)
        resized = _resize_max_dimension(warped)
        processed = _encode_jpeg(resized)
        return PreprocessResult(
            original_bytes=image_bytes,
            processed_bytes=processed,
            preprocess_skipped=False,
        )

    resized = _resize_max_dimension(image)
    processed = _encode_jpeg(resized)
    return PreprocessResult(
        original_bytes=image_bytes,
        processed_bytes=processed,
        preprocess_skipped=True,
    )
