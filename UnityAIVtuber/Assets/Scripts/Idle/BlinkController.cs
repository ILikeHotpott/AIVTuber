using System.Collections;
using UnityEngine;
using Live2D.Cubism.Core;

[DisallowMultipleComponent]
[RequireComponent(typeof(CubismModel))]
public class BlinkController : MonoBehaviour
{
    // ───────── Cubism ─────────
    [Header("Cubism")]
    public CubismModel model;
    public string paramEyeLOpen = "ParamEyeLOpen";
    public string paramEyeROpen = "ParamEyeROpen";

    // ───────── Idle ─────────
    [Header("Idle 微动 (60 %)")]
    [Range(0f, 1f)] public float idleMin = 0.9f;
    [Range(0f, 1f)] public float idleMax = 1.0f;
    public Vector2 idleMoveDur = new(0.18f, 0.28f);
    public Vector2 idleHoldDur = new(1.0f, 1.8f);

    [Header("Idle 内置快速眨眼")]
    [Range(0f, 1f)] public float idleBlinkChance = 0.15f;   // 15 % Idle 时触发一次快速眨眼

    // ───────── 正常眨眼 (快速) ─────────
    [Header("正常眨眼 (快速)")]
    public float normalBlinkCloseDur = 0.15f;
    public float normalBlinkOpenDur  = 0.1f;

    // ───────── 缓慢动作 (target>0.3) ─────────
    [Header("慢动作 (浅闭合)")]
    public Vector2 slowMoveDurRange = new(0.3f, 0.5f);
    private const float slowCloseThreshold = 0.3f;

    // ───────── 事件概率 ─────────
    [Header("事件概率 (总计 ≤ 1.0)")]
    [Range(0f, 1f)] public float chanceIdle        = 0.58f;
    [Range(0f, 1f)] public float chanceHold08      = 0.30f;
    [Range(0f, 1f)] public float chanceHalfClose   = 0.01f;
    [Range(0f, 1f)] public float chanceHold055     = 0.03f;
    [Range(0f, 1f)] public float chanceHold02      = 0.02f;
    [Range(0f, 1f)] public float chanceDoubleBlink = 0.06f;

    // ───────── 特殊事件参数 ─────────
    [Header("Half-Close + Blink")]
    public float halfCloseValue = 0.7f;
    public float halfCloseHold  = 0.6f;                   // 缓慢半闭后停留

    [Header("Hold 0.8 / 0.55 / 0.2")]
    public float  hold08Value   = 0.8f;
    public Vector2 hold08Dur    = new(1.2f, 1.8f);
    public Vector2 hold055Range = new(0.7f, 0.8f);
    public Vector2 hold055Dur   = new(1.2f, 1.8f);
    public float  hold02Value   = 0.7f;
    public float  hold02Dur     = 2.5f;

    [Header("Double Blink")]
    public float  doubleBlinkValue = 0.2f;
    public float  doubleBlinkGap   = 0.3f;

    // ───────── 忽闪 ─────────
    [Header("忽闪")]
    public float  flickerChance      = 0f;
    private readonly Vector2[] flickerDepths =
    {
        new(0.60f, 0.70f),
        new(0.65f, 0.75f),
        new(0.70f, 0.80f),  
        new(0.75f, 0.85f),
        new(0.80f, 0.90f)
    };
    public Vector2 flickerDurRange   = new(0.6f, 1.2f);
    public Vector2 flickerPauseRange = new(2.5f, 4.5f);
    public float   minWaitForFlicker = 1.5f;

    // ───────── 内部引用 ─────────
    private CubismParameter _eyeL, _eyeR;

    private void Awake()
    {
        if (model == null) model = GetComponent<CubismModel>();
        _eyeL = model.Parameters.FindById(paramEyeLOpen);
        _eyeR = model.Parameters.FindById(paramEyeROpen);
        if (_eyeL == null || _eyeR == null)
        {
            Debug.LogError("Blink: 眼睛参数名不匹配");
            enabled = false;
        }
    }

    private void OnEnable()  => StartCoroutine(MainRoutine());
    private void OnDisable() => StopAllCoroutines();

    // ───────── 主循环 ─────────
    private IEnumerator MainRoutine()
    {
        while (true)
        {
            float r = Random.value;
            if      (r < chanceIdle)                               yield return IdleMicroMove();
            else if (r < chanceIdle + chanceHold08) yield return HoldFixed(hold08Value, hold08Dur);
            else if (r < chanceIdle + chanceHold08 + chanceHalfClose ) yield return HalfCloseBlink();
            else if (r < chanceIdle + chanceHold08 + chanceHalfClose + chanceHold055)
                yield return HoldRandom(hold055Range, hold055Dur);
            else if (r < chanceIdle + chanceHold08 + chanceHalfClose + chanceHold055 + chanceHold02)
                yield return HoldFixed(hold02Value, new Vector2(hold02Dur, hold02Dur));
            else yield return DoubleBlink();
        }
    }

