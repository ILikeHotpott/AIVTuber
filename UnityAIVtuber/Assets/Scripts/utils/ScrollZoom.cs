using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;      // 新输入系统需要
#endif

/// <summary>
/// 鼠标滚轮按“初始化时的大小”为基准做相对缩放。
/// Broadcasts <see cref="OnZoomed"/> after scale changes.
/// </summary>
public class ScrollZoom : MonoBehaviour
{
    [Header("Target to scale (Live2D root)")]
    public Transform target;

    [Header("Zoom settings")]
    [Tooltip("滚轮一步的缩放速度，0.1~0.3 合理")]
    public float zoomSpeed = 0.2f;

    [Tooltip("最小倍率 = 初始大小 × minFactor")]
    public float minFactor = 0.3f;
    [Tooltip("最大倍率 = 初始大小 × maxFactor")]
    public float maxFactor = 3f;

    public event System.Action OnZoomed;   // ← 事件

    private Vector3 _baseScale;

    void Awake()
    {
        if (!target) target = transform;
        _baseScale = target.localScale;
    }

    void Update()
    {
        float scroll;
#if ENABLE_INPUT_SYSTEM
        scroll = Mouse.current.scroll.ReadValue().y / 120f;   // 与旧系统保持同量级
#else
        scroll = Input.GetAxis("Mouse ScrollWheel");
#endif
        if (Mathf.Abs(scroll) < 0.0001f) return;

        // 计算新的倍率（乘法缩放）
        float deltaFactor   = 1f + scroll * zoomSpeed;
        float currentFactor = target.localScale.x / _baseScale.x;
        float newFactor     = Mathf.Clamp(currentFactor * deltaFactor, minFactor, maxFactor);

        target.localScale = _baseScale * newFactor;

        OnZoomed?.Invoke();   // 广播
    }
}
