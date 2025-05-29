using UnityEngine;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework;

[DisallowMultipleComponent]
[RequireComponent(typeof(CubismModel))]
public class CubismIdleMotion : MonoBehaviour
{
    public enum IdleMotionStyle { Calm, Energetic, Hyper }

    [Header("Idle Style Preset")]
    public IdleMotionStyle motionStyle = IdleMotionStyle.Energetic;

    [Header("Head Angle Amplitude (deg)")]
    public Vector3 angleAmplitude = new(60f, 8f, 10f);

    [Header("Body Sway Amplitude (deg / m)")]
    public Vector3 bodyAmplitude = new(50f, 50f, 5f);

    [Header("Breath (0-1)")]
    [Range(0f, 1f)] public float breathAmplitude = 1.0f;
    public float breathValueMultiplier = 1.0f;
    public float verticalBounceFrequencyFactor = 1.2f;

    [Header("Lip Sync")]
    public bool enableAutoMouth = false;

    [Header("Noise Settings")]
    [Range(0.05f, 1.5f)] public float baseFrequency = 1.0f;
    [Range(1f, 20f)] public float damping = 15f;

    [Header("Extra Randomness")]
    public bool reseedPeriodically = false;
    public float reseedInterval = 30f;

    // ★★ 头-身体同步参数 ★★
    [Header("Head-Body Sync")]
    [Range(0f, 1f)]
    public float bodySyncStrength = 0.9f;   // 90 % 身体跟随头部
    [Range(0f, 1f)]
    public float headSoloRatio = 0.1f;    // 10 % 仅头自由晃

    CubismModel _model;
    CubismParameter _angX, _angY, _angZ, _bodyX, _bodyY, _bodyZ, _breath, _mouth;

    Vector3 _seedBase, _seedSolo;
    float _nextReseed;

    void Start()
    {
        Debug.Log("🔥 CubismIdleMotion Start 被调用了！");
    }

    [RuntimeInitializeOnLoadMethod]
    static void ForceLink()
    {
        Debug.Log($"🔗 Linking: {typeof(CubismIdleMotion)}");
    }

    static CubismParameter FindParam(CubismModel model, params string[] ids)
    {
        foreach (var id in ids)
        {
            var p = model.Parameters.FindById(id);
            if (p) return p;
        }
        return null;
    }

    // 2️⃣ 在 Awake() 里用它来绑定
    void Awake()
    {
        _model = GetComponent<CubismModel>();

        // 头部角度
        _angX = FindParam(_model, "Angle X", "ParamAngleX");
        _angY = FindParam(_model, "Angle Y", "ParamAngleY");
        _angZ = FindParam(_model, "Angle Z", "ParamAngleZ");

        // 身体摇晃
        _bodyX = FindParam(_model, "Body X", "ParamBodyX", "ParamBodyAngleX");
        _bodyY = FindParam(_model, "Body Y", "ParamBodyY", "ParamBodyAngleY");
        _bodyZ = FindParam(_model, "Body Z", "ParamBodyZ", "ParamBodyAngleZ");

        // 其他保持不变
        _breath = FindParam(_model, "Breathing", "ParamBreath");
        _mouth  = FindParam(_model, "Mouth Open", "ParamMouthOpenY");

        ApplyStylePreset();
        Reseed();
        _nextReseed = Time.time + reseedInterval;
    }


    void ApplyStylePreset()
    {
        switch (motionStyle)
        {
            case IdleMotionStyle.Calm:
                baseFrequency = 0.2f; damping = 6f;
                angleAmplitude = new(35f, 6f, 6f);
                bodyAmplitude = new(28f, 30f, 3f);
                breathAmplitude = 0.8f;
                breathValueMultiplier = 1.0f;
                verticalBounceFrequencyFactor = 0.8f;
                break;

            case IdleMotionStyle.Energetic:
                baseFrequency = 0.35f; damping = 6f;
                angleAmplitude = new(60f, 8f, 10f);
                bodyAmplitude = new(50f, 50f, 5f);
                breathAmplitude = 1.0f;
                breathValueMultiplier = 1.0f;
                verticalBounceFrequencyFactor = 1.2f;
                break;

            case IdleMotionStyle.Hyper:
                baseFrequency = 0.7f; damping = 8f;
                angleAmplitude = new(75f, 10f, 12f);
                bodyAmplitude = new(60f, 70f, 7f);
                breathAmplitude = 1.0f;
                breathValueMultiplier = 1.0f;
                verticalBounceFrequencyFactor = 1.6f;
                break;
        }
    }

