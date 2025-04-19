from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from langchain_sambanova import ChatSambaNovaCloud

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
    def load(self, **kwargs):
        pass


@register_model("gpt-4o")
@register_model("gpt-4o-mini")
@register_model("chatgpt-4o-latest")
@register_model("gpt-4.1")
@register_model("gpt-4.1-mini")
@register_model("gpt-4.5-preview")
class OpenAIModelLoader(BaseModelLoader):
    def load(self, **kwargs):
        allowed_keys = {"model", "temperature", "max_tokens"}
        filtered = {k: v for k, v in kwargs.items() if k in allowed_keys}
        filtered["model"] = self.model_name
        return ChatOpenAI(**filtered)


@register_model("DeepSeek-R1")
class SambaNovaModelLoader(BaseModelLoader):
    def load(self, **kwargs):
        allowed_keys = {"model", "temperature", "max_tokens", "top_k", "top_p"}
        filtered = {k: v for k, v in kwargs.items() if k in allowed_keys}
        filtered["model"] = self.model_name
        return ChatSambaNovaCloud(**filtered)


@register_model("deepseek-v3")
@register_model("deepseek-chat")
class DeepSeekModelLoader(BaseModelLoader):
    def load(self, **kwargs):
        allowed_keys = {"model", "temperature", "max_tokens"}
        filtered = {k: v for k, v in kwargs.items() if k in allowed_keys}
        filtered["model"] = "deepseek-chat"
        return ChatDeepSeek(**filtered)
