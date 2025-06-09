using System.Collections;
using UnityEngine;
using Live2D.Cubism.Core;

[DisallowMultipleComponent]
[DefaultExecutionOrder(1000)]
public class HeadShake : MonoBehaviour
{
    [System.Serializable]
    public class PhysicsSettings
    {
        [Header("Animal Physics")]
        [SerializeField] [Range(0.1f, 100f)] public float effectiveMass = 5f; // kg (cat~5kg, small dog~10kg, horse~500kg)
        [SerializeField] [Range(0.1f, 0.8f)] public float dampingRatio = 0.3f; // ζ ∈ [0.2, 0.4] for natural feel
        
        [Header("Motion Profile")]
        [SerializeField] [Range(20f, 45f)] public float maxAmplitude = 45f; // degrees, Changed from 40f to 45f (max of its range)
        [SerializeField] [Range(0.5f, 3f)] public float shakeDuration = 2f; // total shake time
        [SerializeField] public AnimationCurve amplitudeEnvelope = AnimationCurve.EaseInOut(0f, 1f, 1f, 0f);
        [SerializeField] public AnimationCurve frequencyEnvelope = AnimationCurve.Linear(0f, 1f, 1f, 0.7f);
    }

    [System.Serializable]
    public class NoiseSettings
    {
        [Header("Perlin Noise Layers")]
        [SerializeField] [Range(0f, 5f)] public float noiseAmplitude = 1.5f; // degrees
        [SerializeField] [Range(1f, 20f)] public float primaryFreq = 6f; // Hz
        [SerializeField] [Range(0f, 1f)] public float secondaryGain = 0.5f;
        [SerializeField] [Range(0f, 1f)] public float tertiaryGain = 0.25f;
        [SerializeField] [Range(0f, 360f)] public float phaseOffset = 0f; // for variation
    }

    [System.Serializable]
    public class AxisSettings
    {
        [Header("Multi-Axis Parameters")]
        [SerializeField] public string paramId = "ParamAngleX";
        [SerializeField] [Range(0f, 1f)] public float weight = 1f;
        [SerializeField] [Range(-180f, 180f)] public float phaseOffset = 0f; // degrees
        [SerializeField] [Range(0f, 2f)] public float amplitudeScale = 1f;
        
        [HideInInspector] public CubismParameter parameter;
        [HideInInspector] public float currentValue;
        [HideInInspector] public float velocity;
    }

    [Header("Cubism Model")]
    [SerializeField] private CubismModel _model = null;

    [Header("Physics Configuration")]
    [SerializeField] private PhysicsSettings _physics = new PhysicsSettings();
    
    [Header("Noise Configuration")]
    [SerializeField] private NoiseSettings _noise = new NoiseSettings();

    [Header("Motion Axes")]
    [SerializeField] private AxisSettings[] _axes = new AxisSettings[]
    {
        new AxisSettings { paramId = "ParamAngleX", weight = 1f, phaseOffset = 0f, amplitudeScale = 1f },
        new AxisSettings { paramId = "ParamAngleY", weight = 0.3f, phaseOffset = 45f, amplitudeScale = 0.6f },
        new AxisSettings { paramId = "ParamAngleZ", weight = 0.2f, phaseOffset = -30f, amplitudeScale = 0.4f }
    };

    [Header("Trigger Settings")]
    [SerializeField] private float _triggerInterval = 0f; // Changed from 0.2f to 0f for continuous shaking
    [SerializeField] [Range(0f, 1f)] private float _triggerProbability = 1f;
    [SerializeField] private bool _autoTrigger = true;

    // Physics state
    private struct OscillatorState
    {
        public float position;
        public float velocity;
        public float phase;
        public float amplitude;
        public float frequency;
        public float dampingCoeff;
        public float springConstant;
        public float mass;
    }

    // Runtime variables
    private bool _isShaking = false;
    private float _shakeStartTime;
    private Coroutine _continuousShakeCoroutine; // Added for new logic
    private OscillatorState _oscillator;
    private Vector3 _noiseSeeds; // for independent Perlin noise per axis

    // Cached calculations
    private float _baseFrequency;
    private float _naturalPeriod;

    public bool IsShaking => _isShaking;
    public float ShakeProgress => _isShaking ? Mathf.Clamp01((Time.time - _shakeStartTime) / _physics.shakeDuration) : 0f;

    #region Unity Lifecycle

    private void Awake()
    {
        InitializeModel();
        InitializePhysics();
        GenerateNoiseSeeds();
    }

