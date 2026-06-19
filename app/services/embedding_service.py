from app.config import get_settings

settings = get_settings()


class EmbeddingService:
    def __init__(self) -> None:
        self._model = None

    def load_model(self) -> None:
        if not settings.embeddings_enabled:
            return
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.embedding_model)

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not settings.embeddings_enabled or not texts:
            return []
        self.load_model()
        if self._model is None:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def encode_one(self, text: str) -> list[float] | None:
        results = self.encode([text])
        return results[0] if results else None


embedding_service = EmbeddingService()
