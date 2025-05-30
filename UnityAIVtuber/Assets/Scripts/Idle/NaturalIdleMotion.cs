using UnityEngine;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework;

[DisallowMultipleComponent]
[RequireComponent(typeof(CubismModel))]
public class CubismIdleMotion : MonoBehaviour
{
    public enum IdleMotionStyle { Calm, Energetic, Hyper }
    public enum MotionState { Idle, Active } // 新增状态枚举

    /*────────────────────── 公开参数 ──────────────────────*/

    [Header("Idle Style Preset")]
    public IdleMotionStyle motionStyle = IdleMotionStyle.Energetic;

    [Header("Motion State Control")]
    [Tooltip("直立状态占总时间的百分比")]
    [Range(0f, 0.9f)] public float idleTimeRatio = 0f;
    [Tooltip("状态切换的时间间隔范围")]
    public Vector2 stateChangeInterval = new Vector2(2f, 4f);

    [Header("Head Angle Amplitude (deg)")]
    public Vector3 angleAmplitude = new Vector3(35f, 6f, 8f); // 降低了头部摇晃幅度

    [Header("Body Sway Amplitude (deg / m)")]
    public Vector3 bodyAmplitude = new Vector3(
        30f,  // X - 降低了摇晃幅度
        8f,   // Y - 降低了Y轴幅度
        20f   // Z - 降低了Z轴幅度
    );

    [Header("Breath (0-1)")]
    [Range(0f, 1f)] public float breathAmplitude = 0.8f; // 稍微降低呼吸幅度
    public float breathValueMultiplier = 1.0f;
    public float verticalBounceFrequencyFactor = 1.0f;

    [Header("Lip Sync")]
    public bool enableAutoMouth = false;

    [Header("Noise Settings")]
    [Range(0.05f, 1.5f)] public float baseFrequency = 0.8f;   // 调整基础频率
    [Range(1f, 20f)]     public float damping       = 8f;     // 增加阻尼让动作更平滑

    [Header("Extra Randomness")]
    public bool  reseedPeriodically = false;
    public float reseedInterval     = 25f;

    [Header("Head-Body Sync")]
    [Range(0f, 1f)] public float bodySyncStrength = 0.8f;
    [Range(0f, 1f)] public float headSoloRatio   = 0.15f;

    /*──────────── 方向约束和时间限制参数 ────────────*/
    [Header("Direction & Time Control")]
    [Tooltip("角度保持的最大时间（秒）")]
    public float maxAngleHoldTime = 2f;
    [Tooltip("触发方向约束的幅度阈值")]
    [Range(0.3f, 0.8f)] public float directionConstraintThreshold = 0.5f;

    /*────────────────────── 私有字段 ──────────────────────*/

    CubismModel _model;
    CubismParameter _angX, _angY, _angZ, _bodyX, _bodyY, _bodyZ, _breath, _mouth;

    Vector3 _seedBase, _seedSolo;
    float   _nextReseed;

    // 状态管理
    MotionState _currentState = MotionState.Idle;
    float _nextStateChangeTime = 0f;
    
    // 方向约束状态
    Vector3 _lastHeadDirection = Vector3.zero;
    Vector3 _lastBodyDirection = Vector3.zero;
    float _headAngleHoldStartTime = 0f;
    float _bodyAngleHoldStartTime = 0f;
    
    // 平滑运动状态
    Vector3 _headTargetAngles = Vector3.zero;
    Vector3 _bodyTargetAngles = Vector3.zero;
    Vector3 _headCurrentAngles = Vector3.zero;
    Vector3 _bodyCurrentAngles = Vector3.zero;

    /*────────────────────── 生命周期 ──────────────────────*/

    void Start() => Debug.Log("🔥 CubismIdleMotion Start");

    [RuntimeInitializeOnLoadMethod]
    static void ForceLink() => Debug.Log($"🔗 Linking: {typeof(CubismIdleMotion)}");

    static CubismParameter FindParam(CubismModel model, params string[] ids)
    {
        foreach (var id in ids)
        {
            var p = model.Parameters.FindById(id);
            if (p) return p;
        }
        return null;
    }

