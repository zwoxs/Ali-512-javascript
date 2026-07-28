using UnityEngine;

/// <summary>
/// Basit 3. sahis omuz-ustu kamera.
/// - Fare ile etrafa bakar, karakteri takip eder.
/// - Cinemachine kurmadan calisir (sonra istersen Cinemachine'e gecebilirsin).
///
/// KURULUM:
/// 1. Ana Kamera'yi sec, bu scripti ekle.
/// 2. "Hedef" alanina karakterini surukle.
/// 3. Oyunu baslat: fare ile bak, karakter kameraya gore hareket eder.
/// </summary>
public class CameraFollow : MonoBehaviour
{
    [Header("Hedef")]
    public Transform hedef;              // Takip edilecek karakter
    public Vector3 hedefOfset = new Vector3(0f, 1.6f, 0f); // Omuz/bas hizasi

    [Header("Mesafe & Aci")]
    public float mesafe = 4.5f;
    public float minPitch = -30f;       // En asagi bakis
    public float maxPitch = 60f;        // En yukari bakis

    [Header("Fare Hassasiyeti")]
    public float fareHassasiyeti = 2.5f;

    private float yaw;                   // Yatay aci
    private float pitch = 15f;           // Dikey aci

    void Start()
    {
        // Fareyi kilitle ve gizle (oyun hissi icin)
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;
    }

    void LateUpdate()
    {
        if (hedef == null) return;

        // Fare girdisi
        yaw += Input.GetAxis("Mouse X") * fareHassasiyeti;
        pitch -= Input.GetAxis("Mouse Y") * fareHassasiyeti;
        pitch = Mathf.Clamp(pitch, minPitch, maxPitch);

        // Kamera acisi ve pozisyonu
        Quaternion donus = Quaternion.Euler(pitch, yaw, 0f);
        Vector3 hedefNoktasi = hedef.position + hedefOfset;
        Vector3 istenenPoz = hedefNoktasi - (donus * Vector3.forward * mesafe);

        transform.position = istenenPoz;
        transform.rotation = donus;
    }
}
