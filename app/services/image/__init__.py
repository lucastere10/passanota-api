from app.services.image.storage import InvoicePhotoStorage, invoice_photo_storage

__all__ = ["preprocess_image", "InvoicePhotoStorage", "invoice_photo_storage"]


def __getattr__(name: str):
    if name == "preprocess_image":
        from app.services.image.preprocessor import preprocess_image

        return preprocess_image
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
