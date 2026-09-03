import logging

logger = logging.getLogger(__name__)


class ModelManager:
    _instances = {}

    @classmethod
    def get(cls, model_key: str, loader_fn: callable):
        if model_key not in cls._instances:
            logger.info(f"Loading model: {model_key}")
            cls._instances[model_key] = loader_fn()
            logger.info(f"Model loaded: {model_key}")
        return cls._instances[model_key]

    @classmethod
    def clear(cls):
        cls._instances = {}
