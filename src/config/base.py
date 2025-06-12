from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    lang: str = "zh"
