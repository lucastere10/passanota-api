from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreprocessResult:
    original_bytes: bytes
    processed_bytes: bytes
    preprocess_skipped: bool
    content_type: str = "image/jpeg"
