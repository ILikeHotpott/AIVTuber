using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

public class SocketMotionServer : MonoBehaviour
{
    private Animator animator;
    private Thread socketThread;
    private TcpListener server;
    private TcpClient client;
    private bool isRunning = true;

    void Start()
    {
        animator = GetComponent<Animator>();
        socketThread = new Thread(ListenForCommands);
        socketThread.IsBackground = true;
        socketThread.Start();
    }

    void ListenForCommands()
    {
        try
        {
            server = new TcpListener(IPAddress.Loopback, 5005);
            server.Start();
            Debug.Log("[SocketServer] Started on 5005");

            client = server.AcceptTcpClient();
            NetworkStream stream = client.GetStream();
            byte[] buffer = new byte[1024];

            while (isRunning)
            {
                if (!stream.DataAvailable)
                {
                    Thread.Sleep(10); // 避免空转
                    continue;
                }

                int byteCount = stream.Read(buffer, 0, buffer.Length);
                if (byteCount <= 0) break;

                string message = Encoding.UTF8.GetString(buffer, 0, byteCount).Trim();
                Debug.Log("[SocketServer] Received: " + message);

                UnityMainThreadDispatcher.Instance().Enqueue(() =>
                {
                    switch (message.ToLower())
                    {
                        case "shock":
                            animator.SetTrigger("Shock");
                            break;
                        case "love":
                            animator.SetTrigger("Love");
                            break;
                        case "idle":
                            animator.SetTrigger("Idle");
                            break;
                    }
                });
            }

            stream.Close();
            client.Close();
            server.Stop();
        }
        catch (SocketException ex)
        {
            Debug.Log("[SocketServer] Exception: " + ex);
        }
    }

    void OnApplicationQuit()
    {
        isRunning = false;
        client?.Close();
        server?.Stop();
        socketThread?.Abort();  // 强制关闭线程（也可以用更温和的中止方式）
        Debug.Log("[SocketServer] Closed.");
    }
}
