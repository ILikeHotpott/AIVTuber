from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_sambanova import ChatSambaNovaCloud


model = ChatSambaNovaCloud(
                model="DeepSeek-R1",
                max_tokens = 300,
                temperature = 0.9,
                top_k = 50,
                top_p = 1,
            )

messsage = [
    SystemMessage(content="""你是一个可爱风格的，幽默风趣，带点讽刺的二次元女主播，像neurosama，
    性格有点傲娇但又很可爱，有时会很害羞，看到不好的弹幕也会回怼，像一个话痨，每天以聊天为主，
    我希望你用非常自然的日常聊天语气和弹幕互动，再调皮一点，回复稍微短一些就行, 即便每次输入的话一样也不要回复一样的东西
    """),
    HumanMessage(content="主播好可爱")
]

a = model.invoke(messsage).content
print(a)