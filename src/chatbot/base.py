from abc import ABC, abstractmethod

MODEL_REGISTRY = {}


def register_model(name: str):
    def decorator(cls):
        MODEL_REGISTRY[name.lower()] = cls
        return cls

    return decorator


class BaseModelLoader(ABC):
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def load(self):
        pass
