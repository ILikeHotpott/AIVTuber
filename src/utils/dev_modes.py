from dotenv import load_dotenv
import os

load_dotenv()

ENV_MODE = os.getenv("ENV_MODE", "prod").lower()


def is_dev(): return ENV_MODE == "dev"


def is_prod(): return ENV_MODE == "prod"


def is_test(): return ENV_MODE == "test"
