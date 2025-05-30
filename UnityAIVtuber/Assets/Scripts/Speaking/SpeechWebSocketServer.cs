using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using Live2D.Cubism.Core;
using Newtonsoft.Json;

[System.Serializable]
public class WebSocketCommand
{
    public string command;
}

public class SpeechWebSocketServer : MonoBehaviour
{
    [Header("WebSocket Settings")]
    public int port = 5005;
    
    [Header("Live2D Model")]
    public CubismModel model;
    
    [Header("Speech Animation Settings")]
    [Range(0f, 1f)]
    public float maxMouthOpen = 0.8f;
    [Range(0f, 10f)]
    public float speechSpeed = 8f;
    [Range(0f, 1f)]
    public float mouthFormValue = 0.5f;
    
    private TcpListener tcpListener;
    private Thread tcpListenerThread;
    private bool isListening = false;
    private bool isSpeaking = false;
    
    private CubismParameter mouthOpen;
    private CubismParameter mouthForm;
    
    void Start()
    {
        // 获取Live2D模型组件
        if (model == null)
        {
            model = GetComponent<CubismModel>();
        }

        if (model == null)
        {
            Debug.LogError("CubismModel component is not assigned or found on the GameObject.");
            return;
        }
        
        // 获取嘴部参数
        mouthOpen = model.Parameters.FindById("ParamMouthOpen");
        mouthForm = model.Parameters.FindById("ParamMouthForm");
        
        if (mouthOpen == null)
        {
            Debug.LogError("Parameter 'ParamMouthOpen' not found in the model.");
            return;
        }
        
        if (mouthForm == null)
        {
            Debug.LogWarning("Parameter 'ParamMouthForm' not found in the model.");
        }
        
        // 启动WebSocket服务器
        StartWebSocketServer();
    }
    
    void StartWebSocketServer()
    {
        try
        {
            tcpListener = new TcpListener(IPAddress.Any, port);
            tcpListenerThread = new Thread(new ThreadStart(ListenForWebSocketClients));
            tcpListenerThread.IsBackground = true;
            tcpListenerThread.Start();
            isListening = true;
            
            Debug.Log($"WebSocket Server started on port {port}");
        }
        catch (Exception e)
        {
            Debug.LogError($"Failed to start WebSocket server: {e.Message}");
        }
    }
    
    void ListenForWebSocketClients()
    {
        tcpListener.Start();
        
        while (isListening)
        {
            try
            {
                TcpClient client = tcpListener.AcceptTcpClient();
                Debug.Log("Client connected!");
                
                Thread clientThread = new Thread(() => HandleClient(client));
                clientThread.IsBackground = true;
                clientThread.Start();
            }
            catch (Exception e)
            {
                if (isListening)
                {
                    Debug.LogError($"Error accepting client: {e.Message}");
                }
            }
        }
    }
    
    void HandleClient(TcpClient client)
    {
        NetworkStream stream = client.GetStream();
        byte[] buffer = new byte[1024];
        
        try
        {
            while (client.Connected && isListening)
            {
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                if (bytesRead > 0)
                {
                    string message = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    ProcessMessage(message);
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Error handling client: {e.Message}");
        }
        finally
        {
            client.Close();
            Debug.Log("Client disconnected");
        }
    }
    
    void ProcessMessage(string message)
    {
        try
        {
            WebSocketCommand command = JsonConvert.DeserializeObject<WebSocketCommand>(message);
            
            switch (command.command)
            {
                case "START_SPEAK":
                    Debug.Log("🗣️ Starting to speak");
                    isSpeaking = true;
                    break;
                    
                case "STOP_SPEAK":
                    Debug.Log("🤐 Stopping speech");
                    isSpeaking = false;
                    break;
                    
                default:
                    Debug.LogWarning($"Unknown command: {command.command}");
                    break;
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Error processing message: {e.Message}");
        }
    }
    
    void LateUpdate()
    {
        if (model == null || mouthOpen == null) return;
        
        if (isSpeaking)
        {
            // 说话时的嘴部动画
            float mouthValue = Mathf.Abs(Mathf.Sin(Time.time * speechSpeed)) * maxMouthOpen;
            mouthOpen.Value = mouthValue;
            
            if (mouthForm != null)
            {
                mouthForm.Value = mouthFormValue;
            }
        }
        else
        {
            // 不说话时闭嘴
            mouthOpen.Value = 0f;
            
            if (mouthForm != null)
            {
                mouthForm.Value = 0f;
            }
        }
    }
    
    void OnDestroy()
    {
        StopWebSocketServer();
    }
    
    void OnApplicationQuit()
    {
        StopWebSocketServer();
    }
    
    void StopWebSocketServer()
    {
        isListening = false;
        
        if (tcpListener != null)
        {
            tcpListener.Stop();
        }
        
        if (tcpListenerThread != null && tcpListenerThread.IsAlive)
        {
            tcpListenerThread.Join(1000); // 等待最多1秒
        }
        
        Debug.Log("WebSocket Server stopped");
    }
} 