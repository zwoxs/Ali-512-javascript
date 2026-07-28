using UnityEngine;

/// <summary>
/// Basit 3. sahis karakter kontrolcusu.
/// - CharacterController kullanir (fizik motoru ayari gerektirmez, en kolayi).
/// - Klavye ile hareket, kamera yonune gore yurur, yer cekimi ve ziplama vardir.
/// - Animator varsa "Speed" ve "IsGrounded" parametrelerini gunceller (opsiyonel).
///
/// KURULUM:
/// 1. Karakter GameObject'ine "Character Controller" bileseni ekle.
/// 2. Bu scripti ayni objeye ekle.
/// 3. Inspector'da "Cam" alanina ana kamerani surukle (veya bos birak, otomatik bulur).
/// </summary>
[RequireComponent(typeof(CharacterController))]
public class ThirdPersonController : MonoBehaviour
{
    [Header("Hareket")]
    public float yurumeHizi = 3f;
    public float kosmaHizi = 6f;
    public float donusYumusakligi = 0.1f; // Karakterin donerken ne kadar yumusak dondugunu ayarlar

    [Header("Ziplama & Yer Cekimi")]
    public float ziplamaYuksekligi = 1.2f;
    public float yerCekimi = -20f;

    [Header("Referanslar")]
    public Transform cam;               // Ana kamera. Bos ise Camera.main kullanilir.
    public Animator animator;           // Opsiyonel. Animasyon icin.

    private CharacterController controller;
    private float dikeyHiz;             // Yer cekimi / ziplama icin dikey hiz
    private float donusHiziRef;         // SmoothDampAngle icin ara deger

    void Start()
    {
        controller = GetComponent<CharacterController>();
        if (cam == null && Camera.main != null) cam = Camera.main.transform;
        if (animator == null) animator = GetComponentInChildren<Animator>();
    }

    void Update()
    {
        // --- Girdi (input) ---
        float x = Input.GetAxisRaw("Horizontal"); // A/D veya sol/sag ok
        float z = Input.GetAxisRaw("Vertical");   // W/S veya yukari/asagi ok
        Vector3 girdi = new Vector3(x, 0f, z).normalized;

        bool kosuyor = Input.GetKey(KeyCode.LeftShift);
        float hedefHiz = kosuyor ? kosmaHizi : yurumeHizi;

        // --- Yer kontrolu ---
        bool yerde = controller.isGrounded;
        if (yerde && dikeyHiz < 0f) dikeyHiz = -2f; // Yere yapissin

        Vector3 hareket = Vector3.zero;

        if (girdi.magnitude >= 0.1f)
        {
            // Kameraya gore gidilecek aci
            float hedefAci = Mathf.Atan2(girdi.x, girdi.z) * Mathf.Rad2Deg
                             + (cam != null ? cam.eulerAngles.y : 0f);

            // Karakteri yumusakca o yone dondur
            float aci = Mathf.SmoothDampAngle(transform.eulerAngles.y, hedefAci,
                                              ref donusHiziRef, donusYumusakligi);
            transform.rotation = Quaternion.Euler(0f, aci, 0f);

            // Bakilan yone dogru ilerle
            Vector3 yon = Quaternion.Euler(0f, hedefAci, 0f) * Vector3.forward;
            hareket = yon.normalized * hedefHiz;
        }

        // --- Ziplama ---
        if (yerde && Input.GetButtonDown("Jump"))
        {
            dikeyHiz = Mathf.Sqrt(ziplamaYuksekligi * -2f * yerCekimi);
        }

        // --- Yer cekimi uygula ---
        dikeyHiz += yerCekimi * Time.deltaTime;

        // --- Hareketi uygula ---
        Vector3 sonHareket = hareket + Vector3.up * dikeyHiz;
        controller.Move(sonHareket * Time.deltaTime);

        // --- Animator (opsiyonel) ---
        if (animator != null)
        {
            float animHiz = new Vector3(hareket.x, 0f, hareket.z).magnitude;
            animator.SetFloat("Speed", animHiz);
            animator.SetBool("IsGrounded", yerde);
        }
    }
}
