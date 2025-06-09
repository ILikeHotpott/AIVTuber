using System.Collections;
using UnityEngine;
using Live2D.Cubism.Core;

public class UpDown : MonoBehaviour
{
    public CubismModel model;
    public string paramId = "ParamAngleY";

    public float speed = 1.0f;  // 速度
    public float amplitude = 15.0f;  // 振幅（最大角度）

    private CubismParameter targetParam;

    void Start()
    {
        model = GetComponent<CubismModel>();

        if (model != null)
        {
            targetParam = model.Parameters.FindById(paramId);
        }
    }

    void LateUpdate()
    {
        if (model == null)
        {
            model = GetComponent<CubismModel>();
            Debug.Log("🔥 UpDown: model is null");
            return;
        }

        if (targetParam == null)
        {
            targetParam = model.Parameters.FindById(paramId);
            if (targetParam == null)
            {
                Debug.LogWarning($"🔥 UpDown: Cannot find parameter {paramId}");
                return;
            }
        }

        // 计算sin波形，实现上下（左右）来回运动
        float value = Mathf.Sin(Time.time * speed) * amplitude;

        targetParam.Value = value;
    }
}
