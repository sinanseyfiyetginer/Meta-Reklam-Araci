"""
kural_motoru.py — Otomatik reklam optimizasyon karar motoru.

Görev: KPI verilerini kurallara göre değerlendirir, aksiyon listesi üretir.
       Kurallar config/kurallar.json'dan okunur — her müşteri için özelleştirilebilir.

Güvenlik: Varsayılan mod SADECE ÖNERİ üretir.
          Otomatik uygulama için açıkça --uygula bayrağı gerekir.
"""

from __future__ import annotations
import os
import json
import requests
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── Karar Tipleri ─────────────────────────────────────────────────────────────

KARAR_TIPLERI = {
    "DURDUR":      "🔴",  # Kampanya/reklam durdurulsun
    "BUYUT":       "🚀",  # Bütçe artırılsın
    "UYAR":        "⚠️",  # İnsan gözü gerekiyor
    "KREATIF_YENİ": "🎨", # Görsel/metin yenilensin
    "KİTLE_DEĞİŞ": "👥",  # Hedef kitle gözden geçirilsin
    "TAMAM":       "✅",  # Müdahale gerekmez
}


# ── Karar Veri Yapısı ─────────────────────────────────────────────────────────

@dataclass
class Karar:
    """Bir kampanya için üretilen karar."""
    kampanya_id:   str
    kampanya_isim: str
    tip:           str          # DURDUR, BUYUT, UYAR, vb.
    neden:         str          # İnsan-okunur açıklama
    oncelik:       int = 2      # 1=Acil, 2=Normal, 3=Düşük
    uygulandi:     bool = False # True ise API'ye gönderildi
    hata:          Optional[str] = None


# ── Varsayılan Kurallar ───────────────────────────────────────────────────────

VARSAYILAN_KURALLAR = {
    "durdurma": {
        "min_gosterim":     1000,   # Bu kadar gösterim olmadan karar verme
        "max_ctr_kotu":     0.30,   # CTR bu değerin altındaysa durdur (%)
        "max_cpc_kotu":     25.0,   # TBM bu değerin üzerindeyse durdur (TRY)
        "max_frequency":    6.0,    # Frekans bu değeri geçerse durdur
        "min_harcama":      50.0,   # Bu kadar harcama olmadan durdurma kararı verme (TRY)
    },
    "buyutme": {
        "min_ctr_iyi":      2.0,    # CTR bu değerin üzerindeyse büyüt (%)
        "max_cpc_iyi":      5.0,    # TBM bu değerin altındaysa büyüt (TRY)
        "min_saglik_skoru": 80,     # Sağlık skoru bu değerin üzerindeyse büyüt
        "min_harcama":      100.0,  # İstatistiksel güven için minimum harcama (TRY)
        "butce_artis_orani": 0.20,  # Bütçeyi %20 artır
    },
    "uyari": {
        "frequency_uyari":  3.5,    # Bu değeri geçince uyar
        "ctr_uyari":        0.50,   # CTR bu değerin altına düşünce uyar
        "cpc_uyari":        12.0,   # TBM bu değeri geçince uyar
    },
}


# ── Config Yükleme ────────────────────────────────────────────────────────────

def kural_yukle(musteri_id: str = "varsayilan") -> dict:
    """
    config/kurallar_{musteri_id}.json dosyasını yükler.
    Dosya yoksa varsayılan kuralları kullanır.

    Bu sayede her müşteri için farklı kurallar ayarlayabilirsin.
    Örnek: Agresif büyüme isteyen müşteri için CTR eşiği düşük tutulur.
    """
    dosya_yolu = f"config/kurallar_{musteri_id}.json"

    if os.path.exists(dosya_yolu):
        with open(dosya_yolu, encoding="utf-8") as f:
            return json.load(f)

    return VARSAYILAN_KURALLAR


def kural_kaydet(kurallar: dict, musteri_id: str = "varsayilan") -> None:
    """Kuralları JSON dosyasına kaydeder."""
    os.makedirs("config", exist_ok=True)
    dosya_yolu = f"config/kurallar_{musteri_id}.json"
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        json.dump(kurallar, f, ensure_ascii=False, indent=2)
    print(f"✅ Kurallar kaydedildi: {dosya_yolu}")


# ── Ana Kural Değerlendirme Motoru ────────────────────────────────────────────

