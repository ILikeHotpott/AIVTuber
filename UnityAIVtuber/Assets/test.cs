using UnityEngine;
using Kirurobo;

public class test : MonoBehaviour
{
    private UniWindowController uniWindow;

    void Start()
    {
#if UNITY_2023_1_OR_NEWER
        uniWindow = FindFirstObjectByType<UniWindowController>();
#else
        uniWindow = FindObjectOfType<UniWindowController>();
#endif

        if (uniWindow != null)
        {
            uniWindow.isClickThrough = false;  // ✅ 保证模型可拦截点击
            Debug.Log("✅ UniWindowController found and click-through disabled");
        }
        else
        {
            Debug.LogWarning("❗️UniWindowController not found in scene!");
        }
    }

    void Update()
    {
        if (Input.GetMouseButtonDown(0))
        {
            Vector2 mousePos = Camera.main.ScreenToWorldPoint(Input.mousePosition);
            RaycastHit2D hit = Physics2D.Raycast(mousePos, Vector2.zero);

            if (hit.collider != null)
            {
                Debug.Log("🎯 命中对象：" + hit.collider.name);
            }
            else
            {
                Debug.Log("✅ 没有命中：理论上应该穿透！");
            }
        }
    }
}
