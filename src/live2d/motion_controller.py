import socket


class MotionClient:
    def __init__(self, host='localhost', port=5005):
        self.host = host
        self.port = port
        self.sock = None
        self.connect()

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"[✅] Connected to Unity at {self.host}:{self.port}")
        except Exception as e:
            print(f"[❌] Connection failed: {e}")

    def send_motion(self, command: str):
        if not self.sock:
            print("[⚠️] Socket not connected.")
            return
        try:
            self.sock.send(command.encode())
            print(f"[➡️] Sent motion: {command}")
        except Exception as e:
            print(f"[❌] Failed to send motion: {e}")

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            print("[🔌] Connection closed.")


if __name__ == '__main__':
    client = MotionClient()

    client.send_motion("Love")
    input(">> 按回车继续\n")

    client.send_motion("Shock")
    input(">> 按回车继续\n")

    client.send_motion("Love")
    input(">> 按回车继续\n")

    client.send_motion("Shock")
    input(">> 按回车继续\n")

    client.send_motion("Idle")
    input(">> 按回车结束\n")

    client.close()