    private void Update()
    {
        if (_autoTrigger)
        {
            if (_continuousShakeCoroutine == null)
            {
                _continuousShakeCoroutine = StartCoroutine(ContinuousShakeRoutine());
            }
        }
        else
        {
            if (_continuousShakeCoroutine != null)
            {
                StopCoroutine(_continuousShakeCoroutine);
                _continuousShakeCoroutine = null;
            }
        }
    }

    private void LateUpdate()
    {
        if (_isShaking)
        {
            UpdatePhysicsSimulation();
            ApplyMotionToParameters();
            
            // Check if shake should end
            if (ShakeProgress >= 1f && Mathf.Abs(_oscillator.velocity) < 0.1f)
            {
                EndShake();
            }
        }
    }

    #endregion

    #region Initialization

    private void InitializeModel()
    {
        if (_model == null) _model = GetComponent<CubismModel>();
        if (_model == null)
        {
            Debug.LogError("[HeadShake] No CubismModel found on GameObject", this);
            enabled = false;
            return;
        }

        // Initialize parameter references
        foreach (var axis in _axes)
        {
            axis.parameter = _model.Parameters.FindById(axis.paramId);
            if (axis.parameter == null)
            {
                Debug.LogWarning($"[HeadShake] Parameter '{axis.paramId}' not found in model", this);
            }
        }
    }

    private void InitializePhysics()
    {
        // Calculate base frequency using animal research: f ≈ 2.8 * m^(-0.22)
        _baseFrequency = 2.8f * Mathf.Pow(_physics.effectiveMass, -0.22f);
        _naturalPeriod = 1f / _baseFrequency;
        
        Debug.Log($"[HeadShake] Physics initialized - Mass: {_physics.effectiveMass}kg, Base Frequency: {_baseFrequency:F2}Hz");
    }

    private void GenerateNoiseSeeds()
    {
        _noiseSeeds = new Vector3(
            Random.Range(0f, 1000f),
            Random.Range(0f, 1000f),
            Random.Range(0f, 1000f)
        );
    }

    #endregion

    #region Trigger System

    public void TriggerShake()
    {
        if (_isShaking) EndShake();
        StartShake();
    }

    public void TriggerShakeWithIntensity(float intensity)
    {
        float oldAmplitude = _physics.maxAmplitude;
        _physics.maxAmplitude *= Mathf.Max(0f, intensity);
        TriggerShake();
        _physics.maxAmplitude = oldAmplitude;
    }

    #endregion

    #region Physics Simulation

    private void StartShake()
    {
        if (_continuousShakeCoroutine != null)
        {
            StopCoroutine(_continuousShakeCoroutine);
            _continuousShakeCoroutine = null;
            // Force reset parameters to default if return was interrupted,
            // as the new shake should start from a neutral base.
            foreach (var axis in _axes)
            {
                if (axis.parameter != null)
                {
                    axis.parameter.Value = axis.parameter.DefaultValue;
                    axis.currentValue = 0f; // also reset the tracked current offset
                }
            }
        }

        _isShaking = true;
        _shakeStartTime = Time.time;
        
        // Initialize oscillator with slight randomization
        float amplitudeVariation = Random.Range(0.85f, 1.15f);
        float phaseVariation = Random.Range(0f, Mathf.PI * 2f);
        
        _oscillator = new OscillatorState
        {
            position = 0f,
            velocity = Random.Range(-5f, 5f), // initial random velocity
            phase = phaseVariation,
            amplitude = _physics.maxAmplitude * amplitudeVariation,
            frequency = _baseFrequency,
            mass = _physics.effectiveMass,
            dampingCoeff = CalculateDampingCoefficient(),
            springConstant = CalculateSpringConstant()
        };

        Debug.Log($"[HeadShake] Shake started - Freq: {_oscillator.frequency:F2}Hz, Amp: {_oscillator.amplitude:F1}°");
    }

    private void UpdatePhysicsSimulation()
    {
        float deltaTime = Time.deltaTime;
        float progress = ShakeProgress;
        
        // Dynamic envelope modulation
        float amplitudeEnv = _physics.amplitudeEnvelope.Evaluate(progress);
        float frequencyEnv = _physics.frequencyEnvelope.Evaluate(progress);
        
        // Update frequency based on envelope (animals slow down as they dry)
        _oscillator.frequency = _baseFrequency * frequencyEnv;
        _oscillator.springConstant = Mathf.Pow(2f * Mathf.PI * _oscillator.frequency, 2f) * _oscillator.mass;
        
        // Semi-implicit Euler integration for stability
        // F = -kx - cv (spring-damper equation)
        float force = -_oscillator.springConstant * _oscillator.position - _oscillator.dampingCoeff * _oscillator.velocity;
        float acceleration = force / _oscillator.mass;
        
        // Update velocity then position
        _oscillator.velocity += acceleration * deltaTime;
        _oscillator.position += _oscillator.velocity * deltaTime;
        
        // Apply amplitude envelope
        float envelopedPosition = _oscillator.position * amplitudeEnv;
        
        // Add multi-octave Perlin noise for micro-variations, scaled by envelope
        float noise = CalculatePerlinNoise(Time.time) * amplitudeEnv; // Scaled noise by amplitudeEnv
        
        // Store final value for parameter application
        _oscillator.position = envelopedPosition + noise;
    }