    void LateUpdate()
    {
        if (reseedPeriodically && Time.time >= _nextReseed)
        {
            Reseed();
            _nextReseed = Time.time + reseedInterval;
        }

        float t = Time.time * baseFrequency;

        /* ---------------- 核心噪声 ---------------- */
        Vector3 baseNoise = new(
            Mathf.PerlinNoise(_seedBase.x, t * 1.0f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.y, t * 0.5f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.z, t * 0.4f) - 0.5f);

        Vector3 soloNoise = new(
            Mathf.PerlinNoise(_seedSolo.x, t * 1.2f) - 0.5f,
            Mathf.PerlinNoise(_seedSolo.y, t * 0.6f) - 0.5f,
            Mathf.PerlinNoise(_seedSolo.z, t * 0.5f) - 0.5f);

        Vector3 headNoise = baseNoise + soloNoise * headSoloRatio;

        Vector3 bodyRand = new(
            Mathf.PerlinNoise(_seedBase.x + 7f, t * 0.9f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.y + 7f, t * 1.6f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.z + 7f, t * 1.2f) - 0.5f);

        Vector3 bodyNoise = Vector3.Lerp(bodyRand, baseNoise, bodySyncStrength);

        /* ------------- 写回参数 ------------- */
        Apply(_angX, headNoise.x * angleAmplitude.x);
        Apply(_angY, headNoise.y * angleAmplitude.y);
        Apply(_angZ, headNoise.z * angleAmplitude.z);

        // Dedicated Body Y Bounce
        float bodyYBounceCycleTime = Time.time * verticalBounceFrequencyFactor;
        float bodyYRawNoise = (Mathf.PerlinNoise(_seedBase.y + 37f, bodyYBounceCycleTime) - 0.5f) * 2f;
        float bodyYTargetOffset = bodyYRawNoise * bodyAmplitude.y;
        if (_bodyY) Apply(_bodyY, bodyYTargetOffset, 0.9f);

        // Body X and Z
        Vector3 baseNoiseForBodyXZ = new Vector3(baseNoise.x, 0f, baseNoise.z);
        Vector3 bodyRandForBodyXZ = new Vector3(
            Mathf.PerlinNoise(_seedBase.x + 7f, t * 0.9f) - 0.5f,
            0f,
            Mathf.PerlinNoise(_seedBase.z + 7f, t * 1.2f) - 0.5f);
        Vector3 bodyNoiseXZ = Vector3.Lerp(bodyRandForBodyXZ, baseNoiseForBodyXZ, bodySyncStrength);

        if (_bodyX) Apply(_bodyX, bodyNoiseXZ.x * bodyAmplitude.x);
        if (_bodyZ) Apply(_bodyZ, bodyNoiseXZ.z * bodyAmplitude.z);

        /* ----------- Breath ----------- */
        if (_breath)
        {
            float breathTime = Time.time * 0.3f;
            float breathOffset = (Mathf.PerlinNoise(_seedBase.y + 23f, breathTime) - 0.5f) * 2f;
            float finalBreathValue = breathOffset * breathAmplitude * breathValueMultiplier;
            Apply(_breath, finalBreathValue, 0.9f);
        }

        /* ----------- Mouth ----------- */
        if (enableAutoMouth && _mouth)
            _mouth.Value = Mathf.Abs(Mathf.Sin(Time.time * 6f)) * 0.7f;
    }

    void Apply(CubismParameter p, float offset, float extraDamp = 1f)
    {
        if (!p) return;
        float target = Mathf.Clamp(p.DefaultValue + offset, p.MinimumValue, p.MaximumValue);
        p.Value = Mathf.Lerp(p.Value, target, Time.deltaTime * damping * extraDamp);
    }

    void Reseed()
    {
        _seedBase = Random.insideUnitSphere * 1000f;
        _seedSolo = Random.insideUnitSphere * 1000f + Vector3.one * 99f;
    }

#if UNITY_EDITOR
    void OnValidate()
    {
        baseFrequency = Mathf.Clamp(baseFrequency, 0.01f, 2f);
        damping = Mathf.Max(damping, 0.1f);
        reseedInterval = Mathf.Max(reseedInterval, 1f);
        bodySyncStrength = Mathf.Clamp01(bodySyncStrength);
        headSoloRatio = Mathf.Clamp01(headSoloRatio);
    }
#endif
}

// haha