def kural_degerlendir(kpi_listesi: list, musteri_id: str = "varsayilan") -> list[Karar]:
    """
    KPI listesini alır, her kampanya için kural değerlendirmesi yapar,
    Karar listesi döndürür.

    Öncelik sırası:
    1. DURDUR (kritik durumlar)
    2. BÜYÜT  (fırsat durumlar)
    3. UYAR   (dikkat gereken durumlar)
    4. TAMAM  (müdahale gerekmeyen durumlar)
    """
    kurallar = kural_yukle(musteri_id)
    kararlar = []

    for kpi in kpi_listesi:
        karar = _tek_kampanya_degerlendir(kpi, kurallar)
        kararlar.append(karar)

    # Önceliğe göre sırala: Acil (1) önce
    kararlar.sort(key=lambda x: x.oncelik)
    return kararlar


def _tek_kampanya_degerlendir(kpi, kurallar: dict) -> Karar:
    """Tek bir kampanyanın KPI'sını kurallara göre değerlendirir."""

    d = kurallar.get("durdurma", {})
    b = kurallar.get("buyutme", {})
    u = kurallar.get("uyari", {})

    # ── DURDURMA KONTROLLERİ (Öncelik: Acil) ─────────────────────────────────

    # Kural D1: Çok düşük CTR + yeterli veri var
    if (kpi.gosterim >= d.get("min_gosterim", 1000)
            and kpi.harcama >= d.get("min_harcama", 50)
            and kpi.ctr < d.get("max_ctr_kotu", 0.30)
            and kpi.ctr > 0):
        return Karar(
            kampanya_id=kpi.id,
            kampanya_isim=kpi.isim,
            tip="DURDUR",
            neden=(
                f"CTR %{kpi.ctr:.2f} — eşiğin ({d.get('max_ctr_kotu', 0.30):.2f}%) altında. "
                f"{kpi.gosterim:,} gösterimde sadece {kpi.tiklama} tıklama. "
                f"Görsel veya metin çalışmıyor."
            ),
            oncelik=1,
        )

    # Kural D2: Çok yüksek TBM
    if (kpi.tiklama > 10
            and kpi.cpc > d.get("max_cpc_kotu", 25.0)):
        return Karar(
            kampanya_id=kpi.id,
            kampanya_isim=kpi.isim,
            tip="DURDUR",
            neden=(
                f"TBM {kpi.cpc:.2f} TRY — eşiğin ({d.get('max_cpc_kotu', 25.0)} TRY) üzerinde. "
                f"Her tıklama çok pahalıya mal oluyor. Kitle çok geniş veya rekabet yüksek."
            ),
            oncelik=1,
        )

    # Kural D3: Reklam yorgunluğu kritik seviyede
    if kpi.frequency >= d.get("max_frequency", 6.0):
        return Karar(
            kampanya_id=kpi.id,
            kampanya_isim=kpi.isim,
            tip="DURDUR",
            neden=(
                f"Frekans {kpi.frequency:.1f}x — aynı kişi reklamı {kpi.frequency:.0f} kez gördü. "
                f"Kitle tamamen doymuş, artık bütçe boşa gidiyor."
            ),
            oncelik=1,
        )

    # ── BÜYÜTME KONTROLLERİ (Öncelik: Normal) ────────────────────────────────

    # Kural B1: Yüksek CTR + düşük TBM + yeterli veri
    if (kpi.harcama >= b.get("min_harcama", 100)
            and kpi.ctr >= b.get("min_ctr_iyi", 2.0)
            and kpi.cpc <= b.get("max_cpc_iyi", 5.0)
            and kpi.saglik_skoru >= b.get("min_saglik_skoru", 80)):
        artis = b.get("butce_artis_orani", 0.20) * 100
        return Karar(
            kampanya_id=kpi.id,
            kampanya_isim=kpi.isim,
            tip="BUYUT",
            neden=(
                f"CTR %{kpi.ctr:.2f}, TBM {kpi.cpc:.2f} TRY — her iki metrik de mükemmel. "
                f"Sağlık skoru {kpi.saglik_skoru}/100. "
                f"Bütçeyi %{artis:.0f} artır, bu fırsatı kaçırma."
            ),
            oncelik=2,
        )

    # ── UYARI KONTROLLERİ (Öncelik: Normal) ──────────────────────────────────

    # Kural U1: Frekans uyarı bölgesinde
    if kpi.frequency >= u.get("frequency_uyari", 3.5):
        return Karar(
            kampanya_id=kpi.id,
            kampanya_isim=kpi.isim,
            tip="KİTLE_DEĞİŞ",
            neden=(
                f"Frekans {kpi.frequency:.1f}x — kitle yorulmaya başladı. "
                f"Yeni kitlenler ekle veya benzer kitle (Lookalike) dene."
            ),
            oncelik=2,
        )

    # Kural U2: Orta CTR, kreatif yenilenebilir
    if (kpi.gosterim >= 500
            and kpi.ctr < u.get("ctr_uyari", 0.50)
            and kpi.ctr > 0):
        return Karar(
            kampanya_id=kpi.id,
            kampanya_isim=kpi.isim,
            tip="KREATİF_YENİ",
            neden=(
                f"CTR %{kpi.ctr:.2f} — ortalama altında. "
                f"Görsel veya reklam metnini test et, A/B testi yap."
            ),
            oncelik=2,
        )

    # Kural U3: Yüksek TBM uyarısı
    if kpi.cpc > u.get("cpc_uyari", 12.0) and kpi.tiklama > 5:
        return Karar(
            kampanya_id=kpi.id,
            kampanya_isim=kpi.isim,
            tip="UYAR",
            neden=(
                f"TBM {kpi.cpc:.2f} TRY — yüksek seyrediyor. "
                f"Kitleyi daralt veya teklif stratejisini gözden geçir."
            ),
            oncelik=2,
        )

    # ── HİÇBİR KURAL TETIKLENMEDI: İYİ DURUMDA ───────────────────────────────
    return Karar(
        kampanya_id=kpi.id,
        kampanya_isim=kpi.isim,
        tip="TAMAM",
        neden=(
            f"Sağlık skoru {kpi.saglik_skoru}/100 — {kpi.saglik_etiketi}. "
            f"Müdahale gerekmiyor, takipte kal."
        ),
        oncelik=3,
    )


