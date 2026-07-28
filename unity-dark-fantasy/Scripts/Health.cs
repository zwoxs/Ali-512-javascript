using UnityEngine;
using UnityEngine.Events;

/// <summary>
/// Genel can sistemi. Hem oyuncuya hem dusmana takilabilir.
/// - Hasar al, iyiles, ol.
/// - UnityEvent'ler sayesinde olum/hasar aninda baska seyleri tetikleyebilirsin
///   (ses cal, animasyon oynat, dusmani yok et vb.) kod yazmadan Inspector'dan.
///
/// KURULUM:
/// 1. Bu scripti oyuncu veya dusman objesine ekle.
/// 2. maxCan degerini ayarla.
/// 3. Baska scriptlerden HasarAl(miktar) cagirarak hasar ver.
/// </summary>
public class Health : MonoBehaviour
{
    [Header("Can")]
    public float maxCan = 100f;
    public float mevcutCan;

    [Header("Olaylar (opsiyonel)")]
    public UnityEvent onHasar;          // Hasar alinca
    public UnityEvent onOldu;           // Can 0 olunca

    public bool OlduMu => mevcutCan <= 0f;

    void Awake()
    {
        mevcutCan = maxCan;
    }

    /// <summary>Hasar verir. Can 0'a inince olum tetiklenir.</summary>
    public void HasarAl(float miktar)
    {
        if (OlduMu) return;

        mevcutCan -= miktar;
        onHasar?.Invoke();

        if (mevcutCan <= 0f)
        {
            mevcutCan = 0f;
            onOldu?.Invoke();
        }
    }

    /// <summary>Can yeniler (max'i asmaz).</summary>
    public void Iyilesir(float miktar)
    {
        if (OlduMu) return;
        mevcutCan = Mathf.Min(mevcutCan + miktar, maxCan);
    }
}
