import socket


class MotionClient:
    def __init__(self, host='localhost', port=5005):
        self.host = host
        self.port = port
        self.sock = None
        self.connect()
        self.available_commands = {"Love", "Shock", "Idle"}

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"Connected to Unity at {self.host}:{self.port}")
        except Exception as e:
            print(f"Connection failed: {e}")

    def send_motion(self, command: str):
        if not self.sock:
            print("Socket not connected.")
            return
        try:
            self.sock.send(command.encode())
            print(f"[➡️] Sent motion: {command}")
        except Exception as e:
            print(f"Failed to send motion: {e}")

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            print("Connection closed.")

    def run(self):
        print("输入动作命令（Love / Shock / Idle），输入 exit 退出：")
        while True:
            cmd = input(">>> ").strip()
            if cmd.lower() == "exit":
                break
            if cmd in self.available_commands:
                self.send_motion(cmd)
            else:
                print(f"动作 '{cmd}' 不存在，请输入有效指令：{', '.join(self.available_commands)}")
        self.close()


if __name__ == '__main__':
    client = MotionClient()
    client.run()
