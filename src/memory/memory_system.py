from langchain.memory import ConversationBufferWindowMemory
from langchain.memory import ConversationSummaryBufferMemory
from langchain_chroma import Chroma
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain.schema import Document
from langchain_openai.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain_core.runnables import RunnableWithMessageHistory

from langchain.prompts import PromptTemplate
from datetime import datetime, timedelta
import json
import os
import uuid


class VTuberMemorySystem:
    def __init__(self, vtuber_name, llm_model="gpt-4o"):
        # 基础信息
        self.vtuber_name = vtuber_name
        self.llm = ChatOpenAI(model_name=llm_model)
        self.embeddings = OpenAIEmbeddings()
        self.stream_id = self._generate_stream_id()

        # 短期记忆 - 最近 50 条对话
        self.short_term_memory = ConversationBufferWindowMemory(
            k=50,
            memory_key="short_term_chat_history",
            return_messages=True
        )

        # 中期记忆 - 当前直播摘要
        self.mid_term_memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=4000,
            memory_key="current_stream_memory",
            return_messages=True
        )

        # 长期记忆 - 人设与梗
        # 1. 人设向量数据库
        self.character_vectordb = Chroma(
            collection_name=f"{vtuber_name}_character",
            embedding_function=self.embeddings,
            persist_directory=f"./memory_db/{vtuber_name}/character"
        )
        self.character_retriever = self.character_vectordb.as_retriever(search_kwargs={"k": 3})

        # 2. 梗与热点向量数据库
        self.memes_vectordb = Chroma(
            collection_name=f"{vtuber_name}_memes",
            embedding_function=self.embeddings,
            persist_directory=f"./memory_db/{vtuber_name}/memes"
        )
        self.memes_retriever = self.memes_vectordb.as_retriever(search_kwargs={"k": 3})

        # 3. 用户向量数据库（新增）
        #    用于把对话次数较多的用户信息写入长期记忆
        self.user_vectordb = Chroma(
            collection_name=f"{vtuber_name}_users",
            embedding_function=self.embeddings,
            persist_directory=f"./memory_db/{vtuber_name}/users"
        )

        # 礼物记忆
        self.gift_memory = {}
        self.load_gift_memory()

        # 事件记忆（仅一个活跃事件）
        self.active_event_id = None  # 当前活跃事件 ID（如果有的话）
        # 不再维护一个大的 event_memory 字典，而是每个事件单独存文件

        # 用户实体记忆
        self.entity_memory = {}
        self.load_entity_memory()

        # 直播场次记录
        self.stream_history = {}
        self.load_stream_history()

        # 初始化当前直播信息
        self.init_current_stream()

        # 对话链
        self.conversation_chain = self._create_conversation_chain()

    # =========== 基础方法 ===========

    def _generate_stream_id(self):
        """生成当前直播的唯一ID"""
        return f"stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _create_conversation_chain(self):
        """创建带有记忆的对话链"""
        template = """
你是一个名为{vtuber_name}的AI VTuber。请根据以下信息进行回复。

短期记忆（最近50条）:
{short_term_chat_history}

中期记忆（本场直播摘要）:
{current_stream_memory}

长期记忆 - 人设:
{character_info}

长期记忆 - 梗和热点:
{relevant_memes}

用户信息:
{entity_info}

礼物信息:
{gift_info}

用户: {input}

{vtuber_name}:
"""
        prompt = PromptTemplate(
            input_variables=[
                "vtuber_name",
                "short_term_chat_history",
                "current_stream_memory",
                "character_info",
                "relevant_memes",
                "entity_info",
                "gift_info",
                "input"
            ],
            template=template
        )

        return ConversationChain(
            llm=self.llm,
            prompt=prompt,
            verbose=False,
            memory={}
        )

    # =========== 直播场次记录 ===========

    def init_current_stream(self):
        """初始化当前直播在历史记录中的条目"""
        if self.stream_id not in self.stream_history:
            self.stream_history[self.stream_id] = {
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "viewer_count": 0,
                "interaction_count": 0,
                "total_gifts": 0,
                "top_gifters": [],
                "summary": ""
                # 其他需要的字段可自行添加
            }
            self.save_stream_history()

            # 重置当前直播用户送礼金额
            for user_id in self.gift_memory:
                self.gift_memory[user_id]["current_livestream_money"] = 0
            self.save_gift_memory()

    def end_stream(self):
        """结束当前直播并生成简单总结。"""
        # 更新直播结束时间
        self.stream_history[self.stream_id]["end_time"] = datetime.now().isoformat()

        # 计算本场礼物总额和前三名
        total_gifts = 0
        gifters = []
        for user_id, data in self.gift_memory.items():
            current_stream_money = data.get("current_livestream_money", 0)
            total_gifts += current_stream_money
            if current_stream_money > 0:
                gifters.append({"user_id": user_id, "amount": current_stream_money})

        gifters.sort(key=lambda x: x["amount"], reverse=True)
        top_gifters = gifters[:3]

        self.stream_history[self.stream_id]["total_gifts"] = total_gifts
        self.stream_history[self.stream_id]["top_gifters"] = top_gifters

        # 如果有活跃事件，则结束它
        if self.active_event_id:
            self.end_event(self.active_event_id, results={"info": "直播结束，自动结束事件。"})

        # 生成一个简单总结（可根据需要扩展）
        summary_prompt = f"""
        这是本场直播的对话内容（摘要形式）:
        {self.mid_term_memory.buffer}

        请用简短的语言总结本场直播的主要内容和氛围。 
        直播礼物总额: {total_gifts}, 礼物榜前三: {json.dumps(top_gifters, ensure_ascii=False)}。
        """
        summary = self.llm.predict(summary_prompt)
        self.stream_history[self.stream_id]["summary"] = summary

        # 保存
        self.save_stream_history()

        # 重置中期记忆，为下一场做准备
        self.mid_term_memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=4000,
            memory_key="current_stream_memory",
            return_messages=True
        )

        # 生成新的直播ID，并初始化
        self.stream_id = self._generate_stream_id()
        self.init_current_stream()

        return summary

    def save_stream_history(self):
        """保存直播历史记录"""
        os.makedirs(f"./memory_db/{self.vtuber_name}", exist_ok=True)
        with open(f"./memory_db/{self.vtuber_name}/stream_history.json", "w", encoding="utf-8") as f:
            json.dump(self.stream_history, f, ensure_ascii=False, indent=2)

    def load_stream_history(self):
        """加载直播历史记录"""
        try:
            with open(f"./memory_db/{self.vtuber_name}/stream_history.json", "r", encoding="utf-8") as f:
                self.stream_history = json.load(f)
        except FileNotFoundError:
            self.stream_history = {}

    # =========== 对话处理 ===========

    def process_input(self, user_id, user_input):
        """处理用户输入，并返回AI的回复"""
        # 更新短期/中期记忆
        self.short_term_memory.save_context({"input": f"[{user_id}] {user_input}"}, {"output": ""})
        self.mid_term_memory.save_context({"input": f"[{user_id}] {user_input}"}, {"output": ""})

        # 检索长期记忆（角色、梗）
        character_docs = self.character_retriever.get_relevant_documents(user_input)
        character_info_str = "\n".join([doc.page_content for doc in character_docs])

        memes_docs = self.memes_retriever.get_relevant_documents(user_input)
        relevant_memes_str = "\n".join([doc.page_content for doc in memes_docs])

        # 获取用户实体信息
        entity_info = self.get_entity_info(user_id)

        # 获取礼物信息
        gift_info = self.get_gift_info(user_id)
        gift_info_str = (
            f"用户{user_id}的礼物信息:\n"
            f"- 本场直播礼物金额: {gift_info.get('current_livestream_money', 0)}\n"
            f"- 历史总礼物金额: {gift_info.get('total_money', 0)}\n"
        )

        # 生成回复
        response = self.conversation_chain.predict(
            vtuber_name=self.vtuber_name,
            short_term_chat_history=self.short_term_memory.buffer,
            current_stream_memory=self.mid_term_memory.buffer,
            character_info=character_info_str,
            relevant_memes=relevant_memes_str,
            entity_info=json.dumps(entity_info, ensure_ascii=False),
            gift_info=gift_info_str,
            input=user_input
        )

        # 记忆更新
        self.update_memories(user_id, user_input, response)

        # 直播互动计数
        self.stream_history[self.stream_id]["interaction_count"] += 1
        self.save_stream_history()

        return response

    def update_memories(self, user_id, user_input, response):
        """
        更新短期和中期记忆；更新实体信息；如果对话次数超过阈值，将用户加入长期向量库。
        """
        # 短期 & 中期
        self.short_term_memory.save_context({"input": f"[{user_id}] {user_input}"}, {"output": response})
        self.mid_term_memory.save_context({"input": f"[{user_id}] {user_input}"}, {"output": response})

        # 更新用户实体记忆
        self._update_entity_memory(user_id, user_input, response)

        # 判断是否需要把用户加入长期向量库（示例阈值：单场对话>=8次）
        user_data = self.entity_memory.get(user_id, {})
        interaction_count = user_data.get("interaction_count", 0)
        if interaction_count >= 8:
            self.add_user_to_vector_memory(user_id)

    def _update_entity_memory(self, user_id, user_input, response):
        """从对话中提取用户信息，更新到实体记忆。"""
        # 让LLM解析用户信息的示例
        entity_prompt = f"""
        从以下对话中，如果能提取到用户的个人信息，请以JSON形式给出：
        可能的字段包括 name, preference, birthday, background, relationship。
        如果没有新信息，返回空JSON。

        用户: {user_input}
        {self.vtuber_name}: {response}
        """
        entity_result = self.llm.predict(entity_prompt)

        # 初始化用户实体
        if user_id not in self.entity_memory:
            self.entity_memory[user_id] = {
                "first_interaction": datetime.now().isoformat(),
                "interaction_count": 0,
                "streams_attended": [self.stream_id],
                "last_interaction": datetime.now().isoformat()
            }
        else:
            # 若当前直播未在列表里，添加
            if self.stream_id not in self.entity_memory[user_id].get("streams_attended", []):
                self.entity_memory[user_id]["streams_attended"].append(self.stream_id)

        # 解析并更新
        try:
            start_idx = entity_result.find("{")
            end_idx = entity_result.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                data_json = json.loads(entity_result[start_idx:end_idx])
                self.entity_memory[user_id].update(data_json)
        except:
            pass

        # 交互次数+1
        self.entity_memory[user_id]["interaction_count"] = \
            self.entity_memory[user_id].get("interaction_count", 0) + 1
        self.entity_memory[user_id]["last_interaction"] = datetime.now().isoformat()

        self.save_entity_memory()

    def get_entity_info(self, user_id):
        """返回某个用户的实体信息"""
        return self.entity_memory.get(user_id, {
            "first_interaction": datetime.now().isoformat(),
            "interaction_count": 0,
            "streams_attended": [self.stream_id]
        })

    def add_user_to_vector_memory(self, user_id):
        """
        将用户信息加入长期向量库（如果需要的话）。
        这里简单示例：将 entity_memory[user_id] 转成字符串存储。
        """
        user_info = self.entity_memory.get(user_id, {})
        content_str = json.dumps(user_info, ensure_ascii=False)
        # 可以加更多上下文/描述
        doc = Document(page_content=content_str, metadata={"user_id": user_id})
        self.user_vectordb.add_documents([doc])
        self.user_vectordb.persist()

    # =========== 礼物记忆系统 ===========

    def process_gift(self, user_id, gift_name, gift_count, gift_value):
        """更新礼物记忆，不返回礼物感谢消息（按需求移除LLM感谢逻辑）。"""
        if user_id not in self.gift_memory:
            self.gift_memory[user_id] = {
                "current_livestream_money": 0,
                "total_money": 0
            }

        # 更新礼物计数
        self.gift_memory[user_id][gift_name] = self.gift_memory[user_id].get(gift_name, 0) + gift_count

        # 更新金额
        self.gift_memory[user_id]["current_livestream_money"] += gift_value
        self.gift_memory[user_id]["total_money"] += gift_value

        self.save_gift_memory()

        # 同步更新直播统计
        total_stream_gifts = sum(
            [g.get("current_livestream_money", 0) for g in self.gift_memory.values()]
        )
        self.stream_history[self.stream_id]["total_gifts"] = total_stream_gifts
        self.save_stream_history()

    def get_gift_info(self, user_id):
        """获取用户礼物信息"""
        return self.gift_memory.get(user_id, {
            "current_livestream_money": 0,
            "total_money": 0
        })

    def get_top_gifters(self, count=10, time_period=None):
        """获取礼物排行榜，可扩展 time_period 逻辑"""
        all_gifters = []

        if time_period == "current":
            # 当前直播
            for uid, data in self.gift_memory.items():
                all_gifters.append({
                    "user_id": uid,
                    "amount": data.get("current_livestream_money", 0)
                })
        else:
            # 总排行
            for uid, data in self.gift_memory.items():
                all_gifters.append({
                    "user_id": uid,
                    "amount": data.get("total_money", 0)
                })

        all_gifters.sort(key=lambda x: x["amount"], reverse=True)
        return all_gifters[:count]

    def save_gift_memory(self):
        """保存礼物信息"""
        os.makedirs(f"./memory_db/{self.vtuber_name}", exist_ok=True)
        with open(f"./memory_db/{self.vtuber_name}/gift_memory.json", "w", encoding="utf-8") as f:
            json.dump(self.gift_memory, f, ensure_ascii=False, indent=2)

    def load_gift_memory(self):
        """加载礼物信息"""
        try:
            with open(f"./memory_db/{self.vtuber_name}/gift_memory.json", "r", encoding="utf-8") as f:
                self.gift_memory = json.load(f)
        except FileNotFoundError:
            self.gift_memory = {}

    # =========== 事件记忆系统（单活跃事件） ===========

    def create_event(self, event_name, description, duration_minutes=30):
        """创建一个新事件，并写入单独文件。只允许一个活跃事件，若已有则结束之前的。"""
        # 如果已有活跃事件，先结束
        if self.active_event_id:
            self.end_event(self.active_event_id, results={"info": "创建新事件时，自动结束之前的事件。"})

        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        event_id = f"event_{uuid.uuid4().hex[:8]}"

        event_data = {
            "id": event_id,
            "name": event_name,
            "description": description,
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(minutes=duration_minutes)).isoformat(),
            "is_active": True
        }

        # 设置当前活跃事件ID
        self.active_event_id = event_id

        # 将事件信息写入文件
        filename = f"{event_name}_{timestamp_str}.json"
        filepath = os.path.join(f"./memory_db/{self.vtuber_name}/events", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(event_data, f, ensure_ascii=False, indent=2)

        return event_id

    def end_event(self, event_id, results=None):
        """
        结束某个事件（如果文件存在则更新 is_active = False）。
        若传入 results，则写入事件文件。
        """
        # 在目录中找到对应事件文件（此处为示例做法，实际可维护 event_id->filepath 的映射）
        events_dir = os.path.join(f"./memory_db/{self.vtuber_name}", "events")
        if not os.path.exists(events_dir):
            return

        for fname in os.listdir(events_dir):
            if fname.startswith(event_id) or event_id in fname:
                filepath = os.path.join(events_dir, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        event_data = json.load(f)
                    if event_data["id"] == event_id and event_data.get("is_active", False):
                        # 更新
                        event_data["is_active"] = False
                        event_data["end_time"] = datetime.now().isoformat()
                        if results:
                            event_data["results"] = results
                        # 写回
                        with open(filepath, "w", encoding="utf-8") as f:
                            json.dump(event_data, f, ensure_ascii=False, indent=2)
                        # 如果正好是当前活跃事件，清空
                        if self.active_event_id == event_id:
                            self.active_event_id = None
                        break
                except:
                    continue

    # =========== 实体记忆 ===========

    def save_entity_memory(self):
        os.makedirs(f"./memory_db/{self.vtuber_name}", exist_ok=True)
        with open(f"./memory_db/{self.vtuber_name}/entities.json", "w", encoding="utf-8") as f:
            json.dump(self.entity_memory, f, ensure_ascii=False, indent=2)

    def load_entity_memory(self):
        try:
            with open(f"./memory_db/{self.vtuber_name}/entities.json", "r", encoding="utf-8") as f:
                self.entity_memory = json.load(f)
        except FileNotFoundError:
            self.entity_memory = {}