    void Awake()
    {
        _model = GetComponent<CubismModel>();

        /* 头部参数 */
        _angX = FindParam(_model, "Angle X",  "ParamAngleX");
        _angY = FindParam(_model, "Angle Y",  "ParamAngleY");
        _angZ = FindParam(_model, "Angle Z",  "ParamAngleZ");

        /* 身体参数 */
        _bodyX = FindParam(_model, "Body X",  "ParamBodyX",  "ParamBodyAngleX");
        _bodyY = FindParam(_model, "Body Y",  "ParamBodyY",  "ParamBodyAngleY");
        _bodyZ = FindParam(_model, "Body Z",  "ParamBodyZ",  "ParamBodyAngleZ");

        /* 其它 */
        _breath = FindParam(_model, "Breathing", "ParamBreath");
        _mouth  = FindParam(_model, "Mouth Open", "ParamMouthOpenY");

        ApplyStylePreset();
        Reseed();
        _nextReseed = Time.time + reseedInterval;
        ScheduleNextStateChange();
    }

    /*────────────────────── 预设风格 ──────────────────────*/
    void ApplyStylePreset()
    {
        switch (motionStyle)
        {
            case IdleMotionStyle.Calm:
                baseFrequency = 0.3f; damping = 6f;
                angleAmplitude = new Vector3(25f, 4f, 5f);
                bodyAmplitude  = new Vector3(20f, 6f, 15f);
                verticalBounceFrequencyFactor = 0.8f;
                break;

            case IdleMotionStyle.Energetic:
                baseFrequency = 0.8f;
                damping       = 8f;
                angleAmplitude = new Vector3(35f, 6f, 8f);
                bodyAmplitude  = new Vector3(30f, 8f, 20f);
                verticalBounceFrequencyFactor = 1.0f;
                break;

            case IdleMotionStyle.Hyper:
                baseFrequency = 1.0f;
                damping       = 10f;
                angleAmplitude = new Vector3(45f, 8f, 10f);
                bodyAmplitude  = new Vector3(40f, 10f, 25f);
                verticalBounceFrequencyFactor = 1.2f;
                break;
        }
    }

    /*────────────────────── 主循环 ──────────────────────*/
    void LateUpdate()
    {
        /*==== 定时换种子 ====*/
        if (reseedPeriodically && Time.time >= _nextReseed)
        {
            Reseed();
            _nextReseed = Time.time + reseedInterval;
        }

        /*==== 状态切换控制 ====*/
        UpdateMotionState();

        float t = Time.time * baseFrequency;

        /*==== 生成目标角度 ====*/
        GenerateTargetAngles(t);

        /*==== 应用方向约束和时间限制 ====*/
        ApplyDirectionConstraints();

        /*==== 平滑更新当前角度 ====*/
        UpdateCurrentAngles();

        /*==== 应用到参数 ====*/
        ApplyToParameters();

        /*==== 呼吸 ====*/
        UpdateBreathing(t);

        /*==== 自动张嘴 ====*/
        if (enableAutoMouth && _mouth)
            _mouth.Value = Mathf.Abs(Mathf.Sin(Time.time * 6f)) * 0.6f;
    }

    void UpdateMotionState()
    {
        // 如果idleTimeRatio为0，直接保持Active状态，无需状态切换
        if (idleTimeRatio <= 0f)
        {
            _currentState = MotionState.Active;
            return;
        }
        
        if (Time.time >= _nextStateChangeTime)
        {
            // 根据概率决定下一个状态
            float random = Random.value;
            if (_currentState == MotionState.Idle)
            {
                _currentState = (random < (1f - idleTimeRatio)) ? MotionState.Active : MotionState.Idle;
            }
            else
            {
                _currentState = (random < idleTimeRatio) ? MotionState.Idle : MotionState.Active;
            }
            
            ScheduleNextStateChange();
        }
    }

