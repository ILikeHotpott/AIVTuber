import asyncio
import threading
import time
from typing import Optional

from src.chatbot.llama.chat_engine import ChatEngine
from src.danmaku.message_queue.queue_manager import TotalMessageQueue
from src.danmaku.models import Message, User
from src.prompt.builders.base import DialogueActor


class ChatWithAudience:
    """
    连接 Twitch 弹幕监听器和 ChatEngine 的协调器
    当 talk_to = DialogueActor.AUDIENCE 时，处理观众弹幕消息
    """
    
    def __init__(self, stream_id: str, connect_to_unity: bool = True):
        self.connect_to_unity = connect_to_unity
        self.chat_engine: Optional[ChatEngine] = None
        self.total_queue: Optional[TotalMessageQueue] = None
        self.running = False
        self._message_thread = None
        self._twitch_thread = None
        self.stream_id = stream_id
        
    def start(self):
        """启动弹幕监听和消息处理"""
        if self.running:
            print("[ChatWithAudience] Already running.")
            return
            
        print("[ChatWithAudience] Starting...")
        
        # 初始化 ChatEngine
        self.chat_engine = ChatEngine.get_instance(
            talk_to=DialogueActor.AUDIENCE, 
            connect_to_unity=self.connect_to_unity
        )
        
        # 初始化消息队列
        self.total_queue = TotalMessageQueue()
        
        self.running = True
        
        # 启动 Twitch 监听器线程
        self._start_twitch_listener()
        
        # 启动消息处理线程
        self._start_message_processor()
        
        print("[ChatWithAudience] Started successfully.")
        
    def _start_twitch_listener(self):
        """在单独线程中启动 Twitch 监听器"""
        def twitch_worker():
            try:
                from src.danmaku.twitch.config import TwitchConfig
                from src.danmaku.twitch.listener import TwitchCommentListener
                import nest_asyncio
                
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                config = TwitchConfig()
                bot = TwitchCommentListener(config, self.total_queue)
                
                nest_asyncio.apply()
                
                # 在新的事件循环中运行 bot
                loop.run_until_complete(bot.run())
                
            except Exception as e:
                print(f"[ChatWithAudience] Twitch listener error: {e}")
            finally:
                # 确保循环关闭
                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_closed():
                        loop.close()
                except:
                    pass
                
        self._twitch_thread = threading.Thread(target=twitch_worker, daemon=True)
        self._twitch_thread.start()
        
    def _start_message_processor(self):
        """启动消息处理线程"""
        def message_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._message_loop())
            finally:
                loop.close()
            
        self._message_thread = threading.Thread(target=message_worker, daemon=True)
        self._message_thread.start()
        
    async def _message_loop(self):
        """主消息处理循环"""
        print("[ChatWithAudience] Message processing loop started.")
        
        # 在 AI 说完话之后才开始计时，避免自言自语
        idle_since_speech: float | None = None  # 记录 AI 说完话的时间戳

        while self.running:
            try:
                message = await self._get_next_message()

                if message:
                    idle_since_speech = None
                    await self._process_message(message)
                    idle_since_speech = time.time()
                else:
                    if idle_since_speech is not None:
                        if time.time() - idle_since_speech >= 5:
                            await self._inject_please_say_more()
                            idle_since_speech = None
                    await asyncio.sleep(0.5)

            except Exception as e:
                print(f"[ChatWithAudience] Error in message loop: {e}")
                await asyncio.sleep(1)  # 出错时等待更长时间
                
    async def _get_next_message(self) -> Optional[Message]:
        """从总队列中获取下一条优先级最高的消息"""
        if not self.total_queue:
            return None
            
        try:
            # 获取异步方法的结果
            result = await self.total_queue.get_next_message_async()
            if result:
                print(f"[ChatWithAudience] Got message: {result.user.name}: {result.content}")
            return result
        except Exception as e:
            print(f"[ChatWithAudience] Error getting message: {e}")
            return None
            
    async def _process_message(self, message: Message):
        """处理单条消息"""
        print(f"[ChatWithAudience] Processing message: {message.user.name}: {message.content}")
        
        # 等待上一次 TTS 完成
        await self._wait_for_tts_completion()
        
        try:
            response = await self.chat_engine.stream_chat(
                user_id=self.stream_id,
                msg=message.prompt,
                language="English"
            )
            
        except Exception as e:
            print(f"[ChatWithAudience] Error processing message: {e}")
            
    async def _wait_for_tts_completion(self):
        """等待 TTS 完成播放"""
        if not self.chat_engine:
            return
            
        while self.chat_engine.is_speaking():
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.2)
        
    def stop(self):
        """停止弹幕监听和消息处理"""
        if not self.running:
            print("[ChatWithAudience] Already stopped.")
            return
            
        print("[ChatWithAudience] Stopping...")
        self.running = False
        
        # 等待线程结束
        if self._message_thread and self._message_thread.is_alive():
            self._message_thread.join(timeout=5)
            
        if self._twitch_thread and self._twitch_thread.is_alive():
            self._twitch_thread.join(timeout=5)
            
        print("[ChatWithAudience] Stopped.")
        
    async def stop_async(self):
        """异步停止，用于清理 ChatEngine"""
        self.stop()
        
        if self.chat_engine:
            await self.chat_engine.close()
            
        print("[ChatWithAudience] Async cleanup completed.")

    async def _inject_please_say_more(self):
        """在长时间空闲时向总队列写入系统提示。"""

        if not self.total_queue:
            return

        try:
            system_user = User(user_id=0, name="System")
            await self.total_queue.put_danmu(system_user, "(System prompt: Please say more)")
            print("[ChatWithAudience] Injected idle prompt → Please say more")
        except Exception as exc:
            print(f"[ChatWithAudience] Failed to inject idle prompt: {exc}")


async def main():
    """示例主函数"""
    chat_with_audience = ChatWithAudience(connect_to_unity=True, stream_id="test_stream_4")
    
    try:
        chat_with_audience.start()
        
        print("Chat with audience is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        await chat_with_audience.stop_async()


if __name__ == "__main__":
    asyncio.run(main())
