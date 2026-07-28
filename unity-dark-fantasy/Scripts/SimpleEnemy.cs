using UnityEngine;

/// <summary>
/// Cok basit dusman AI'i (yapay zeka).
/// - Oyuncu menzile girince kovalar.
/// - Yakina gelince belirli araliklarla saldirir (oyuncunun Health'ine hasar verir).
/// - NavMesh gerektirmez; dogrudan oyuncuya dogru yurur (duz zeminde calisir).
///   Ileride NavMeshAgent'a gecince engellerden dolasabilir.
///
/// KURULUM:
/// 1. Dusman objesine bu scripti + bir Health bileseni ekle.
/// 2. "oyuncu" alanina oyuncu Transform'unu surukle (veya bos birak, "Player" tag'ini arar).
/// 3. Oyuncunun tag'ini "Player" yap ki otomatik bulsun.
/// </summary>
public class SimpleEnemy : MonoBehaviour
{
    [Header("Hedef")]
    public Transform oyuncu;

    [Header("Davranis")]
    public float gorusMenzili = 12f;     // Bu mesafeden yakinsa kovalar
    public float saldiriMenzili = 2f;    // Bu mesafeden yakinsa saldirir
    public float hareketHizi = 2.5f;
    public float donusHizi = 8f;

    [Header("Saldiri")]
    public float saldiriHasari = 10f;
    public float saldiriAraligi = 1.5f;  // Saniyede kac kez vurabilir

    private float sonSaldiriZamani;
    private Health oyuncuCani;

    void Start()
    {
        if (oyuncu == null)
        {
            GameObject p = GameObject.FindGameObjectWithTag("Player");
            if (p != null) oyuncu = p.transform;
        }
        if (oyuncu != null) oyuncuCani = oyuncu.GetComponent<Health>();
    }

    void Update()
    {
        if (oyuncu == null) return;

        float mesafe = Vector3.Distance(transform.position, oyuncu.position);
        if (mesafe > gorusMenzili) return; // Oyuncu uzakta, bekle

        // Oyuncuya don
        Vector3 yon = (oyuncu.position - transform.position);
        yon.y = 0f;
        if (yon.sqrMagnitude > 0.001f)
        {
            Quaternion hedefDonus = Quaternion.LookRotation(yon);
            transform.rotation = Quaternion.Slerp(transform.rotation, hedefDonus,
                                                  donusHizi * Time.deltaTime);
        }

        if (mesafe > saldiriMenzili)
        {
            // Kovala
            transform.position += yon.normalized * hareketHizi * Time.deltaTime;
        }
        else
        {
            // Saldiri menzilinde: belirli araliklarla vur
            if (Time.time - sonSaldiriZamani >= saldiriAraligi)
            {
                sonSaldiriZamani = Time.time;
                if (oyuncuCani != null) oyuncuCani.HasarAl(saldiriHasari);
            }
        }
    }

    // Sahnede menzilleri gorsel olarak goster (sadece editörde)
    void OnDrawGizmosSelected()
    {
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(transform.position, gorusMenzili);
        Gizmos.color = Color.red;
        Gizmos.DrawWireSphere(transform.position, saldiriMenzili);
    }
}