    private float CalculateDampingCoefficient()
    {
        // c = 2ζ√(km) where ζ is damping ratio
        return 2f * _physics.dampingRatio * Mathf.Sqrt(_oscillator.springConstant * _oscillator.mass);
    }

    private float CalculateSpringConstant()
    {
        // k = (2πf)² * m
        return Mathf.Pow(2f * Mathf.PI * _oscillator.frequency, 2f) * _oscillator.mass;
    }

    private float CalculatePerlinNoise(float time)
    {
        // Multi-octave fBm (fractal Brownian motion) for natural variation
        float noise = 0f;
        float amplitude = _noise.noiseAmplitude;
        
        // Primary octave
        noise += Mathf.PerlinNoise(_noiseSeeds.x + time * _noise.primaryFreq, 0f) * amplitude;
        
        // Secondary octave (higher frequency, lower amplitude)
        if (_noise.secondaryGain > 0f)
        {
            noise += Mathf.PerlinNoise(_noiseSeeds.y + time * _noise.primaryFreq * 2f, 0f) * amplitude * _noise.secondaryGain;
        }
        
        // Tertiary octave (highest frequency, lowest amplitude)
        if (_noise.tertiaryGain > 0f)
        {
            noise += Mathf.PerlinNoise(_noiseSeeds.z + time * _noise.primaryFreq * 4f, 0f) * amplitude * _noise.tertiaryGain;
        }
        
        // Center the noise around 0
        return (noise - 0.5f * amplitude * (1f + _noise.secondaryGain + _noise.tertiaryGain));
    }

    #endregion

    #region Parameter Application

    private void ApplyMotionToParameters()
    {
        float baseValue = _oscillator.position;
        
        foreach (var axis in _axes)
        {
            if (axis.parameter == null || axis.weight <= 0f) continue;
            
            // Calculate phase offset in radians
            float phaseRad = axis.phaseOffset * Mathf.Deg2Rad;
            
            // Apply phase offset to create cascading motion
            float time = Time.time - _shakeStartTime;
            float phasedValue = baseValue * Mathf.Cos(phaseRad) + 
                               (_oscillator.velocity * 0.1f) * Mathf.Sin(phaseRad);
            
            // Scale and weight the value
            float finalValue = phasedValue * axis.amplitudeScale * axis.weight;
            
            // Apply to parameter with safety clamping
            float currentParam = axis.parameter.Value;
            float newValue = currentParam + finalValue;
            axis.parameter.Value = Mathf.Clamp(newValue, axis.parameter.MinimumValue, axis.parameter.MaximumValue);
            
            // Store for debugging
            axis.currentValue = finalValue;
        }
    }

    private void EndShake()
    {
        _isShaking = false;
        // _oscillator.position = 0f; // These are less critical now due to noise scaling and robust return
        // _oscillator.velocity = 0f;
        
        if (_continuousShakeCoroutine != null)
        {
            StopCoroutine(_continuousShakeCoroutine);
        }
        _continuousShakeCoroutine = StartCoroutine(SmoothReturnToNeutral());
    }

    private IEnumerator SmoothReturnToNeutral()
    {
        float returnDuration = 0.3f;
        float[] initialParameterValues = new float[_axes.Length];
        float[] initialCurrentValues = new float[_axes.Length]; // To lerp currentValue to 0

        // Record starting values
        for (int i = 0; i < _axes.Length; i++)
        {
            if (_axes[i].parameter != null)
            {
                initialParameterValues[i] = _axes[i].parameter.Value;
                initialCurrentValues[i] = _axes[i].currentValue;
            }
        }
        
        // Smooth return
        for (float t = 0f; t < returnDuration; t += Time.deltaTime)
        {
            float progress = t / returnDuration;
            float smoothProgress = Mathf.SmoothStep(0f, 1f, progress);
            
            for (int i = 0; i < _axes.Length; i++)
            {
                if (_axes[i].parameter != null)
                {
                    // Lerp parameter directly to its default value
                    _axes[i].parameter.Value = Mathf.Lerp(initialParameterValues[i], _axes[i].parameter.DefaultValue, smoothProgress);
                    // Lerp the stored currentValue to 0 as well
                    _axes[i].currentValue = Mathf.Lerp(initialCurrentValues[i], 0f, smoothProgress);
                }
            }
            
            yield return null;
        }
        
        // Final cleanup to ensure exact values
        foreach (var axis in _axes)
        {
            if (axis.parameter != null)
            {
                axis.parameter.Value = axis.parameter.DefaultValue;
            }
            axis.currentValue = 0f;
        }
        _continuousShakeCoroutine = null; // Clear the coroutine reference once done
    }

