from datetime import date
from src.prompt.templates.general import general_settings_prompt_english


class PromptBuilder:

    def __init__(self):
        self.general_prompt = general_settings_prompt_english

    def prompt_with_audience(self):
        today = str(date.today())
        return today + self.general_prompt


# 获取今天的日期
today = date.today()

print(today)
