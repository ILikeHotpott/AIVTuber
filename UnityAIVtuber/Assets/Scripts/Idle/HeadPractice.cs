using UnityEngine;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework;

public class HeadPractice : MonoBehaviour
{
    public CubismModel model;

    void Start()
    {
        if (model == null)
        {
            model = GetComponent<CubismModel>();
        }

        if (model == null)
        {
            Debug.LogError("CubismModel component is not assigned or found on the GameObject.");
            return;
        }

        foreach (var param in model.Parameters)
        {
            Debug.Log($"🧩 Parameter: {param.Id} | Min: {param.MinimumValue} | Max: {param.MaximumValue} | Default: {param.DefaultValue}");
        }
    }

    void LateUpdate()
    {
        if (model == null)
        {
            Debug.LogWarning("CubismModel is not assigned or found on the GameObject.");
            return;
        }
        var bodyZ = model.Parameters.FindById("ParamBodyAngleZ");
        if (bodyZ == null)
        {
            Debug.LogWarning("Parameter 'ParamBodyZ' not found in the model.");
            return;
        }
        bodyZ.Value = Mathf.Sin(Time.time * 1f) * 10f;

    }
}