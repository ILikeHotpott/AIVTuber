using UnityEngine;
using Live2D.Cubism.Core;
using Live2D.Cubism.Framework;

public class PrintAllCubismParameters : MonoBehaviour
{
    void Start()
    {
        var parameters = GetComponentsInChildren<CubismParameter>();

        Debug.Log($"Found {parameters.Length} parameters:");

        foreach (var param in parameters)
        {
            string info = $"Name: {param.Id} | Value: {param.Value} | Min: {param.MinimumValue} | Max: {param.MaximumValue}";
            Debug.Log(info);
        }
    }
}
