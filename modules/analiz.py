"""
analiz.py — KPI hesaplama ve reklam sağlık değerlendirme motoru.

Görev: Meta API'den gelen ham sayıları alır, anlamlı metriklere dönüştürür.
       Türkiye pazarı kıyaslamaları kullanır.
       Her kampanya/reklam için 0-100 arası Sağlık Skoru üretir.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ── Türkiye Meta Reklam Pazarı Kıyaslama Değerleri ───────────────────────────
# Bu değerler Türkiye'deki ortalama performanslardır.
# Bunların üzerindeysen iyi, altındaysan iyileştirme gerekiyor.

KIYAS = {
    "ctr_iyi":        1.5,   # %1.5 ve üzeri → iyi tıklama oranı
    "ctr_orta":       0.8,   # %0.8-1.5 → ortalama
    "ctr_kotu":       0.3,   # %0.3 altı → kötü

    "cpc_iyi":        5.0,   # 5 TRY altı → ucuz tıklama
    "cpc_orta":      10.0,   # 5-10 TRY → ortalama
    "cpc_kotu":      20.0,   # 20 TRY üzeri → pahalı

    "cpm_iyi":       40.0,   # 40 TRY altı → ucuz gösterim
    "cpm_orta":      80.0,   # 40-80 TRY → ortalama
    "cpm_kotu":     150.0,   # 150 TRY üzeri → çok pahalı

    "frequency_iyi":  2.0,   # Aynı kişiye 2 kezden az gösterdiysen → taze
    "frequency_uyari": 3.5,  # 2-3.5 arası → dikkat et
    "frequency_kotu":  5.0,  # 5 üzeri → reklam yorgunluğu başlamış

    "min_gosterim":  500,    # İstatistiksel anlamlılık için minimum gösterim
}


# ── KPI Veri Yapısı ───────────────────────────────────────────────────────────

@dataclass
class KPI:
    """Bir kampanya veya reklamın hesaplanmış KPI değerleri."""

    # Ham veriler (Meta'dan gelen)
    isim: str = ""
    id: str = ""
    durum: str = ""
    harcama: float = 0.0
    gosterim: int = 0
    tiklama: int = 0
    erisim: int = 0
    frequency: float = 0.0

    # Hesaplanan metrikler
    ctr: float = 0.0        # Tıklama Oranı (%)
    cpc: float = 0.0        # Tıklama Başına Maliyet (TRY)
    cpm: float = 0.0        # Bin Gösterim Maliyeti (TRY)
    roas: float = 0.0       # Reklam Harcaması Getirisi

    # Değerlendirme
    saglik_skoru: int = 0           # 0-100 arası genel puan
    saglik_etiketi: str = ""        # "Mükemmel", "İyi", "Ortalama", "Zayıf", "Kritik"
    reklam_yorgunlugu: bool = False # Aynı kitleye çok gösterildi mi?
    oneri: str = ""                 # "Büyüt", "İzle", "Optimize Et", "Durdur"
    uyarilar: list = field(default_factory=list)  # Dikkat edilmesi gereken noktalar


# ── Ana Analiz Fonksiyonları ──────────────────────────────────────────────────

def icgoru_parse(ham_veri: dict) -> dict:
    """
    Meta API'nin döndürdüğü insights verisini düzleştirir.
    Meta bazen veriyi iç içe dict olarak, bazen liste olarak gönderir.
    Bu fonksiyon her durumda çalışır.
    """
    if not ham_veri:
        return {}

    # Insights bir liste içinde gelebilir: {"data": [{...}]}
    if "data" in ham_veri:
        liste = ham_veri["data"]
        return liste[0] if liste else {}

    return ham_veri


def kpi_hesapla(isim: str, id: str, durum: str, icgoru: dict) -> KPI:
    """
    Ham API verisinden KPI nesnesi üretir.

    Formüller:
    - CTR  = (tıklama / gösterim) × 100
    - CPC  = harcama / tıklama
    - CPM  = (harcama / gösterim) × 1000
    - ROAS = dönüşüm geliri / harcama
    """
    kpi = KPI(isim=isim, id=id, durum=durum)

    if not icgoru:
        kpi.saglik_etiketi = "Veri Yok"
        kpi.oneri = "İzle"
        return kpi

    # Ham değerleri al
    kpi.harcama   = float(icgoru.get("spend", 0) or 0)
    kpi.gosterim  = int(icgoru.get("impressions", 0) or 0)
    kpi.tiklama   = int(icgoru.get("clicks", 0) or 0)
    kpi.erisim    = int(icgoru.get("reach", 0) or 0)
    kpi.frequency = float(icgoru.get("frequency", 0) or 0)

    # Meta bazen CTR/CPC/CPM'i direkt veriyor, yoksa hesapla
    if icgoru.get("ctr"):
        kpi.ctr = float(icgoru["ctr"])
    elif kpi.gosterim > 0:
        kpi.ctr = (kpi.tiklama / kpi.gosterim) * 100

    if icgoru.get("cpc"):
        kpi.cpc = float(icgoru["cpc"])
    elif kpi.tiklama > 0:
        kpi.cpc = kpi.harcama / kpi.tiklama

    if icgoru.get("cpm"):
        kpi.cpm = float(icgoru["cpm"])
    elif kpi.gosterim > 0:
        kpi.cpm = (kpi.harcama / kpi.gosterim) * 1000

    # ROAS: actions içinde "purchase" değeri aranır
    actions = icgoru.get("actions", []) or []
    for action in actions:
        if action.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase"):
            kpi.roas = float(action.get("value", 0) or 0)
            break

    # Reklam yorgunluğu
    kpi.reklam_yorgunlugu = kpi.frequency >= KIYAS["frequency_kotu"]

    # Uyarı listesi
    kpi.uyarilar = _uyari_uret(kpi)

    # Sağlık skoru hesapla
    kpi.saglik_skoru = _saglik_skoru_hesapla(kpi)
    kpi.saglik_etiketi = _saglik_etiketi(kpi.saglik_skoru)
    kpi.oneri = _oneri_uret(kpi)

    return kpi


def _saglik_skoru_hesapla(kpi: KPI) -> int:
    """
    0-100 arası Reklam Sağlık Skoru üretir.

    Puan bileşenleri:
    - CTR   (0-35 puan): En önemli gösterge — insanlar reklamı tıklıyor mu?
    - CPC   (0-25 puan): Her tıklama kaça mal oluyor?
    - CPM   (0-20 puan): Gösterim maliyeti makul mu?
    - Frekans (0-20 puan): Aynı kişiye çok fazla mı gösteriliyor?
    """
    if kpi.gosterim < KIYAS["min_gosterim"]:
        # Yeterli veri yok, orta puan ver
        return 50

    puan = 0

    # CTR puanı (0-35)
    if kpi.ctr >= KIYAS["ctr_iyi"]:
        puan += 35
    elif kpi.ctr >= KIYAS["ctr_orta"]:
        puan += 22
    elif kpi.ctr >= KIYAS["ctr_kotu"]:
        puan += 10
    else:
        puan += 0

    # CPC puanı (0-25) — sadece tıklama varsa
    if kpi.tiklama > 0:
        if kpi.cpc <= KIYAS["cpc_iyi"]:
            puan += 25
        elif kpi.cpc <= KIYAS["cpc_orta"]:
            puan += 16
        elif kpi.cpc <= KIYAS["cpc_kotu"]:
            puan += 8
        else:
            puan += 0
    else:
        puan += 12  # Tıklama yoksa orta puan

    # CPM puanı (0-20)
    if kpi.harcama > 0 and kpi.gosterim > 0:
        if kpi.cpm <= KIYAS["cpm_iyi"]:
            puan += 20
        elif kpi.cpm <= KIYAS["cpm_orta"]:
            puan += 13
        elif kpi.cpm <= KIYAS["cpm_kotu"]:
            puan += 6
        else:
            puan += 0
    else:
        puan += 10

    # Frekans puanı (0-20)
    if kpi.frequency > 0:
        if kpi.frequency <= KIYAS["frequency_iyi"]:
            puan += 20
        elif kpi.frequency <= KIYAS["frequency_uyari"]:
            puan += 12
        elif kpi.frequency < KIYAS["frequency_kotu"]:
            puan += 5
        else:
            puan += 0
    else:
        puan += 15

    return min(100, max(0, puan))


def _saglik_etiketi(skor: int) -> str:
    """Skor aralığına göre Türkçe etiket döndürür."""
    if skor >= 85:
        return "Mükemmel"
    elif skor >= 70:
        return "İyi"
    elif skor >= 50:
        return "Ortalama"
    elif skor >= 30:
        return "Zayıf"
    else:
        return "Kritik"


def _oneri_uret(kpi: KPI) -> str:
    """
    Tek satırlık aksiyon önerisi döndürür.
    Kural motoru daha detaylı karar alır; bu sadece hızlı etikettir.
    """
    if kpi.saglik_skoru >= 85:
        return "Büyüt — Bütçeyi artır"
    elif kpi.saglik_skoru >= 70:
        return "Sürdür — Takipte kal"
    elif kpi.saglik_skoru >= 50:
        return "Optimize Et — Kreatifi yenile"
    elif kpi.reklam_yorgunlugu:
        return "Kitleyi Değiştir — Yorgunluk başladı"
    elif kpi.saglik_skoru >= 30:
        return "Müdahale Gerekli — İnceleme yap"
    else:
        return "Durdur — Bütçe boşa gidiyor"


def _uyari_uret(kpi: KPI) -> list:
    """Dikkat çekilmesi gereken durumları listeler."""
    uyarilar = []

    if kpi.reklam_yorgunlugu:
        uyarilar.append(
            f"⚠️ Reklam Yorgunluğu: Frekans {kpi.frequency:.1f} — "
            f"aynı kişi reklamı {kpi.frequency:.0f} kez gördü. Kreatif yenile."
        )
    if kpi.ctr < KIYAS["ctr_kotu"] and kpi.gosterim >= KIYAS["min_gosterim"]:
        uyarilar.append(
            f"⚠️ Düşük CTR: %{kpi.ctr:.2f} — görseli veya metni değiştir."
        )
    if kpi.cpc > KIYAS["cpc_kotu"] and kpi.tiklama > 0:
        uyarilar.append(
            f"⚠️ Yüksek Tıklama Maliyeti: {kpi.cpc:.2f} TRY/tıklama — kitleyi daralt."
        )
    if kpi.cpm > KIYAS["cpm_kotu"] and kpi.harcama > 0:
        uyarilar.append(
            f"⚠️ Yüksek Gösterim Maliyeti: {kpi.cpm:.2f} TRY/1000 gösterim — kitle çok rekabetçi."
        )
    if kpi.gosterim < KIYAS["min_gosterim"] and kpi.harcama > 0:
        uyarilar.append(
            f"ℹ️ Az Veri: Sadece {kpi.gosterim:,} gösterim — yorum yapmak için çok erken."
        )

    return uyarilar


# ── Kampanya Listesini Toplu Analiz Et ───────────────────────────────────────

def kampanyalari_analiz_et(kampanyalar: list) -> list[KPI]:
    """
    meta_api.kampanyalari_cek() çıktısını alır,
    her kampanya için KPI nesnesi üretir ve liste döndürür.
    """
    sonuclar = []
    for k in kampanyalar:
        icgoru_ham = k.get("insights", {})
        icgoru = icgoru_parse(icgoru_ham)
        kpi = kpi_hesapla(
            isim=k.get("name", "İsimsiz"),
            id=k.get("id", ""),
            durum=k.get("status", ""),
            icgoru=icgoru,
        )
        sonuclar.append(kpi)

    # Harcamaya göre sırala (en çok harcayandan en aza)
    sonuclar.sort(key=lambda x: x.harcama, reverse=True)
    return sonuclar


def hesap_ozeti_analiz(ozet: dict) -> KPI:
    """Hesap geneli tek KPI özeti üretir."""
    return kpi_hesapla(
        isim="Hesap Geneli",
        id="account",
        durum="ACTIVE",
        icgoru=ozet,
    )


# ── Konsol Çıktısı (Test İçin) ────────────────────────────────────────────────

def kpi_yazdir(kpi: KPI) -> None:
    """KPI nesnesini okunabilir formatta terminale yazar."""

    durum_ikon = {
        "ACTIVE": "🟢", "PAUSED": "🔴", "ARCHIVED": "⚫",
        "DELETED": "⚫", "CAMPAIGN_PAUSED": "🟡"
    }.get(kpi.durum, "⚪")

    print(f"\n{durum_ikon} {kpi.isim}")
    print(f"   Sağlık Skoru : {kpi.saglik_skoru}/100 — {kpi.saglik_etiketi}")
    print(f"   Harcama      : {kpi.harcama:,.2f} TRY")
    print(f"   Gösterim     : {kpi.gosterim:,}")
    print(f"   Tıklama      : {kpi.tiklama:,}")
    print(f"   CTR          : %{kpi.ctr:.2f}")
    print(f"   TBM (CPC)    : {kpi.cpc:.2f} TRY")
    print(f"   CPM          : {kpi.cpm:.2f} TRY")
    if kpi.frequency > 0:
        print(f"   Frekans      : {kpi.frequency:.1f}x")
    print(f"   Öneri        : {kpi.oneri}")
    for uyari in kpi.uyarilar:
        print(f"   {uyari}")
