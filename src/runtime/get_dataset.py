from datasets import load_dataset

# 加载数据集
dataset = load_dataset("neifuisan/Neuro-sama-QnA")

# 提取问答数据并保存成txt格式
with open("Neuro-sama-QnA.txt", "w", encoding="utf-8") as f:
    for item in dataset["train"]:
        instruction = item.get("instruction", "").strip()
        output = item.get("output", "").strip()
        if instruction and output:
            f.write(f"Q: {instruction}\nA: {output}\n\n")