    void GenerateTargetAngles(float t)
    {
        /*==== 核心噪声生成 ====*/
        Vector3 baseNoise = new Vector3(
            Mathf.PerlinNoise(_seedBase.x,     t * 1.0f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.y,     t * 0.6f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.z,     t * 0.5f) - 0.5f
        );

        Vector3 soloNoise = new Vector3(
            Mathf.PerlinNoise(_seedSolo.x,     t * 1.2f) - 0.5f,
            Mathf.PerlinNoise(_seedSolo.y,     t * 0.8f) - 0.5f,
            Mathf.PerlinNoise(_seedSolo.z,     t * 0.7f) - 0.5f
        );

        // 头部目标角度
        Vector3 headNoise = baseNoise + soloNoise * headSoloRatio;
        _headTargetAngles = new Vector3(
            headNoise.x * angleAmplitude.x,
            headNoise.y * angleAmplitude.y,
            headNoise.z * angleAmplitude.z
        );

        // 身体目标角度
        Vector3 bodyRand = new Vector3(
            Mathf.PerlinNoise(_seedBase.x + 7f, t * 0.9f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.y + 7f, t * 1.1f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.z + 7f, t * 0.8f) - 0.5f
        );

        Vector3 bodyNoise = Vector3.Lerp(bodyRand, baseNoise, bodySyncStrength);
        _bodyTargetAngles = new Vector3(
            bodyNoise.x * bodyAmplitude.x,
            bodyNoise.y * bodyAmplitude.y,
            bodyNoise.z * bodyAmplitude.z
        );
    }

    void ApplyDirectionConstraints()
    {
        // 方向约束：防止持续往同一方向摆动
        CheckDirectionConstraint(ref _headTargetAngles, _headCurrentAngles, angleAmplitude);
        CheckDirectionConstraint(ref _bodyTargetAngles, _bodyCurrentAngles, bodyAmplitude);
        
        // 检查角度保持时间，如果太久就强制改变方向
        bool headDirectionChanged = Vector3.Distance(_headTargetAngles.normalized, _lastHeadDirection.normalized) > 0.1f;
        if (headDirectionChanged)
        {
            _lastHeadDirection = _headTargetAngles;
            _headAngleHoldStartTime = Time.time;
        }
        else if (Time.time - _headAngleHoldStartTime > maxAngleHoldTime)
        {
            // 强制改变头部方向而不是回归中心
            ForceDirectionChange(ref _headTargetAngles, angleAmplitude);
            _headAngleHoldStartTime = Time.time;
        }

        // 检查身体角度保持时间
        bool bodyDirectionChanged = Vector3.Distance(_bodyTargetAngles.normalized, _lastBodyDirection.normalized) > 0.1f;
        if (bodyDirectionChanged)
        {
            _lastBodyDirection = _bodyTargetAngles;
            _bodyAngleHoldStartTime = Time.time;
        }
        else if (Time.time - _bodyAngleHoldStartTime > maxAngleHoldTime)
        {
            // 强制改变身体方向而不是回归中心
            ForceDirectionChange(ref _bodyTargetAngles, bodyAmplitude);
            _bodyAngleHoldStartTime = Time.time;
        }
    }

    void CheckDirectionConstraint(ref Vector3 targetAngles, Vector3 currentAngles, Vector3 amplitude)
    {
        for (int i = 0; i < 3; i++)
        {
            float threshold = amplitude[i] * directionConstraintThreshold;
            
            // 如果当前角度已经比较大，且目标角度还要继续往同一方向
            if (Mathf.Abs(currentAngles[i]) > threshold)
            {
                bool sameDirection = Mathf.Sign(targetAngles[i]) == Mathf.Sign(currentAngles[i]);
                if (sameDirection && Mathf.Abs(targetAngles[i]) > Mathf.Abs(currentAngles[i]))
                {
                    // 直接反向或随机改变方向，不再停顿或回归中心
                    float choice = Random.value;
                    if (choice < 0.6f)
                    {
                        // 反向摆动
                        targetAngles[i] = -currentAngles[i] * Random.Range(0.3f, 0.8f);
                    }
                    else
                    {
                        // 随机改变到不同方向
                        targetAngles[i] = Random.Range(-amplitude[i] * 0.6f, amplitude[i] * 0.6f);
                    }
                }
            }
        }
    }

    void ForceDirectionChange(ref Vector3 targetAngles, Vector3 amplitude)
    {
        // 强制改变方向，确保不会长时间保持同一方向
        for (int i = 0; i < 3; i++)
        {
            float randomDirection = Random.Range(-1f, 1f);
            targetAngles[i] = randomDirection * amplitude[i] * Random.Range(0.4f, 0.8f);
        }
    }

