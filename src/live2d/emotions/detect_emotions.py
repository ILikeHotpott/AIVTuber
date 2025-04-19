from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import json
from time import time
from dotenv import load_dotenv

load_dotenv()

# 初始化模型
llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0)

# Prompt 模板（注意！示例 JSON 中的花括号要双写）
prompt_template = PromptTemplate.from_template("""
你是一个判断情绪的高手，现在要分析一个女孩子说的话的情绪，并给出四种情绪的评分，分数加起来为1。
情绪类别包括：normal, shy, joy, anger，由高到低输出
请只输出 JSON 格式的结果，形如：
{{
  "normal": 0.30,
  "shy": 0.2,
  "joy": 0.25,
  "anger": 0.25
}}

句子："{sentence}"
""")

# 组合成链
emotion_chain = prompt_template | llm


# 分析函数
def predict_emotion(sentence: str) -> dict:
    try:
        result = emotion_chain.invoke({"sentence": sentence})
        return json.loads(result.content)
    except Exception as e:
        print("解析失败:", e)
        return {}


# 示例
if __name__ == "__main__":
    total_start = time()

    sentence = "这是一种非常复杂的情感"
    start = time()
    result = predict_emotion(sentence)
    end = time()
    sorted_dict = dict(sorted(result.items(), key=lambda item: item[1], reverse=True))
    print(sorted_dict)
    print(f"模型调用耗时: {end - start:.2f} 秒")
    print(f"总程序耗时: {time() - total_start:.2f} 秒")
