using UnityEngine;

/// <summary>
/// Basit yakin dovus saldirisi.
/// - Sol fare tusuna basinca onundeki kucuk kureyi kontrol eder,
///   icindeki Health'i olan dusmanlara hasar verir.
/// - Animator varsa "Attack" tetikleyicisini calistirir (opsiyonel).
///
/// KURULUM:
/// 1. Oyuncuya bu scripti ekle.
/// 2. "saldiriNoktasi" icin oyuncunun onune bos bir child obje koy (elin hizasi)
///    ve buraya surukle. Bos birakirsan oyuncunun biraz onunu kullanir.
/// 3. "dusmanKatmani" olarak dusmanlarin Layer'ini sec (veya Everything birak).
/// </summary>
public class PlayerAttack : MonoBehaviour
{
    [Header("Saldiri")]
    public float hasar = 25f;
    public float menzil = 1.8f;         // saldiriNoktasi cevresindeki kure yaricapi
    public float bekleme = 0.5f;        // saldirilar arasi minimum sure
    public Transform saldiriNoktasi;    // Vurus merkezi (opsiyonel)
    public LayerMask dusmanKatmani = ~0; // Varsayilan: her sey

    [Header("Referans")]
    public Animator animator;

    private float sonSaldiri;

    void Start()
    {
        if (animator == null) animator = GetComponentInChildren<Animator>();
    }

    void Update()
    {
        if (Input.GetMouseButtonDown(0) && Time.time - sonSaldiri >= bekleme)
        {
            sonSaldiri = Time.time;
            Saldir();
        }
    }

    void Saldir()
    {
        if (animator != null) animator.SetTrigger("Attack");

        Vector3 merkez = saldiriNoktasi != null
            ? saldiriNoktasi.position
            : transform.position + transform.forward * 1.2f + Vector3.up * 1f;

        Collider[] hedefler = Physics.OverlapSphere(merkez, menzil, dusmanKatmani);
        foreach (Collider c in hedefler)
        {
            if (c.transform == transform) continue; // kendine vurma
            Health h = c.GetComponent<Health>();
            if (h != null) h.HasarAl(hasar);
        }
    }

    void OnDrawGizmosSelected()
    {
        Vector3 merkez = saldiriNoktasi != null
            ? saldiriNoktasi.position
            : transform.position + transform.forward * 1.2f + Vector3.up * 1f;
        Gizmos.color = Color.cyan;
        Gizmos.DrawWireSphere(merkez, menzil);
    }
}
