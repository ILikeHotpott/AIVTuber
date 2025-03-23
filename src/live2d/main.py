import json
import websocket

# === 配置信息 ===
VTS_WS_URL = "ws://localhost:8001"
AUTH_TOKEN = "f9b1adcc56c69a8b875c50e57c260d006ffc920ece355fa0369466c8b16b9219"
PLUGIN_NAME = "SeranionPythonPlugin"
PLUGIN_DEV = "YitongLiu"

# === 支持的热键名称（你可以继续添加） ===
SUPPORTED_HOTKEYS = [
    "Anim Shake",
    "PlayLoveMotion",
    "PlayShockMotion",
    "Idle_2",
    "Shock"
]

# === 全局变量保存当前选择的热键 ID ===
current_hotkey_id = None


# === WebSocket 回调函数 ===
def on_open(ws):
    print("正在尝试连接到 VTube Studio WebSocket...")

    auth_payload = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "auth-request",
        "messageType": "AuthenticationRequest",
        "data": {
            "pluginName": PLUGIN_NAME,
            "pluginDeveloper": PLUGIN_DEV,
            "authenticationToken": AUTH_TOKEN
        }
    }
    ws.send(json.dumps(auth_payload))


def on_message(ws, message):
    print("收到消息：", message)
    try:
        msg = json.loads(message)
        msg_type = msg.get("messageType")
        request_id = msg.get("requestID", "")

        if msg_type == "AuthenticationResponse" and msg["data"].get("authenticated"):
            print(f"✅ 身份验证成功，准备触发热键：{current_hotkey_id}")
            play_motion(ws, current_hotkey_id)

        elif msg_type == "APIError" and request_id == "auth-request":
            print("认证失败：", msg["data"].get("message"))

        elif msg_type == "APIError" and request_id == "play-hotkey-request":
            print("播放动画失败：", msg["data"].get("message"))

    except Exception as e:
        print("解析消息时出错：", e)


def play_motion(ws, hotkey_id):
    print(f"🎬 触发热键：{hotkey_id}")
    play_payload = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "play-hotkey-request",
        "messageType": "HotkeyTriggerRequest",
        "data": {
            "hotkeyID": hotkey_id
        }
    }
    ws.send(json.dumps(play_payload))


def on_error(ws, error):
    print("❌ 出错：", error)


def on_close(ws, close_status_code, close_msg):
    print("连接关闭")


# === 启动函数，接收热键参数 ===
def start_ws(hotkey_id):
    global current_hotkey_id

    if hotkey_id not in SUPPORTED_HOTKEYS:
        print(f"热键 '{hotkey_id}' 不在支持列表中。请从以下列表选择：")
        for h in SUPPORTED_HOTKEYS:
            print(" -", h)
        return

    current_hotkey_id = hotkey_id

    ws = websocket.WebSocketApp(
        VTS_WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()


# === 示例入口 ===
if __name__ == "__main__":
    # 修改这里选择你想触发的热键
    start_ws("Anim Shake")

# ["Anim Shake", "Eyes Cry", "Angry Sign", "Shock Sign", "Remove Expressions", "Anim Shake", "Shock"]
