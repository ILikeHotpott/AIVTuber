import os
import openai
import numpy as np
from numpy.linalg import norm

api_key = os.getenv("OPENAI_API_KEY")



# 设置 API Key
client = openai.OpenAI(api_key=api_key)

# 示例弹幕
comments = [
    "丸辣，要赶不上了[流泪]",
    "我要训练一支bt大军，小满开播了就狂舔",
    "小满高中天天给我擦身体乳[流泪]",
    "小满满月快乐喵",
    "哈哈哈哈",
    "真的假的？这太离谱了吧！",
    "小满今天又被喷了",
    "有人懂吗？这是不是翻车了？",
    "这是什么情况？？？",
    "今天梅西获得了世界杯冠军，你怎么看"
]


# 获取文本嵌入向量
def get_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    return np.array(response.data[0].embedding)  # 转为 numpy 数组


# 定义“话题性”文本
topic_text = "热门话题、争议、讨论、爆炸性、震惊、重要、值得讨论"
query_embedding = get_embedding(topic_text)

# 获取所有弹幕的向量
comment_embeddings = [get_embedding(c) for c in comments]


# 计算余弦相似度
def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))


# 计算每条弹幕的相似度
similarities = [cosine_similarity(query_embedding, emb) for emb in comment_embeddings]

# 根据相似度排序
ranked_comments = sorted(zip(comments, similarities), key=lambda x: x[1], reverse=True)

# 选出最有话题度的 3 条弹幕
top_comments = [c[0] for c in ranked_comments[:3]]
print("最有话题度的弹幕:", top_comments)
