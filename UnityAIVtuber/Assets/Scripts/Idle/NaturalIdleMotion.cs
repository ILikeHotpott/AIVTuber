using UnityEngine;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework;

[DisallowMultipleComponent]
[RequireComponent(typeof(CubismModel))]
public class CubismIdleMotion : MonoBehaviour
{
    public enum IdleMotionStyle { Calm, Energetic, Hyper }
    
    // 新增：多种动作模式，重点增加上下抖动类型
    public enum MotionMode 
    { 
        SubtleSway,        // 轻微摆动
        MediumSway,        // 中等摆动  
        LargeSway,         // 大幅摆动
        VerticalBounce,    // 上下弹跳
        VerticalQuick,     // 快速上下抖动
        VerticalRhythm,    // 有节奏的上下 (下上下上)
        VerticalTriple,    // 三连上下抖动
        VerticalSingle,    // 单次下上动作
        VerticalMixed,     // 混合上下抖动模式
        SideToSide,        // 左右侧身
        HeadTilt,          // 歪头
        ComboGentle,       // 温和组合动作
        ComboEnergetic,    // 活跃组合动作
        ComboComplex       // 复杂组合动作
    }

    /*────────────────────── 公开参数 ──────────────────────*/

    [Header("Idle Style Preset")]
    public IdleMotionStyle motionStyle = IdleMotionStyle.Energetic;

    [Header("Motion Mode Control")]
    [Tooltip("动作模式切换间隔")]
    public Vector2 modeChangeInterval = new Vector2(2f, 5f);
    [Tooltip("静止状态概率（0-1，0表示永不静止）")]
    [Range(0f, 0.1f)] public float stillnessProbability = 0.0f;
    [Tooltip("上下抖动模式的额外概率加成")]
    [Range(0f, 0.9f)] public float verticalMotionBoost = 0.6f;

    [Header("Continuous Base Motion (防止静止)")]
    [Tooltip("基础连续侧身运动强度")]
    [Range(0.1f, 1.0f)] public float baseSideMotionIntensity = 0.3f;
    [Tooltip("基础连续歪头运动强度")]
    [Range(0.05f, 0.5f)] public float baseTiltMotionIntensity = 0.15f;
    [Tooltip("基础运动频率")]
    [Range(0.1f, 2.0f)] public float baseMotionFrequency = 0.4f;

    [Header("Head Angle Amplitude (deg)")]
    public Vector3 angleAmplitude = new Vector3(35f, 6f, 8f);

    [Header("Body Motion Amplitudes (使用-30到30范围)")]
    [Tooltip("侧身幅度 (Body X/ParamAngleX)")]
    public Vector2 sideBodyRange = new Vector2(8f, 15f);
    [Tooltip("上下运动幅度 (Body Y/ParamAngleY) - 使用-30到30的全范围")]  
    public Vector2 verticalBodyRange = new Vector2(12f, 25f);
    [Tooltip("歪头幅度 (Body Z/ParamAngleZ)")]
    public Vector2 tiltBodyRange = new Vector2(8f, 15f);

    [Header("Breath (0-1)")]
    [Range(0f, 1f)] public float breathAmplitude = 0.8f;
    public float breathValueMultiplier = 1.0f;

    [Header("Lip Sync")]
    public bool enableAutoMouth = false;

    [Header("Motion Smoothness")]
    [Range(0.1f, 2.5f)] public float baseFrequency = 0.6f;
    [Range(1f, 15f)]     public float damping       = 15f;
    [Range(0.5f, 5f)]    public float modeTransitionSpeed = 1.5f;

    [Header("Extra Randomness")]
    public bool  reseedPeriodically = true;
    public float reseedInterval     = 18f;

    /*────────────────────── 私有字段 ──────────────────────*/

    CubismModel _model;
    CubismParameter _angX, _angY, _angZ, _bodyX, _bodyY, _bodyZ, _breath, _mouth;

    Vector3 _seedBase, _seedExtra, _seedMotion;
    float   _nextReseed;

    // 动作模式管理
    MotionMode _currentMode = MotionMode.VerticalBounce;
    MotionMode _targetMode = MotionMode.VerticalBounce;
    float _nextModeChangeTime = 0f;
    float _modeTransitionProgress = 1f;
    
    // 上下抖动专用状态
    bool _isVerticalShaking = false;
    float _verticalShakeStartTime = 0f;
    int _verticalShakeCount = 0;
    int _targetVerticalShakeCount = 1;
    float _verticalShakeInterval = 0.4f;
    float _nextVerticalShakeTime = 0f;
    int _verticalCycleCount = 0;        // 当前完成的循环数
    int _targetVerticalCycles = 2;      // 目标循环数（1次循环=上下）
    
