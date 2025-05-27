using UnityEngine;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework;

public class ParamController : MonoBehaviour
{
    private CubismModel model;

    void Start()
    {
        model = this.GetComponent<CubismModel>();

        if (model == null)
        {
            Debug.LogError("CubismModel 获取失败，请确保脚本挂在模型根节点上！");
        }
    }

    void LateUpdate()  // 用 LateUpdate，确保 Cubism 系统已初始化完成
    {
        if (model == null || model.Parameters == null)
            return;

        SetParam("ParamMouthOpenY", Mathf.Abs(Mathf.Sin(Time.time * 3f)));
        SetParam("ParamEyeLOpen", ShouldBlink() ? 0f : 1f);
        SetParam("ParamEyeROpen", ShouldBlink() ? 0f : 1f);
        SetParam("ParamAngleZ", Mathf.Sin(Time.time) * 20f);
        SetParam("ParamBodyX", Mathf.Sin(Time.time * 0.5f) * 10f);
    }

    void SetParam(string paramId, float value)
    {
        var p = model.Parameters.FindById(paramId);
        if (p != null) p.Value = value;
    }

    bool ShouldBlink()
    {
        float t = Mathf.PingPong(Time.time * 2f, 1f);
        return t > 0.95f;
    }
}