# ── Meta API Üzerinden Otomatik Uygulama ─────────────────────────────────────

def karar_uygula(karar: Karar, uygula: bool = False) -> Karar:
    """
    Kararı Meta API üzerinden uygular.

    uygula=False (varsayılan) → Sadece öneri, hiçbir şey değiştirilmez.
    uygula=True              → Gerçekten uygulanır (DİKKAT!)
    """
    if not uygula:
        karar.hata = "Simülasyon modu — gerçek uygulama için --uygula bayrağını ekle."
        return karar

    token = os.getenv("META_ACCESS_TOKEN")
    api_ver = "v20.0"
    url = f"https://graph.facebook.com/{api_ver}/{karar.kampanya_id}"

    if karar.tip == "DURDUR":
        yanit = requests.post(url, data={
            "status": "PAUSED",
            "access_token": token,
        })

    elif karar.tip == "BUYUT":
        # Mevcut bütçeyi çek
        mevcut = requests.get(url, params={
            "fields": "daily_budget",
            "access_token": token,
        }).json()
        mevcut_butce = int(mevcut.get("daily_budget", 0))
        if mevcut_butce > 0:
            yeni_butce = int(mevcut_butce * 1.20)  # %20 artır
            yanit = requests.post(url, data={
                "daily_budget": yeni_butce,
                "access_token": token,
            })
        else:
            karar.hata = "Günlük bütçe bulunamadı, ömür boyu bütçe kullanılıyor olabilir."
            return karar
    else:
        # Diğer karar tipleri (UYAR, KREATİF vb.) API aksiyonu gerektirmiyor
        karar.uygulandi = True
        return karar

    if yanit.status_code == 200:
        karar.uygulandi = True
    else:
        karar.hata = yanit.json().get("error", {}).get("message", "Bilinmeyen hata")

    return karar


# ── Kararları Konsola Yaz ─────────────────────────────────────────────────────

def kararlar_yazdir(kararlar: list[Karar]) -> None:
    """Karar listesini okunabilir formatta terminale yazar."""

    acil    = [k for k in kararlar if k.oncelik == 1]
    normal  = [k for k in kararlar if k.oncelik == 2]
    tamam   = [k for k in kararlar if k.oncelik == 3]

    if acil:
        print(f"\n{'='*55}")
        print(f"  🚨 ACİL — {len(acil)} kampanya hemen müdahale istiyor")
        print(f"{'='*55}")
        for k in acil:
            ikon = KARAR_TIPLERI.get(k.tip, "•")
            print(f"\n{ikon} {k.tip}: {k.kampanya_isim[:50]}")
            print(f"   {k.neden}")

    if normal:
        print(f"\n{'='*55}")
        print(f"  📋 NORMAL — {len(normal)} kampanya aksiyon bekliyor")
        print(f"{'='*55}")
        for k in normal:
            ikon = KARAR_TIPLERI.get(k.tip, "•")
            print(f"\n{ikon} {k.tip}: {k.kampanya_isim[:50]}")
            print(f"   {k.neden}")

    if tamam:
        print(f"\n{'='*55}")
        print(f"  ✅ TAMAM — {len(tamam)} kampanya iyi durumda")
        print(f"{'='*55}")
        for k in tamam:
            print(f"   ✅ {k.kampanya_isim[:50]}")
