"""
butce_ve_zaman.py — Bütçe pace takibi, demografik analiz ve zaman performansı.

Görev:
  1. Bütçe Pace    → Ay ortasında bütçe bitecek mi? Harcama hızı doğru mu?
  2. Demografik    → Hangi yaş/cinsiyet grubu daha verimli?
  3. Zaman Analizi → Haftanın hangi günü, günün hangi saati en iyi performans?
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date
from calendar import monthrange


# ── Sabit Etiketler ───────────────────────────────────────────────────────────

GUN_ISIMLERI = {
    "Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba",
    "Thursday": "Perşembe", "Friday": "Cuma",
    "Saturday": "Cumartesi", "Sunday": "Pazar",
}

YAS_SIRASI = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]


# ── Veri Yapıları ─────────────────────────────────────────────────────────────

@dataclass
class ButcePace:
    """Bir kampanya veya hesabın bütçe pace durumu."""
    kampanya_isim: str = ""
    aylik_butce: float = 0.0        # Bu ay için toplam bütçe (TRY)
    harcanan: float = 0.0           # Bu ay harcanan (TRY)
    kalan: float = 0.0              # Kalan bütçe (TRY)
    gecen_gun: int = 0              # Ayın kaçıncı günündeyiz
    kalan_gun: int = 0              # Kaç gün kaldı
    beklenen_harcama: float = 0.0   # Bu hızla devam ederse ay sonunda ne kadar harcanır
    pace_yuzdesi: float = 0.0       # Harcama / Bütçe × 100
    zaman_yuzdesi: float = 0.0      # Gecen gün / Ay uzunluğu × 100
    durum: str = ""                 # "✅ Dengeli", "⚠️ Yavaş", "🔴 Hızlı"
    uyari: str = ""


@dataclass
class DemografikSegment:
    """Bir yaş/cinsiyet segmentinin performansı."""
    yas_grubu: str = ""
    cinsiyet: str = ""
    etiket: str = ""        # "25-34 Kadın" gibi
    gosterim: int = 0
    tiklama: int = 0
    harcama: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    donusum: float = 0.0
    verimlilik: str = ""    # "🟢 Yüksek", "🟡 Orta", "🔴 Düşük"


@dataclass
class SaatlikPerformans:
    """Bir saatin veya günün performansı."""
    etiket: str = ""        # "14:00" veya "Salı"
    gosterim: int = 0
    tiklama: int = 0
    harcama: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    skor: float = 0.0       # Normalize edilmiş verimlilik skoru


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _f(d, k):
    try: return float(d.get(k) or 0)
    except: return 0.0

def _i(d, k):
    try: return int(float(d.get(k) or 0))
    except: return 0

def _donusum(actions):
    tipler = {"purchase", "lead", "complete_registration",
              "offsite_conversion.fb_pixel_purchase"}
    t = 0.0
    for a in (actions or []):
        if a.get("action_type") in tipler:
            try: t += float(a.get("value", 0) or 0)
            except: pass
    return t


# ── 1. BÜTÇE PACE TAKİBİ ─────────────────────────────────────────────────────

def butce_pace_hesapla(kampanyalar: list, aylik_butce_tl: float = 0.0) -> ButcePace:
    """
    Kampanyaların bu ayki toplam harcamasını ve bütçe durumunu hesaplar.

    kampanyalar    : meta_api.kampanyalari_cek('this_month') çıktısı
    aylik_butce_tl : Müşterinin bu ay için belirlediği toplam bütçe (TRY)
                     0 girilirse kampanya bütçelerinden otomatik hesaplanır
    """
    bugun = date.today()
    ay_uzunlugu = monthrange(bugun.year, bugun.month)[1]
    gecen_gun = bugun.day
    kalan_gun = ay_uzunlugu - gecen_gun

    # Bu ay toplam harcama
    toplam_harcama = 0.0
    toplam_butce   = 0.0

    for k in kampanyalar:
        ig = k.get("insights", {})
        if "data" in (ig or {}):
            ig = ig["data"][0] if ig["data"] else {}
        toplam_harcama += _f(ig, "spend")

        # Günlük bütçeyi aylık bütçeye çevir
        gunluk = _f(k, "daily_budget") / 100  # Meta cent cinsinden verir
        if gunluk > 0:
            toplam_butce += gunluk * ay_uzunlugu
        else:
            omur_boyu = _f(k, "lifetime_budget") / 100
            toplam_butce += omur_boyu

    # Manuel bütçe girilmişse onu kullan
    if aylik_butce_tl > 0:
        toplam_butce = aylik_butce_tl

    # Pace hesapla
    if toplam_butce == 0:
        # Bütçe bilgisi yoksa sadece harcama göster
        return ButcePace(
            kampanya_isim="Tüm Hesap",
            harcanan=toplam_harcama,
            gecen_gun=gecen_gun,
            kalan_gun=kalan_gun,
            durum="ℹ️ Bütçe bilgisi girilmemiş",
            uyari="Müşteri config'ine 'aylik_butce' ekle",
        )

    zaman_yuzde = (gecen_gun / ay_uzunlugu) * 100
    pace_yuzde  = (toplam_harcama / toplam_butce) * 100 if toplam_butce > 0 else 0

    # Bu hızla ay sonunda ne kadar harcanır?
    gunluk_ort     = toplam_harcama / gecen_gun if gecen_gun > 0 else 0
    beklenen       = gunluk_ort * ay_uzunlugu
    kalan_butce    = toplam_butce - toplam_harcama

    # Durum değerlendirmesi
    fark = pace_yuzde - zaman_yuzde
    if abs(fark) <= 10:
        durum = "✅ Dengeli"
        uyari = f"Harcama hızı dengeli. Beklenen ay sonu: {beklenen:,.0f} ₺"
    elif fark > 10:
        durum = "🔴 Hızlı Harcama"
        bitis_gunu = int(kalan_butce / gunluk_ort) if gunluk_ort > 0 else 0
        uyari = (
            f"Bu hızla bütçe {bitis_gunu} gün içinde biter "
            f"({(bugun.day + bitis_gunu)}. günde). "
            f"Günlük bütçeyi düşür veya hedeflemeyi daralt."
        )
    else:
        durum = "⚠️ Yavaş Harcama"
        uyari = (
            f"Bütçenin yalnızca %{pace_yuzde:.0f}'i harcandı "
            f"ama ayın %{zaman_yuzde:.0f}'i geçti. "
            f"Kitle genişletilmeli veya teklif artırılmalı."
        )

    return ButcePace(
        kampanya_isim="Tüm Hesap",
        aylik_butce=toplam_butce,
        harcanan=toplam_harcama,
        kalan=kalan_butce,
        gecen_gun=gecen_gun,
        kalan_gun=kalan_gun,
        beklenen_harcama=beklenen,
        pace_yuzdesi=pace_yuzde,
        zaman_yuzdesi=zaman_yuzde,
        durum=durum,
        uyari=uyari,
    )


# ── 2. DEMOGRAFİK ANALİZ ─────────────────────────────────────────────────────

def demografik_analiz_et(ham_liste: list) -> list[DemografikSegment]:
    """
    meta_api.demografik_dagilim() çıktısını analiz eder.
    Yaş ve cinsiyet bazında CTR, CPC, dönüşüm hesaplar.
    """
    sonuclar = []

    cinsiyet_tr = {"male": "Erkek", "female": "Kadın", "unknown": "Bilinmiyor"}

    for p in ham_liste:
        yas     = p.get("age", "")
        cinsiyet = p.get("gender", "")
        etiket  = f"{yas} {cinsiyet_tr.get(cinsiyet, cinsiyet)}"

        gosterim = _i(p, "impressions")
        tiklama  = _i(p, "clicks")
        harcama  = _f(p, "spend")
        ctr = _f(p, "ctr") or (tiklama / gosterim * 100 if gosterim else 0)
        cpc = _f(p, "cpc") or (harcama / tiklama if tiklama else 0)
        don = _donusum(p.get("actions"))

        if gosterim == 0 and harcama == 0:
            continue

        # Verimlilik
        if ctr >= 1.5 and (cpc <= 8 or cpc == 0):
            verimlilik = "🟢 Yüksek"
        elif ctr >= 0.8 or cpc <= 12:
            verimlilik = "🟡 Orta"
        else:
            verimlilik = "🔴 Düşük"

        sonuclar.append(DemografikSegment(
            yas_grubu=yas, cinsiyet=cinsiyet, etiket=etiket,
            gosterim=gosterim, tiklama=tiklama, harcama=harcama,
            ctr=ctr, cpc=cpc, donusum=don, verimlilik=verimlilik,
        ))

    # CTR'a göre sırala (en iyiden en kötüye)
    sonuclar.sort(key=lambda x: x.ctr, reverse=True)
    return sonuclar


# ── 3. SAATLİK / GÜNLÜK PERFORMANS ───────────────────────────────────────────

def saatlik_analiz_et(ham_liste: list) -> list[SaatlikPerformans]:
    """
    meta_api.saatlik_dagilim() çıktısından saatlik performans üretir.
    En verimli saatleri bulur.
    """
    sonuclar = []
    for p in ham_liste:
        saat_str = p.get("hourly_stats_aggregated_by_advertiser_time_zone", "")
        if not saat_str:
            continue

        # "00:00 - 01:00" → "00:00"
        etiket = saat_str.split(" - ")[0] if " - " in saat_str else saat_str

        gosterim = _i(p, "impressions")
        tiklama  = _i(p, "clicks")
        harcama  = _f(p, "spend")
        ctr = _f(p, "ctr") or (tiklama / gosterim * 100 if gosterim else 0)
        cpc = _f(p, "cpc") or (harcama / tiklama if tiklama else 0)

        if gosterim == 0:
            continue

        sonuclar.append(SaatlikPerformans(
            etiket=etiket, gosterim=gosterim, tiklama=tiklama,
            harcama=harcama, ctr=ctr, cpc=cpc,
        ))

    # Verimlilik skoru: CTR yüksek + CPC düşük = iyi
    if sonuclar:
        max_ctr = max(s.ctr for s in sonuclar) or 1
        min_cpc = min(s.cpc for s in sonuclar if s.cpc > 0) or 1
        for s in sonuclar:
            ctr_norm = s.ctr / max_ctr
            cpc_norm = (1 / s.cpc * min_cpc) if s.cpc > 0 else 0
            s.skor = (ctr_norm * 0.6 + cpc_norm * 0.4) * 100

    sonuclar.sort(key=lambda x: x.skor, reverse=True)
    return sonuclar


def gunluk_analiz_et(saatlik_liste: list[SaatlikPerformans]) -> dict[str, SaatlikPerformans]:
    """
    Saatlik verileri gün bazında gruplar (Meta bazı hesaplarda gün verisi verir).
    """
    return saatlik_liste  # Saatlik veriyi döndür, raporda grup olarak göster


# ── RAPOR BÖLÜMLERİ ──────────────────────────────────────────────────────────

def butce_bolumu_yaz(pace: ButcePace) -> str:
    if not pace or pace.aylik_butce == 0:
        return ""

    # Görsel progress bar
    dolu   = int(pace.pace_yuzdesi / 5)   # 20 karakterlik bar
    zaman  = int(pace.zaman_yuzdesi / 5)
    dolu   = min(20, dolu)
    zaman  = min(20, zaman)

    harcama_bar = "█" * dolu + "░" * (20 - dolu)
    zaman_bar   = "█" * zaman + "░" * (20 - zaman)

    satirlar = [
        "## 💰 Bütçe Pace Takibi\n",
        f"> {pace.durum}\n",
        f"| | Değer |",
        f"|---|---|",
        f"| Aylık Bütçe | {pace.aylik_butce:,.0f} ₺ |",
        f"| Bu Ay Harcanan | {pace.harcanan:,.2f} ₺ |",
        f"| Kalan Bütçe | {pace.kalan:,.2f} ₺ |",
        f"| Geçen Gün | {pace.gecen_gun}. gün |",
        f"| Kalan Gün | {pace.kalan_gun} gün |",
        f"| Beklenen Ay Sonu | {pace.beklenen_harcama:,.0f} ₺ |",
        "",
        "```",
        f"Harcama : {harcama_bar} %{pace.pace_yuzdesi:.0f}",
        f"Zaman   : {zaman_bar} %{pace.zaman_yuzdesi:.0f}",
        "```",
        "",
        f"> ⚡ {pace.uyari}\n",
    ]
    return "\n".join(satirlar)


def demografik_bolumu_yaz(segmentler: list[DemografikSegment]) -> str:
    if not segmentler:
        return ""

    satirlar = [
        "## 👤 Demografik Analiz (Yaş & Cinsiyet)\n",
        "> Hangi yaş grubu ve cinsiyet daha verimli dönüşüm yapıyor?\n",
    ]

    # En iyi 3 segment
    en_iyi = [s for s in segmentler if s.ctr > 0][:3]
    if en_iyi:
        satirlar.append("### 🏆 En Verimli Segmentler\n")
        for i, s in enumerate(en_iyi, 1):
            don_str = f" | Dönüşüm: {s.donusum:.0f}" if s.donusum > 0 else ""
            satirlar.append(
                f"**{i}. {s.etiket}** — "
                f"CTR: %{s.ctr:.2f} | TBM: {s.cpc:.2f} ₺"
                f"{don_str} | {s.verimlilik}\n"
            )

    # Tam tablo
    satirlar += [
        "### Tüm Segmentler\n",
        "| Segment | Gösterim | Tıklama | CTR | TBM | Verimlilik |",
        "|---|---|---|---|---|---|",
    ]
    for s in segmentler:
        satirlar.append(
            f"| {s.etiket} "
            f"| {s.gosterim:,} "
            f"| {s.tiklama:,} "
            f"| %{s.ctr:.2f} "
            f"| {s.cpc:.2f} ₺ "
            f"| {s.verimlilik} |"
        )
    satirlar.append("")
    return "\n".join(satirlar)


def saatlik_bolumu_yaz(saatler: list[SaatlikPerformans]) -> str:
    if not saatler:
        return ""

    # En iyi ve en kötü 5 saat
    en_iyi  = saatler[:5]
    en_kotu = sorted(saatler, key=lambda x: x.skor)[:3]

    satirlar = [
        "## ⏰ Saatlik Performans Analizi\n",
        "> Günün hangi saatinde reklam göstermek daha verimli?\n",
        "### 🟢 En Verimli Saatler\n",
        "| Saat | Gösterim | CTR | TBM | Verimlilik Skoru |",
        "|---|---|---|---|---|",
    ]
    for s in en_iyi:
        skor_bar = "█" * int(s.skor / 10) + "░" * (10 - int(s.skor / 10))
        satirlar.append(
            f"| {s.etiket} "
            f"| {s.gosterim:,} "
            f"| %{s.ctr:.2f} "
            f"| {s.cpc:.2f} ₺ "
            f"| {skor_bar} {s.skor:.0f} |"
        )

    if en_kotu and en_kotu[0].skor < 40:
        satirlar += [
            "",
            "### 🔴 Verimsiz Saatler (Bütçeyi Kıs)\n",
            "| Saat | Gösterim | CTR | TBM |",
            "|---|---|---|---|",
        ]
        for s in en_kotu:
            satirlar.append(
                f"| {s.etiket} "
                f"| {s.gosterim:,} "
                f"| %{s.ctr:.2f} "
                f"| {s.cpc:.2f} ₺ |"
            )

    satirlar.append("")
    return "\n".join(satirlar)
