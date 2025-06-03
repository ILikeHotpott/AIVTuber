import threading
import asyncio
import time

from src.asr.asr_engine import ASREngine
from src.asr.asr_config import ASRConfig
from src.chatbot.llama.chat_engine import ChatEngine

# ═══════════════ 新增：集成新的管理系统 ═══════════════
from src.danmaku.user.user_manager import UserManager
from src.chatbot.core.chat_mode_manager import ChatModeManager, ChatMode, ChatMessage


class SceneOrchestrator:
    def __init__(self, connect_to_unity: bool = True, chat_mode: ChatMode = ChatMode.HYBRID):
        # ═══════════════ 修改：集成新的管理系统 ═══════════════
        self.connect_to_unity = connect_to_unity
        self.chat_mode = chat_mode
        
        # 初始化用户管理器
        self.user_manager = UserManager()
        
        # 初始化聊天引擎（保持向后兼容）
        self.chat_engine = ChatEngine.get_instance(
            connect_to_unity=self.connect_to_unity,
            use_user_manager=True  # 启用新的用户管理系统
        )
        
        # 初始化聊天模式管理器
        self.chat_mode_manager = ChatModeManager(
            user_manager=self.user_manager,
            mode=self.chat_mode
        )
        
        # 设置响应回调
        self.chat_mode_manager.set_response_callback(self._on_chat_response)
        
        # ═══════════════ 保留：旧版本兼容性 ═══════════════
        # 为了向后兼容，保留 ASR 相关属性
        self.asr = None
        self.asr_running = False
        self._asr_thread = None
        self.loop = asyncio.get_event_loop()
        
        print(f"[SceneOrchestrator] Initialized with mode: {chat_mode.value}")

    def _on_chat_response(self, response: str, message: ChatMessage) -> None:
        """处理聊天响应的回调函数"""
        print(f"[SceneOrchestrator] Response for {message.source.value}: {response[:100]}...")
        
        # 如果需要，可以在这里添加额外的响应处理逻辑
        # 例如：发送到Unity、记录日志、触发其他事件等
        
        # 将响应发送到TTS队列（通过ChatEngine）
        if hasattr(self.chat_engine, '_speak_q'):
            # 分句处理
            sentences = self._split_into_sentences(response)
            for sentence in sentences:
                if sentence.strip():
                    self.chat_engine._speak_q.put(sentence.strip())

    def _split_into_sentences(self, text: str) -> list[str]:
        """将文本分割成句子"""
        import re
        # 简单的句子分割，可以根据需要改进
        sentences = re.split(r'[。！？；!?]', text)
        return [s.strip() for s in sentences if s.strip()]

    def start(self):
        print("[SceneOrchestrator] Starting with new chat mode system...")
        
        # ═══════════════ 新增：启动新的聊天模式管理器 ═══════════════
        self.chat_mode_manager.start()
        
        # ═══════════════ 保留：向后兼容 ═══════════════
        # 如果需要单独的ASR控制，可以保留这些方法
        if hasattr(self, 'asr') and self.asr:
            self._start_asr()

    def _start_asr(self):
        """启动ASR（向后兼容方法）"""
        if not self.asr:
            self.asr = ASREngine(ASRConfig(debug=True))
            
        if self.asr_running:
            print("[SceneOrchestrator] ASR already running.")
            return
            
        self.asr.start()
        self.asr_running = True
        self._asr_thread = threading.Thread(target=self._asr_loop, daemon=True)
        self._asr_thread.start()

    def _asr_safe_say(self, text: str):
        """处理ASR输入（向后兼容方法）"""
        print("[SceneOrchestrator] PAUSE ASR")
        if self.asr:
            self.asr.pause()

        # ═══════════════ 修改：使用新的聊天模式管理器 ═══════════════
        # 将ASR消息添加到新的管理器中
        self.chat_mode_manager.add_asr_message(text, "asr_user")

        # 等待TTS完全播放结束
        while self.chat_engine.is_speaking():
            time.sleep(0.05)

        time.sleep(0.5)

        print("[SceneOrchestrator] RESUME ASR")
        if self.asr:
            self.asr.resume()

    def _asr_loop(self):
        """ASR循环（向后兼容方法）"""
        print("[SceneOrchestrator] ASR loop started.")
        while self.asr_running and self.asr:
            text = self.asr.get_text(timeout=1)
            if text:
                print(f"[ASR] {text}")
                self._asr_safe_say(text)

    # ═══════════════ 新增：新的接口方法 ═══════════════
    def add_danmaku_message(self, content: str, user_id: str, username: str = "", is_vip: bool = False):
        """添加弹幕消息"""
        self.chat_mode_manager.add_danmaku_message(content, user_id, username, is_vip)

    def register_user(self, user_id: str, username: str = None, metadata: dict = None):
        """注册用户"""
        return self.user_manager.register_user(user_id, username, metadata)

    def get_user_stats(self) -> dict:
        """获取用户统计信息"""
        user_stats = self.user_manager.get_stats()
        chat_stats = self.chat_mode_manager.get_stats()
        
        return {
            "user_management": user_stats,
            "chat_management": chat_stats,
            "mode": self.chat_mode.value,
            "unity_connected": self.connect_to_unity
        }

    def switch_chat_mode(self, new_mode: ChatMode):
        """切换聊天模式"""
        if new_mode == self.chat_mode:
            print(f"[SceneOrchestrator] Already in {new_mode.value} mode.")
            return
            
        print(f"[SceneOrchestrator] Switching from {self.chat_mode.value} to {new_mode.value} mode...")
        
        # 停止当前模式管理器
        self.chat_mode_manager.stop()
        
        # 创建新的模式管理器
        self.chat_mode = new_mode
        self.chat_mode_manager = ChatModeManager(
            user_manager=self.user_manager,
            mode=self.chat_mode
        )
        self.chat_mode_manager.set_response_callback(self._on_chat_response)
        
        # 启动新的模式管理器
        self.chat_mode_manager.start()
        
        print(f"[SceneOrchestrator] Switched to {new_mode.value} mode.")

    def stop(self):
        print("[SceneOrchestrator] Stopping...")
        
        # ═══════════════ 新增：停止新的管理系统 ═══════════════
        if hasattr(self, 'chat_mode_manager') and self.chat_mode_manager:
            self.chat_mode_manager.stop()
        
        # ═══════════════ 保留：向后兼容 ═══════════════
        if self.asr_running and self.asr:
            self.asr_running = False
            self.asr.stop()
            if self._asr_thread:
                self._asr_thread.join()

    async def stop_async_components(self):
        print("[SceneOrchestrator] Closing async components...")
        
        # ═══════════════ 新增：关闭新的管理系统 ═══════════════
        if hasattr(self, 'chat_mode_manager') and self.chat_mode_manager:
            await self.chat_mode_manager.close()
            
        if hasattr(self, 'user_manager') and self.user_manager:
            await self.user_manager.close()
        
        # ═══════════════ 保留：关闭ChatEngine ═══════════════
        if hasattr(self, 'chat_engine') and self.chat_engine:
            await self.chat_engine.close()
            
        print("[SceneOrchestrator] Async components closed.")


