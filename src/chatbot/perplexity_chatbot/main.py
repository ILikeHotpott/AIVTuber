import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatPerplexity
from langchain_core.prompts import ChatPromptTemplate
load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

chat = ChatPerplexity(temperature=0.8, pplx_api_key=PERPLEXITY_API_KEY, model="sonar")

system = "You are event describer"
human = "{input}"
prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])

chain = prompt | chat
response = chain.invoke({"input": "给我找找最近中文互联网上爆火的梗和新闻事件，最近三天的，话题度高的，娱乐性强的"})
print(response.content)