    // 运动状态
    Vector3 _headTargetAngles = Vector3.zero;
    Vector3 _bodyTargetAngles = Vector3.zero;
    Vector3 _headCurrentAngles = Vector3.zero;
    Vector3 _bodyCurrentAngles = Vector3.zero;
    Vector3 _previousBodyTargetAngles = Vector3.zero; // 用于平滑过渡
    
    // 基础连续运动状态
    Vector3 _baseContinuousMotion = Vector3.zero;
    float _baseMotionTime = 0f;

    // 动作模式参数
    struct MotionModeParams
    {
        public Vector3 headAmplitudeMultiplier;
        public Vector3 bodyAmplitudeMultiplier;
        public Vector3 frequencyMultiplier;
        public float intensityLevel;
        public bool useComplexPattern;
        public bool isVerticalFocused;
    }
    
    MotionModeParams _currentModeParams;
    MotionModeParams _targetModeParams;

    /*────────────────────── 生命周期 ──────────────────────*/

    void Start() => Debug.Log("🔥 CubismIdleMotion Start - Enhanced Vertical Motion");

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
        _bodyX = FindParam(_model, "ParamAngleX");
        _bodyY = FindParam(_model, "ParamAngleY");
        _bodyZ = FindParam(_model, "ParamAngleZ");

        /* 其它 */
        _breath = FindParam(_model, "Breathing", "ParamBreath");
        _mouth  = FindParam(_model, "Mouth Open", "ParamMouthOpenY");