async def main(orchestrator: SceneOrchestrator):
    orchestrator.start()

    print("Scene running (Multi-mode chat active). Press Ctrl+C to stop.")

    try:
        # ═══════════════ 新增：演示不同的功能 ═══════════════
        # 注册一些示例用户
        orchestrator.register_user("user1", "张三", {"role": "viewer"})
        orchestrator.register_user("user2", "李四", {"role": "vip"})
        
        # 模拟一些弹幕消息
        await asyncio.sleep(2)
        orchestrator.add_danmaku_message("你好主播！", "user1", "张三")
        
        await asyncio.sleep(3)
        orchestrator.add_danmaku_message("今天直播什么内容？", "user2", "李四", is_vip=True)
        
        # 主循环
        while True:
            await asyncio.sleep(1)
            
            # 可以在这里添加定期任务，比如打印统计信息
            # stats = orchestrator.get_user_stats()
            # print(f"[Stats] Users: {stats['user_management']['active_users']}, "
            #       f"Messages: {stats['chat_management']['processed_messages']}")
            
    except KeyboardInterrupt:
        print("Stopping Scene...")
    finally:
        print("[SceneOrchestrator] Stopping synchronous components...")
        orchestrator.stop()


if __name__ == "__main__":
    # ═══════════════ 修改：支持命令行参数选择模式 ═══════════════
    import sys
    
    # 默认混合模式，可以通过命令行参数改变
    mode = ChatMode.HYBRID
    if len(sys.argv) > 1:
        mode_str = sys.argv[1].lower()
        if mode_str == "realtime":
            mode = ChatMode.REALTIME
        elif mode_str == "danmaku":
            mode = ChatMode.DANMAKU
        elif mode_str == "hybrid":
            mode = ChatMode.HYBRID
        else:
            print(f"Unknown mode: {mode_str}. Using default: hybrid")
    
    orchestrator = SceneOrchestrator(connect_to_unity=True, chat_mode=mode)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(orchestrator))
    except KeyboardInterrupt:
        print("Stopping Scene from __main__ (KeyboardInterrupt)...")
    finally:
        print("[SceneOrchestrator] Cleaning up...")
        if orchestrator:
            if hasattr(orchestrator, 'asr_running') and orchestrator.asr_running:
                print("[SceneOrchestrator] Ensuring synchronous components are stopped from __main__...")
                orchestrator.stop()

            print("[SceneOrchestrator] Stopping asynchronous components from __main__...")
            loop.run_until_complete(orchestrator.stop_async_components())

        print("[SceneOrchestrator] Closing event loop...")
        loop.close()
        print("[SceneOrchestrator] Event loop closed.")