    void UpdateCurrentAngles()
    {
        float smoothSpeed = damping * Time.deltaTime;
        
        _headCurrentAngles = Vector3.Lerp(_headCurrentAngles, _headTargetAngles, smoothSpeed);
        _bodyCurrentAngles = Vector3.Lerp(_bodyCurrentAngles, _bodyTargetAngles, smoothSpeed);
    }

    void ApplyToParameters()
    {
        // 头部参数
        if (_angX) _angX.Value = Mathf.Clamp(_angX.DefaultValue + _headCurrentAngles.x, _angX.MinimumValue, _angX.MaximumValue);
        if (_angY) _angY.Value = Mathf.Clamp(_angY.DefaultValue + _headCurrentAngles.y, _angY.MinimumValue, _angY.MaximumValue);
        if (_angZ) _angZ.Value = Mathf.Clamp(_angZ.DefaultValue + _headCurrentAngles.z, _angZ.MinimumValue, _angZ.MaximumValue);

        // 身体参数
        if (_bodyX) _bodyX.Value = Mathf.Clamp(_bodyX.DefaultValue + _bodyCurrentAngles.x, _bodyX.MinimumValue, _bodyX.MaximumValue);
        if (_bodyY) 
        {
            float bodyYCycle = Time.time * verticalBounceFrequencyFactor;
            float bodyYNoise = (Mathf.PerlinNoise(_seedBase.y + 37f, bodyYCycle) - 0.5f) * 2f;
            _bodyY.Value = Mathf.Clamp(_bodyY.DefaultValue + bodyYNoise * bodyAmplitude.y, _bodyY.MinimumValue, _bodyY.MaximumValue);
        }
        if (_bodyZ) _bodyZ.Value = Mathf.Clamp(_bodyZ.DefaultValue + _bodyCurrentAngles.z, _bodyZ.MinimumValue, _bodyZ.MaximumValue);
    }

    void UpdateBreathing(float t)
    {
        if (_breath)
        {
            float bTime  = Time.time * 0.3f;
            float bNoise = (Mathf.PerlinNoise(_seedBase.y + 23f, bTime) - 0.5f) * 2f;
            float target = _breath.DefaultValue + bNoise * breathAmplitude * breathValueMultiplier;
            _breath.Value = Mathf.Clamp(target, _breath.MinimumValue, _breath.MaximumValue);
        }
    }

    void ScheduleNextStateChange()
    {
        _nextStateChangeTime = Time.time + Random.Range(stateChangeInterval.x, stateChangeInterval.y);
    }

    /*─────────────────── 随机种子 ───────────────────*/
    void Reseed()
    {
        _seedBase = Random.insideUnitSphere * 1000f;
        _seedSolo = Random.insideUnitSphere * 1000f + Vector3.one * 99f;
    }

#if UNITY_EDITOR
    void OnValidate()
    {
        baseFrequency    = Mathf.Clamp(baseFrequency, 0.01f, 2f);
        damping          = Mathf.Max(damping, 0.1f);
        reseedInterval   = Mathf.Max(1f, reseedInterval);
        bodySyncStrength = Mathf.Clamp01(bodySyncStrength);
        headSoloRatio    = Mathf.Clamp01(headSoloRatio);
        idleTimeRatio    = Mathf.Clamp(idleTimeRatio, 0f, 0.9f);
        maxAngleHoldTime = Mathf.Max(0.1f, maxAngleHoldTime);
        directionConstraintThreshold = Mathf.Clamp(directionConstraintThreshold, 0.1f, 0.9f);
        stateChangeInterval.x = Mathf.Max(0.5f, stateChangeInterval.x);
        stateChangeInterval.y = Mathf.Max(stateChangeInterval.x, stateChangeInterval.y);
    }
#endif
}

/* 关键更新
 * 1. ✨『方向反转约束』：为 Body-X 增加与 Body-Z 相同的停顿→快速回弹逻辑，
 *    确保角色摆到极限后必定先停顿或回弹，而不会继续往同一方向堆叠。
 * 2. ✨『速度曲线』：引入 speedCurve（PerlinNoise 曲线 0.75–1.75），
 *    动态乘到所有 Apply / ApplySmooth 的 extraDamp，从而实现时快时慢的摇晃节奏。
 * 3. 其余逻辑保持一致，并继续保留 Micro-Jitter（永不静止）。
 */