    #endregion

    #region Validation and Debug

    private void OnValidate()
    {
        if (_physics.effectiveMass <= 0f) _physics.effectiveMass = 0.1f;
        if (_physics.dampingRatio <= 0f) _physics.dampingRatio = 0.1f;
        if (_physics.maxAmplitude <= 0f) _physics.maxAmplitude = 1f;
        if (_physics.shakeDuration <= 0f) _physics.shakeDuration = 0.5f;
        
        // Ensure amplitude envelope is valid
        if (_physics.amplitudeEnvelope == null || _physics.amplitudeEnvelope.keys.Length == 0)
        {
            _physics.amplitudeEnvelope = AnimationCurve.EaseInOut(0f, 1f, 1f, 0f);
        }
        
        if (_physics.frequencyEnvelope == null || _physics.frequencyEnvelope.keys.Length == 0)
        {
            _physics.frequencyEnvelope = AnimationCurve.Linear(0f, 1f, 1f, 0.7f);
        }
        
        // Recalculate physics if values changed
        if (Application.isPlaying)
        {
            InitializePhysics();
        }
    }

#if UNITY_EDITOR
    [Header("Debug")]
    [SerializeField] private bool _showDebugGUI = true;
    [SerializeField] private bool _showDetailedDebug = false;

    [ContextMenu("Trigger Shake")]
    private void DebugTriggerShake()
    {
        if (Application.isPlaying) TriggerShake();
    }

    [ContextMenu("Trigger Intense Shake")]
    private void DebugTriggerIntenseShake()
    {
        if (Application.isPlaying) TriggerShakeWithIntensity(1.5f);
    }

    private void OnGUI()
    {
        if (!_showDebugGUI || !Application.isPlaying) return;
        
        GUILayout.BeginArea(new Rect(10, 10, 400, _showDetailedDebug ? 300 : 200));
        GUILayout.Box("HeadShake - Physics-Based Natural Motion");
        
        // Basic info
        GUILayout.Label($"Shaking: {_isShaking}");
        GUILayout.Label($"Progress: {ShakeProgress:P1}");
        GUILayout.Label($"Base Frequency: {_baseFrequency:F2} Hz (Mass: {_physics.effectiveMass}kg)");
        GUILayout.Label($"Position: {_oscillator.position:F2}°");
        GUILayout.Label($"Velocity: {_oscillator.velocity:F2}°/s");
        
        if (_showDetailedDebug)
        {
            GUILayout.Label($"Spring K: {_oscillator.springConstant:F1}");
            GUILayout.Label($"Damping C: {_oscillator.dampingCoeff:F1}");
            
            GUILayout.Space(5);
            GUILayout.Label("Parameter Values:");
            foreach (var axis in _axes)
            {
                if (axis.parameter != null)
                {
                    GUILayout.Label($"  {axis.paramId}: {axis.parameter.Value:F2} (offset: {axis.currentValue:F2})");
                }
            }
        }
        
        GUILayout.Space(10);
        if (GUILayout.Button("Trigger Normal Shake"))
        {
            TriggerShake();
        }
        if (GUILayout.Button("Trigger Intense Shake"))
        {
            TriggerShakeWithIntensity(3f);
        }
        
        GUILayout.EndArea();
    }
#endif

    #endregion

    private IEnumerator ContinuousShakeRoutine()
    {
        while (true) // "一直循环"
        {
            yield return new WaitForSeconds(2f); // "每2秒"

            // Ensure still auto-triggering after the wait, in case _autoTrigger changed.
            if (!_autoTrigger) 
            {
                _continuousShakeCoroutine = null; // Clear self-reference before exiting
                yield break;
            }

            float randomValue = Random.Range(0f, 1f); // "随机生成一个0-1的数字"
            if (randomValue > 0.5f)
            {
                TriggerShakeWithIntensity(3f); 
            }
            else
            {
                TriggerShake(); // Otherwise, do a normal shake
            }
        }
    }
}