using UnityEngine;
using Live2D.Cubism.Core;

public class IdlePractice : MonoBehaviour
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
        if (model == null) return;

        var mouthOpen = model.Parameters.FindById("ParamMouthOpen");
        var mouthForm = model.Parameters.FindById("ParamMouthForm");

        mouthForm.Value = 0.5f;

        if (mouthOpen == null)
        {
            Debug.LogWarning("Parameter 'Mouth Open' not found in the model.");
            return;
        }

        mouthOpen.Value = Mathf.Abs(Mathf.Sin(Time.time * 10)) * 0.7f;

    }
}