    // ───────── Idle 微动 / 快速眨眼 ─────────
    private IEnumerator IdleMicroMove()
    {
        float mid = Random.Range(idleMin, idleMax);
        yield return MoveEyes(mid, Random.Range(idleMoveDur.x, idleMoveDur.y));

        float hold = Random.Range(idleHoldDur.x, idleHoldDur.y);

        // 15 % 概率在 Idle 停顿期插入一次"正常快速眨眼"
        if (Random.value < idleBlinkChance)
        {
            float half = hold * 0.5f;               // 前半段停顿
            yield return WaitWithMicroFlicker(half);
            // 快速眨眼
            yield return FastMoveEyes(0f);
            yield return FastMoveEyes(1f);
            yield return WaitWithMicroFlicker(hold - half);
        }
        else
        {
            yield return WaitWithMicroFlicker(hold);
        }

        yield return MoveEyes(1f, Random.Range(idleMoveDur.x, idleMoveDur.y));
    }

    // ───────── Half-Close Event ─────────
    private IEnumerator HalfCloseBlink()
    {
        yield return FastMoveEyes(halfCloseValue);         // 半闭 (慢)
        yield return WaitWithMicroFlicker(halfCloseHold);
        yield return FastMoveEyes(0f);                     // 闭眼 (快)
        yield return FastMoveEyes(1f);                     // 睁眼 (快)
    }

    // ───────── Hold Events ─────────
    private IEnumerator HoldFixed(float value, Vector2 dur)
    {
        yield return SlowOrFastMove(value);
        yield return WaitWithMicroFlicker(Random.Range(dur.x, dur.y));
        yield return FastMoveEyes(1f);
    }

    private IEnumerator HoldRandom(Vector2 range, Vector2 dur)
    {
        float v = Random.Range(range.x, range.y);
        yield return SlowOrFastMove(v);
        yield return WaitWithMicroFlicker(Random.Range(dur.x, dur.y));
        yield return FastMoveEyes(1f);
    }

    // ───────── Double Blink ─────────
    private IEnumerator DoubleBlink()
    {
        yield return SlowOrFastMove(doubleBlinkValue);
        yield return FastMoveEyes(1f);
        yield return new WaitForSeconds(doubleBlinkGap);
        yield return SlowOrFastMove(doubleBlinkValue);
        yield return FastMoveEyes(1f);
    }

    // ───────── 忽闪 ─────────
    private IEnumerator WaitWithMicroFlicker(float total)
    {
        if (total < minWaitForFlicker || Random.value > flickerChance)
        {
            yield return new WaitForSeconds(total);
            yield break;
        }

        float endT = Time.time + total;
        yield return new WaitForSeconds(Random.Range(0.3f, 0.5f));

        while (Time.time < endT)
        {
            Vector2 depth = flickerDepths[Random.Range(0, flickerDepths.Length)];
            float mid = Random.Range(depth.x, depth.y);
            float dur = Random.Range(flickerDurRange.x, flickerDurRange.y);

            yield return SlowMoveEyes(mid, dur);
            yield return SlowMoveEyes(1f,  dur);

            float pause = Mathf.Min(Random.Range(flickerPauseRange.x, flickerPauseRange.y),
                                    endT - Time.time);
            if (pause > 0) yield return new WaitForSeconds(pause);
        }
    }

    // ───────── 移动工具 ─────────
    private IEnumerator SlowOrFastMove(float target)
        => (target <= slowCloseThreshold) ? FastMoveEyes(target)
                                          : SlowMoveEyes(target);

    private IEnumerator FastMoveEyes(float target)
        => MoveEyes(target, (target < 1f) ? normalBlinkCloseDur : normalBlinkOpenDur);

    private IEnumerator SlowMoveEyes(float target)
        => MoveEyes(target, Random.Range(slowMoveDurRange.x, slowMoveDurRange.y));

    private IEnumerator SlowMoveEyes(float target, float dur)
        => MoveEyes(target, dur);

    private IEnumerator MoveEyes(float target, float dur)
    {
        float start = _eyeL.Value;
        float t = 0f;
        while (t < dur)
        {
            t += Time.deltaTime;
            float v = Mathf.Lerp(start, target, t / dur);
            _eyeL.Value = _eyeR.Value = v;
            yield return null;
        }
        _eyeL.Value = _eyeR.Value = target;
    }
}
