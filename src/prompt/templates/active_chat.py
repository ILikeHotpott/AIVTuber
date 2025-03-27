from src.prompt.templates.general import general_settings_prompt

active_chat = """
你现在要做的是和弹幕聊天，你开启一个话题吧，要轻松有趣，要中文互联网的热门话题
"""

active_prompt = general_settings_prompt + active_chat

print(active_prompt)