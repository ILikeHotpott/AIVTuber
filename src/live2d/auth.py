import json
import websocket

PLUGIN_NAME = "SeranionPythonPlugin"
PLUGIN_DEV = "YitongLiu"


def on_open(ws):
    print("🔐 请求新的 token...")
    token_request = {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "get-token",
        "messageType": "AuthenticationTokenRequest",
        "data": {
            "pluginName": PLUGIN_NAME,
            "pluginDeveloper": PLUGIN_DEV
        }
    }
    ws.send(json.dumps(token_request))


def on_message(ws, message):
    print("📩 收到消息：", message)
    msg = json.loads(message)
    if msg.get("messageType") == "AuthenticationTokenResponse":
        token = msg["data"]["authenticationToken"]
        print("✅ 获取成功！请保存此 token：")
        print(f"\n👉 TOKEN: {token}\n")
        ws.close()


def on_error(ws, error):
    print("❌ 错误：", error)


def on_close(ws, close_status_code, close_msg):
    print("🔌 连接关闭")


def start():
    ws = websocket.WebSocketApp(
        "ws://localhost:8001",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()


if __name__ == "__main__":
    start()