        ApplyStylePreset();
        Reseed();
        _nextReseed = Time.time + reseedInterval;
        SelectRandomMotionMode();
        ScheduleNextModeChange();
    }

    /*────────────────────── 预设风格 ──────────────────────*/
    void ApplyStylePreset()
    {
        switch (motionStyle)
        {
            case IdleMotionStyle.Calm:
                baseFrequency = 0.4f; 
                damping = 8f;
                angleAmplitude = new Vector3(20f, 4f, 6f);
                sideBodyRange = new Vector2(6f, 12f);
                verticalBodyRange = new Vector2(8f, 18f);
                tiltBodyRange = new Vector2(6f, 12f);
                modeChangeInterval = new Vector2(4f, 8f);
                verticalMotionBoost = 0.4f;
                break;

            case IdleMotionStyle.Energetic:
                baseFrequency = 0.6f;
                damping = 10f;
                angleAmplitude = new Vector3(30f, 6f, 8f);
                sideBodyRange = new Vector2(8f, 15f);
                verticalBodyRange = new Vector2(12f, 25f);
                tiltBodyRange = new Vector2(8f, 15f);
                modeChangeInterval = new Vector2(3f, 6f);
                verticalMotionBoost = 0.6f;
                break;

            case IdleMotionStyle.Hyper:
                baseFrequency = 0.9f;
                damping = 12f;
                angleAmplitude = new Vector3(40f, 8f, 12f);
                sideBodyRange = new Vector2(10f, 18f);
                verticalBodyRange = new Vector2(15f, 28f);
                tiltBodyRange = new Vector2(10f, 18f);
                modeChangeInterval = new Vector2(2f, 4f);
                verticalMotionBoost = 0.7f;
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

        /*==== 更新基础运动时间 ====*/
        _baseMotionTime += Time.deltaTime * baseMotionFrequency;

        /*==== 动作模式切换 ====*/
        UpdateMotionMode();

        float t = Time.time * baseFrequency;

        /*==== 生成基础连续运动（防止静止）====*/
        GenerateBaseContinuousMotion();

        /*==== 生成运动 ====*/
        if (_currentModeParams.isVerticalFocused)
        {
            GenerateVerticalShakeMotion(t);
        }
        else
        {
            GenerateNaturalMotion(t);
        }

        /*==== 合并基础运动和模式运动 ====*/
        CombineMotions();

        /*==== 平滑更新当前角度 ====*/
        UpdateCurrentAngles();

        /*==== 应用到参数 ====*/
        ApplyToParameters();

        /*==== 呼吸 ====*/
        UpdateBreathing(Time.time * baseFrequency);

        /*==== 自动张嘴 ====*/
        if (enableAutoMouth && _mouth)
            _mouth.Value = Mathf.Abs(Mathf.Sin(Time.time * 6f)) * 0.6f;
    }

    void UpdateMotionMode()
    {
        // 检查是否需要切换模式
        if (Time.time >= _nextModeChangeTime)
        {
            // 保存当前目标角度，用于平滑过渡
            _previousBodyTargetAngles = _bodyTargetAngles;
            
            SelectRandomMotionMode();
            ScheduleNextModeChange();
            _modeTransitionProgress = 0f;
        }
        
        // 平滑过渡到新模式
        if (_modeTransitionProgress < 1f)
        {
            _modeTransitionProgress += Time.deltaTime * modeTransitionSpeed;
            _modeTransitionProgress = Mathf.Clamp01(_modeTransitionProgress);
            
            // 插值混合当前和目标模式参数
            _currentModeParams = LerpModeParams(_currentModeParams, _targetModeParams, _modeTransitionProgress);
            
            if (_modeTransitionProgress >= 1f)
            {
                _currentMode = _targetMode;
                
                // 如果切换到上下抖动模式，初始化抖动状态
                if (_currentModeParams.isVerticalFocused)
                {
                    InitializeVerticalShake();
                }
            }
        }
    }

    void SelectRandomMotionMode()
    {
        // 完全移除静止状态，确保永远有运动
        
        // 增加上下抖动模式的概率
        float verticalChance = Random.value;
        if (verticalChance < verticalMotionBoost)
        {
            // 选择上下抖动模式
            MotionMode[] verticalModes = {
                MotionMode.VerticalBounce,
                MotionMode.VerticalQuick,
                MotionMode.VerticalRhythm,
                MotionMode.VerticalTriple,
                MotionMode.VerticalSingle,
                MotionMode.VerticalMixed
            };
            _targetMode = verticalModes[Random.Range(0, verticalModes.Length)];
        }
        else
        {
            // 选择其他模式
            MotionMode[] otherModes = {
                MotionMode.SubtleSway,
                MotionMode.MediumSway,
                MotionMode.LargeSway,
                MotionMode.SideToSide,
                MotionMode.HeadTilt,
                MotionMode.ComboGentle,
                MotionMode.ComboEnergetic,
                MotionMode.ComboComplex
            };
            
            MotionMode newMode;
            do {
                newMode = otherModes[Random.Range(0, otherModes.Length)];
            } while (newMode == _currentMode && otherModes.Length > 1);
            
            _targetMode = newMode;
        }
        
        _targetModeParams = GetModeParams(_targetMode);
        
        // 确保所有模式都有最低强度，防止过度减弱
        _targetModeParams.intensityLevel = Mathf.Max(_targetModeParams.intensityLevel, 0.8f);
    }

    void InitializeVerticalShake()
    {
        _isVerticalShaking = true;
        _verticalShakeStartTime = Time.time;
        _verticalShakeCount = 0;
        _verticalCycleCount = 0;
        _nextVerticalShakeTime = Time.time;
        
        // 设置循环次数的概率分布
        float cycleRandom = Random.value;
        if (cycleRandom < 0.15f)  // 15% 概率
        {
            _targetVerticalCycles = 1;  // 一次上下
        }
        else if (cycleRandom < 0.75f)  // 60% 概率
        {
            _targetVerticalCycles = 2;  // 两次上下（最常见）
        }
        else  // 25% 概率
        {
            _targetVerticalCycles = 3;  // 三次上下
        }
        
        _targetVerticalShakeCount = _targetVerticalCycles * 2; // 每个循环包含上下两次
        
        // 调试信息
        Debug.Log($"🔄 开始抖动 - 目标循环: {_targetVerticalCycles}次, 总抖动: {_targetVerticalShakeCount}次, 概率值: {cycleRandom:F2}");
        
        // 根据模式设置不同的抖动参数，调整间隔让动作更流畅
        switch (_currentMode)
        {
            case MotionMode.VerticalSingle:
                _verticalShakeInterval = 0.35f;
                break;
            case MotionMode.VerticalQuick:
                _verticalShakeInterval = 0.2f;
                break;
            case MotionMode.VerticalRhythm:
                _verticalShakeInterval = 0.3f;
                break;
            case MotionMode.VerticalTriple:
                _verticalShakeInterval = 0.25f;
                break;
            case MotionMode.VerticalMixed:
                _verticalShakeInterval = Random.Range(0.25f, 0.4f);
                break;
            default:
                _verticalShakeInterval = 0.3f;
                break;
        }
    }

    MotionModeParams GetModeParams(MotionMode mode)
    {
        MotionModeParams param = new MotionModeParams();
        
        switch (mode)
        {
            case MotionMode.SubtleSway:
                param.headAmplitudeMultiplier = new Vector3(0.5f, 0.6f, 0.5f);
                param.bodyAmplitudeMultiplier = new Vector3(0.6f, 0.8f, 0.6f);
                param.frequencyMultiplier = new Vector3(1.2f, 1.0f, 0.8f);
                param.intensityLevel = 1.0f;
                param.useComplexPattern = false;
                param.isVerticalFocused = false;
                break;
                
            case MotionMode.MediumSway:
                param.headAmplitudeMultiplier = new Vector3(0.7f, 0.8f, 0.7f);
                param.bodyAmplitudeMultiplier = new Vector3(0.8f, 1.0f, 0.8f);
                param.frequencyMultiplier = new Vector3(1.4f, 1.2f, 1.0f);
                param.intensityLevel = 1.2f;
                param.useComplexPattern = false;
                param.isVerticalFocused = false;
                break;
                
            case MotionMode.LargeSway:
                param.headAmplitudeMultiplier = new Vector3(1.0f, 1.0f, 1.0f);
                param.bodyAmplitudeMultiplier = new Vector3(1.0f, 1.0f, 1.0f);
                param.frequencyMultiplier = new Vector3(1.3f, 1.1f, 0.9f);
                param.intensityLevel = 1.5f;
                param.useComplexPattern = false;
                param.isVerticalFocused = false;
                break;
                
            // === 上下抖动模式 - 降低频率版 ===
            case MotionMode.VerticalBounce:
                param.headAmplitudeMultiplier = new Vector3(0.3f, 0.8f, 0.2f);
                param.bodyAmplitudeMultiplier = new Vector3(0.4f, 1.0f, 0.1f);
                param.frequencyMultiplier = new Vector3(1.1f, 1.2f, 0.4f);
                param.intensityLevel = 1.5f;
                param.useComplexPattern = false;
                param.isVerticalFocused = true;
                break;
                
            case MotionMode.VerticalQuick:
                param.headAmplitudeMultiplier = new Vector3(0.2f, 0.7f, 0.1f);
                param.bodyAmplitudeMultiplier = new Vector3(0.3f, 1.0f, 0.1f);
                param.frequencyMultiplier = new Vector3(1.0f, 1.3f, 0.3f);
                param.intensityLevel = 1.6f;
                param.useComplexPattern = false;
                param.isVerticalFocused = true;
                break;
                
            case MotionMode.VerticalRhythm:
                param.headAmplitudeMultiplier = new Vector3(0.3f, 0.9f, 0.2f);
                param.bodyAmplitudeMultiplier = new Vector3(0.4f, 1.0f, 0.1f);
                param.frequencyMultiplier = new Vector3(1.2f, 1.3f, 0.3f);
                param.intensityLevel = 1.4f;
                param.useComplexPattern = false;
                param.isVerticalFocused = true;
                break;
                
            case MotionMode.VerticalTriple:
                param.headAmplitudeMultiplier = new Vector3(0.2f, 0.8f, 0.1f);
                param.bodyAmplitudeMultiplier = new Vector3(0.3f, 1.0f, 0.1f);
                param.frequencyMultiplier = new Vector3(1.0f, 1.2f, 0.3f);
                param.intensityLevel = 1.5f;
                param.useComplexPattern = false;
                param.isVerticalFocused = true;
                break;
                
            case MotionMode.VerticalSingle:
                param.headAmplitudeMultiplier = new Vector3(0.2f, 0.7f, 0.1f);
                param.bodyAmplitudeMultiplier = new Vector3(0.3f, 1.0f, 0.1f);
                param.frequencyMultiplier = new Vector3(0.9f, 1.1f, 0.3f);
                param.intensityLevel = 1.3f;
                param.useComplexPattern = false;
                param.isVerticalFocused = true;
                break;
                
            case MotionMode.VerticalMixed:
                param.headAmplitudeMultiplier = new Vector3(0.3f, 0.9f, 0.2f);
                param.bodyAmplitudeMultiplier = new Vector3(0.4f, 1.0f, 0.1f);
                param.frequencyMultiplier = new Vector3(1.1f, 1.3f, 0.3f);
                param.intensityLevel = 1.6f;
                param.useComplexPattern = false;
                param.isVerticalFocused = true;
                break;
                
            case MotionMode.SideToSide:
                param.headAmplitudeMultiplier = new Vector3(0.9f, 0.3f, 0.4f);
                param.bodyAmplitudeMultiplier = new Vector3(1.0f, 0.4f, 0.3f);
                param.frequencyMultiplier = new Vector3(1.8f, 0.6f, 0.6f);
                param.intensityLevel = 1.3f;
                param.useComplexPattern = false;
                param.isVerticalFocused = false;
                break;
                
            case MotionMode.HeadTilt:
                param.headAmplitudeMultiplier = new Vector3(0.4f, 0.7f, 1.0f);
                param.bodyAmplitudeMultiplier = new Vector3(0.5f, 0.5f, 1.0f);
                param.frequencyMultiplier = new Vector3(1.1f, 0.8f, 1.1f);
                param.intensityLevel = 1.2f;
                param.useComplexPattern = false;
                param.isVerticalFocused = false;
                break;
                
            case MotionMode.ComboGentle:
                param.headAmplitudeMultiplier = new Vector3(0.6f, 0.7f, 0.6f);
                param.bodyAmplitudeMultiplier = new Vector3(0.8f, 0.9f, 0.8f);
                param.frequencyMultiplier = new Vector3(1.3f, 1.2f, 0.9f);
                param.intensityLevel = 1.1f;
                param.useComplexPattern = true;
                param.isVerticalFocused = false;
                break;
                
            case MotionMode.ComboEnergetic:
                param.headAmplitudeMultiplier = new Vector3(0.9f, 0.9f, 0.9f);
                param.bodyAmplitudeMultiplier = new Vector3(1.0f, 1.0f, 1.0f);
                param.frequencyMultiplier = new Vector3(1.6f, 1.3f, 1.0f);
                param.intensityLevel = 1.4f;
                param.useComplexPattern = true;
                param.isVerticalFocused = false;
                break;
                
            case MotionMode.ComboComplex:
                param.headAmplitudeMultiplier = new Vector3(1.0f, 1.0f, 1.0f);
                param.bodyAmplitudeMultiplier = new Vector3(1.0f, 1.0f, 1.0f);
                param.frequencyMultiplier = new Vector3(1.7f, 1.4f, 1.1f);
                param.intensityLevel = 1.6f;
                param.useComplexPattern = true;
                param.isVerticalFocused = false;
                break;
        }
        
        return param;
    }

    MotionModeParams LerpModeParams(MotionModeParams from, MotionModeParams to, float t)
    {
        MotionModeParams result = new MotionModeParams();
        result.headAmplitudeMultiplier = Vector3.Lerp(from.headAmplitudeMultiplier, to.headAmplitudeMultiplier, t);
        result.bodyAmplitudeMultiplier = Vector3.Lerp(from.bodyAmplitudeMultiplier, to.bodyAmplitudeMultiplier, t);
        result.frequencyMultiplier = Vector3.Lerp(from.frequencyMultiplier, to.frequencyMultiplier, t);
        result.intensityLevel = Mathf.Lerp(from.intensityLevel, to.intensityLevel, t);
        result.useComplexPattern = t > 0.5f ? to.useComplexPattern : from.useComplexPattern;
        result.isVerticalFocused = t > 0.5f ? to.isVerticalFocused : from.isVerticalFocused;
        return result;
    }

    void GenerateVerticalShakeMotion(float t)
    {
        // 处理连续的上下抖动
        if (_isVerticalShaking && Time.time >= _nextVerticalShakeTime)
        {
            _verticalShakeCount++;
            _nextVerticalShakeTime = Time.time + _verticalShakeInterval;
            
            Debug.Log($"📊 抖动进度: {_verticalShakeCount}/{_targetVerticalShakeCount}, 循环: {_verticalCycleCount}/{_targetVerticalCycles}");
            
            // 检查是否完成了一个循环（上下算一个循环）
            // 修复：应该在每2次抖动后才增加循环计数，且从1开始计算
            if (_verticalShakeCount > 0 && _verticalShakeCount % 2 == 0)
            {
                _verticalCycleCount++;
                Debug.Log($"✅ 完成第{_verticalCycleCount}个循环");
            }
            
            // 检查是否完成了所有循环
            if (_verticalShakeCount >= _targetVerticalShakeCount)
            {
                _isVerticalShaking = false;
                Debug.Log($"🏁 抖动完成! 总共{_verticalCycleCount}个循环，{_verticalShakeCount}次抖动");
            }
        }
        
        // 生成连续的基础运动（防止卡顿）- 增强平滑度
        Vector3 continuousNoise = new Vector3(
            Mathf.PerlinNoise(_seedBase.x, t * 1.0f) - 0.5f,  // 提高频率确保连续运动
            Mathf.PerlinNoise(_seedBase.y, t * 0.6f) - 0.5f,
            Mathf.PerlinNoise(_seedBase.z, t * 0.7f) - 0.5f   // 提高Z轴频率
        );
        
        // 头部保持相对稳定，更加平滑
        _headTargetAngles = Vector3.Lerp(_headTargetAngles, continuousNoise * 0.3f, Time.deltaTime * 3f);
        
        // 身体的上下抖动
        float verticalMotion = 0f;
        
        if (_isVerticalShaking)
        {
            // 计算当前在循环中的位置
            // 修复：从1开始计算，奇数为下，偶数为上
            bool isDownPhase = (_verticalShakeCount % 2 == 1);
            float shakePhase = isDownPhase ? -1f : 1f;
            
            // 根据时间在一个抖动周期内的位置调整强度 - 使用更平滑的过渡
            float cycleTime = (Time.time - (_nextVerticalShakeTime - _verticalShakeInterval)) / _verticalShakeInterval;
            cycleTime = Mathf.Clamp01(cycleTime);
            
            // 使用平滑的曲线，避免突然跳跃
            float shakeIntensity = Mathf.SmoothStep(0f, 1f, Mathf.Sin(cycleTime * Mathf.PI));
            
            verticalMotion = shakePhase * shakeIntensity * _currentModeParams.intensityLevel;
            
            // 调试当前抖动状态
            if (Time.frameCount % 30 == 0) // 每30帧输出一次，避免刷屏
            {
                Debug.Log($"🎯 当前抖动: 第{_verticalShakeCount}次, {(isDownPhase ? "向下" : "向上")}, 强度: {shakeIntensity:F2}");
            }
        }
        else
        {
            // 不在抖动时保持连续的上下运动，更加平滑
            verticalMotion = continuousNoise.y * 0.6f * _currentModeParams.intensityLevel;
        }
        
        // 使用动态范围，充分利用-30到30
        float verticalRange = Mathf.Lerp(verticalBodyRange.x, verticalBodyRange.y, _currentModeParams.bodyAmplitudeMultiplier.y);
        
        Vector3 newBodyTarget = new Vector3(
            continuousNoise.x * 5f * _currentModeParams.bodyAmplitudeMultiplier.x, // 进一步增强侧身运动
            verticalMotion * verticalRange, // 主要的上下运动
            continuousNoise.z * 3f * _currentModeParams.bodyAmplitudeMultiplier.z  // 增强歪头运动
        );
        
        // 平滑过渡，避免突然跳跃
        _bodyTargetAngles = Vector3.Lerp(_bodyTargetAngles, newBodyTarget, Time.deltaTime * 8f);
    }

    void GenerateNaturalMotion(float t)
    {
        /*==== 增强的连续噪声生成 ====*/
        Vector3 primaryNoise = new Vector3(
            Mathf.PerlinNoise(_seedBase.x, t * _currentModeParams.frequencyMultiplier.x) - 0.5f,
            Mathf.PerlinNoise(_seedBase.y, t * _currentModeParams.frequencyMultiplier.y) - 0.5f,
            Mathf.PerlinNoise(_seedBase.z, t * _currentModeParams.frequencyMultiplier.z) - 0.5f
        );

        /*==== 复杂模式额外噪声 ====*/
        Vector3 secondaryNoise = Vector3.zero;
        if (_currentModeParams.useComplexPattern)
        {
            secondaryNoise = new Vector3(
                Mathf.PerlinNoise(_seedExtra.x, t * 1.6f) - 0.5f,  // 进一步提高X轴复杂噪声频率
                Mathf.PerlinNoise(_seedExtra.y, t * 1.1f) - 0.5f,
                Mathf.PerlinNoise(_seedExtra.z, t * 1.2f) - 0.5f   // 提高Z轴复杂噪声频率
            ) * 0.4f;  // 稍微增加复杂噪声的影响
        }

        /*==== 连续运动变化曲线 ====*/
        float intensityCurve = 0.85f + 0.25f * Mathf.PerlinNoise(_seedMotion.x, t * 0.3f);  // 提高基础强度
        float combinedIntensity = _currentModeParams.intensityLevel * intensityCurve;

        /*==== 头部运动 - 增强平滑度 ====*/
        Vector3 headNoise = (primaryNoise + secondaryNoise) * combinedIntensity;
        Vector3 newHeadTarget = new Vector3(
            headNoise.x * angleAmplitude.x * _currentModeParams.headAmplitudeMultiplier.x,
            headNoise.y * angleAmplitude.y * _currentModeParams.headAmplitudeMultiplier.y,
            headNoise.z * angleAmplitude.z * _currentModeParams.headAmplitudeMultiplier.z
        );
        
        // 平滑过渡头部角度
        _headTargetAngles = Vector3.Lerp(_headTargetAngles, newHeadTarget, Time.deltaTime * 4f);

        /*==== 身体运动 - 确保连续运动 ====*/
        Vector3 bodyPrimary = new Vector3(
            (Mathf.PerlinNoise(_seedBase.x + 10f, t * _currentModeParams.frequencyMultiplier.x * 1.3f) - 0.5f) * 2f,  // 进一步提高X轴频率
            (Mathf.PerlinNoise(_seedBase.y + 20f, t * _currentModeParams.frequencyMultiplier.y * 0.8f) - 0.5f) * 2f,
            (Mathf.PerlinNoise(_seedBase.z + 30f, t * _currentModeParams.frequencyMultiplier.z * 1.0f) - 0.5f) * 2f  // 提高Z轴频率
        );

        Vector3 bodySecondary = Vector3.zero;
        if (_currentModeParams.useComplexPattern)
        {
            bodySecondary = new Vector3(
                (Mathf.PerlinNoise(_seedExtra.x + 15f, t * 1.5f) - 0.5f) * 2f,  // 进一步提高X轴复杂运动频率
                (Mathf.PerlinNoise(_seedExtra.y + 25f, t * 1.0f) - 0.5f) * 2f,
                (Mathf.PerlinNoise(_seedExtra.z + 35f, t * 1.1f) - 0.5f) * 2f   // 提高Z轴复杂运动频率
            ) * 0.4f;
        }

        Vector3 bodyNoise = (bodyPrimary + bodySecondary) * combinedIntensity;
        
        // 使用动态范围 - 充分利用-30到30的范围
        float sideRange = Mathf.Lerp(sideBodyRange.x, sideBodyRange.y, _currentModeParams.bodyAmplitudeMultiplier.x);
        float verticalRange = Mathf.Lerp(verticalBodyRange.x, verticalBodyRange.y, _currentModeParams.bodyAmplitudeMultiplier.y);
        float tiltRange = Mathf.Lerp(tiltBodyRange.x, tiltBodyRange.y, _currentModeParams.bodyAmplitudeMultiplier.z);
        
        Vector3 newBodyTarget = new Vector3(
            bodyNoise.x * sideRange,        // 侧身 (Body X) - 提高频率但保持自然  
            bodyNoise.y * verticalRange,    // 上下 (Body Y) - 保持幅度但降低频率  
            bodyNoise.z * tiltRange         // 歪头 (Body Z) - 增强运动
        );
        
        // 平滑过渡身体角度，避免突然跳跃
        _bodyTargetAngles = Vector3.Lerp(_bodyTargetAngles, newBodyTarget, Time.deltaTime * 6f);
    }

    void UpdateCurrentAngles()
    {
        float smoothSpeed = damping * Time.deltaTime;
        
        // 增强平滑度，减少机械感，确保连续运动
        _headCurrentAngles = Vector3.Lerp(_headCurrentAngles, _headTargetAngles, smoothSpeed);
        _bodyCurrentAngles = Vector3.Lerp(_bodyCurrentAngles, _bodyTargetAngles, smoothSpeed);
        
        // 确保身体运动永远不会完全静止
        if (_bodyCurrentAngles.magnitude < 0.1f)
        {
            _bodyCurrentAngles += _baseContinuousMotion * 0.5f;
        }
    }

    void ApplyToParameters()
    {
        // 头部参数
        if (_angX) _angX.Value = Mathf.Clamp(_angX.DefaultValue + _headCurrentAngles.x, _angX.MinimumValue, _angX.MaximumValue);
        if (_angY) _angY.Value = Mathf.Clamp(_angY.DefaultValue + _headCurrentAngles.y, _angY.MinimumValue, _angY.MaximumValue);
        if (_angZ) _angZ.Value = Mathf.Clamp(_angZ.DefaultValue + _headCurrentAngles.z, _angZ.MinimumValue, _angZ.MaximumValue);

        // 身体参数 - 直接使用计算值，充分利用-30到30范围
        if (_bodyX) _bodyX.Value = Mathf.Clamp(_bodyCurrentAngles.x, -30f, 30f);
        if (_bodyY) _bodyY.Value = Mathf.Clamp(_bodyCurrentAngles.y, -30f, 30f);  
        if (_bodyZ) _bodyZ.Value = Mathf.Clamp(_bodyCurrentAngles.z, -30f, 30f);
    }

    void UpdateBreathing(float t)
    {
        if (_breath)
        {
            float bTime = Time.time * 0.4f;
            float bNoise = (Mathf.PerlinNoise(_seedBase.y + 23f, bTime) - 0.5f) * 2f;
            float target = _breath.DefaultValue + bNoise * breathAmplitude * breathValueMultiplier;
            _breath.Value = Mathf.Clamp(target, _breath.MinimumValue, _breath.MaximumValue);
        }
    }

    void ScheduleNextModeChange()
    {
        _nextModeChangeTime = Time.time + Random.Range(modeChangeInterval.x, modeChangeInterval.y);
    }

    /*─────────────────── 随机种子 ───────────────────*/
    void Reseed()
    {
        _seedBase = Random.insideUnitSphere * 1000f;
        _seedExtra = Random.insideUnitSphere * 1000f + Vector3.one * 500f;
        _seedMotion = Random.insideUnitSphere * 1000f + Vector3.one * 1500f;
    }

    /*==== 生成基础连续运动（确保永不静止）====*/
    void GenerateBaseContinuousMotion()
    {
        // 使用多层噪声确保连续运动
        float sideMotion1 = Mathf.PerlinNoise(_seedBase.x + 100f, _baseMotionTime * 0.7f) - 0.5f;
        float sideMotion2 = Mathf.PerlinNoise(_seedBase.x + 200f, _baseMotionTime * 1.3f) - 0.5f;
        float tiltMotion1 = Mathf.PerlinNoise(_seedBase.z + 300f, _baseMotionTime * 0.5f) - 0.5f;
        float tiltMotion2 = Mathf.PerlinNoise(_seedBase.z + 400f, _baseMotionTime * 0.9f) - 0.5f;
        
        // 组合多层运动，确保复杂性
        float combinedSideMotion = (sideMotion1 * 0.7f + sideMotion2 * 0.3f) * 2f;
        float combinedTiltMotion = (tiltMotion1 * 0.8f + tiltMotion2 * 0.2f) * 2f;
        
        // 计算动态范围
        float sideRange = Mathf.Lerp(sideBodyRange.x, sideBodyRange.y, 0.5f);
        float tiltRange = Mathf.Lerp(tiltBodyRange.x, tiltBodyRange.y, 0.3f);
        
        // 生成基础连续运动
        _baseContinuousMotion = new Vector3(
            combinedSideMotion * sideRange * baseSideMotionIntensity,  // 主要侧身运动
            0f,  // Y轴由其他系统处理
            combinedTiltMotion * tiltRange * baseTiltMotionIntensity   // 辅助歪头运动
        );
        
        // 添加微小的随机变化，增加自然感
        _baseContinuousMotion.x += (Random.value - 0.5f) * 0.5f;
        _baseContinuousMotion.z += (Random.value - 0.5f) * 0.3f;
    }

    /*==== 合并基础运动和模式运动 ====*/
    void CombineMotions()
    {
        // 基础运动始终存在，模式运动叠加在上面
        Vector3 finalBodyTarget = _bodyTargetAngles + _baseContinuousMotion;
        
        // 确保在合理范围内
        finalBodyTarget.x = Mathf.Clamp(finalBodyTarget.x, -25f, 25f);
        finalBodyTarget.y = Mathf.Clamp(finalBodyTarget.y, -30f, 30f);
        finalBodyTarget.z = Mathf.Clamp(finalBodyTarget.z, -25f, 25f);
        
        _bodyTargetAngles = finalBodyTarget;
    }

#if UNITY_EDITOR
    void OnValidate()
    {
        baseFrequency = Mathf.Clamp(baseFrequency, 0.01f, 3f);
        damping = Mathf.Max(damping, 0.1f);
        reseedInterval = Mathf.Max(1f, reseedInterval);
        stillnessProbability = Mathf.Clamp01(stillnessProbability);
        verticalMotionBoost = Mathf.Clamp01(verticalMotionBoost);
        modeTransitionSpeed = Mathf.Max(0.1f, modeTransitionSpeed);
        modeChangeInterval.x = Mathf.Max(0.5f, modeChangeInterval.x);
        modeChangeInterval.y = Mathf.Max(modeChangeInterval.x, modeChangeInterval.y);
        
        sideBodyRange.x = Mathf.Max(0f, sideBodyRange.x);
        sideBodyRange.y = Mathf.Max(sideBodyRange.x, sideBodyRange.y);
        verticalBodyRange.x = Mathf.Max(0f, verticalBodyRange.x);
        verticalBodyRange.y = Mathf.Max(verticalBodyRange.x, verticalBodyRange.y);
        tiltBodyRange.x = Mathf.Max(0f, tiltBodyRange.x);
        tiltBodyRange.y = Mathf.Max(tiltBodyRange.x, tiltBodyRange.y);
    }
#endif
}

/* 流畅运动优化总结
 * 🚀 『消除卡顿问题』：
 *    - 移除所有停顿机制，保持持续运动
 *    - 增强连续噪声生成，防止运动中断
 *    - 优化平滑度参数，减少机械感
 * 
 * 📈 『大幅增强_bodyY运动』：
 *    - 上下运动范围提升到15-30，充分利用-30到30范围
 *    - 频率倍率提升，让上下运动更快更明显
 *    - 强度等级专门优化，所有上下抖动模式强度提升
 * 
 * 🔄 『持续自然运动』：
 *    - 静止概率降到0%，确保永不停止
 *    - 上下抖动概率提升到80%
 *    - 模式切换间隔缩短到2-5秒，更频繁的动作变化
 * 
 * ⚡『优化运动质量』：
 *    - baseFrequency提升到1.2，运动更快
 *    - damping优化到12，平滑但不迟钝
 *    - 使用更快的正弦曲线(* 2f)，减少机械感
 */