using System.Collections;
using UnityEngine;
using Kirurobo;     // UniWinC

[RequireComponent(typeof(ScrollZoom))]
public class ZoomFitController : MonoBehaviour
{
    public Transform target;      // Live2D 根
    public Camera    cam;         // 主摄像机
    public int       marginPx = 40;

    ScrollZoom          zoom;
    UniWindowController uwc;

    void Awake()
    {
        if (!target) target = transform;
        if (!cam)    cam    = Camera.main;

        zoom = GetComponent<ScrollZoom>();
        uwc  = FindFirstObjectByType<UniWindowController>();

        zoom.target = target;               // 防呆
    }

    void OnEnable()  => zoom.OnZoomed += ResizeRoutine;
    void OnDisable() => zoom.OnZoomed -= ResizeRoutine;

    /* ---------- 核心逻辑 ---------- */
    void ResizeRoutine()
    {
        if (!uwc) return;

        /* -- STEP-1 计算包围盒世界尺寸 -- */
        Bounds B = BoundsOf(target);
        float worldW = B.size.x;
        float worldH = B.size.y;

        /* -- STEP-2 根据“当前”像素密度推算需要的窗口大小 -- */
        float pxPerUnit = Screen.height / (cam.orthographicSize * 2f);
        Vector2 needPx = new(
            Mathf.Ceil(worldW * pxPerUnit) + marginPx * 2,
            Mathf.Ceil(worldH * pxPerUnit) + marginPx * 2);

        /* -- STEP-3 原生窗口中心保持不动地改尺寸 -- */
        Vector2 oldSize = uwc.windowSize;
        Vector2 oldPos  = uwc.windowPosition;
        Vector2 delta   = (needPx - oldSize) * 0.5f;

        uwc.windowSize     = needPx;
        uwc.windowPosition = oldPos - delta;

        /* -- STEP-4 同步 Unity 渲染分辨率，然后在下一帧再调 Camera -- */
        int rx = Mathf.RoundToInt(needPx.x);
        int ry = Mathf.RoundToInt(needPx.y);
        if (rx != Screen.width || ry != Screen.height)
            Screen.SetResolution(rx, ry, false);           // false = Windowed

        StopAllCoroutines();               // 避免多次并发
        StartCoroutine(AdjustCameraNextFrame(B));          // 下一帧再做视野修正
    }

    IEnumerator AdjustCameraNextFrame(Bounds lastBounds)
    {
        yield return null;                 // 等 1 帧，等待 Screen 宽高刷新

        /* —— 用最新宽高 & 宽高比重算可见范围 —— */
        float aspect    = (float)Screen.width / Screen.height;
        float pxPerUnit = Screen.height / (cam.orthographicSize * 2f); // 旧值，仅为 margin 换算

        float halfH = lastBounds.size.y * 0.5f;
        float halfW = lastBounds.size.x * 0.5f / aspect;
        cam.orthographicSize = Mathf.Max(halfH, halfW) + (marginPx / pxPerUnit);

        /* —— 镜头对准模型中心 —— */
        Vector3 c = lastBounds.center;
        cam.transform.position = new Vector3(c.x, c.y, cam.transform.position.z);
    }

    /* 工具：求包围盒 */
    static Bounds BoundsOf(Transform root)
    {
        var rs = root.GetComponentsInChildren<Renderer>();
        Bounds b = rs[0].bounds;
        foreach (var r in rs) b.Encapsulate(r.bounds);
        return b;
    }
}
