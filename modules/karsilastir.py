"""
karsilastir.py — Dönem karşılaştırma motoru.

Görev: Mevcut dönem ile önceki dönemi kıyaslar.
       Her metrik için yüzde değişim ve trend oku üretir.
       "Bu hafta geçen haftadan iyi mi kötü mü?" sorusunu yanıtlar.
"""

from __future__ import annotations
from dataclasses import dataclass


# ── Karşılaştırma Veri Yapısı ─────────────────────────────────────────────────

@dataclass
class MetrikKarsilastirma:
    """Tek bir metriğin iki dönem karşılaştırması."""
    isim: str
    simdi: float
    once: float
    degisim_yuzde: float = 0.0
    trend: str = "→"        # ↑ arttı, ↓ düştü, → değişmedi
    iyi_mi: bool = True     # Bu değişim iyi mi kötü mü?
    aciklama: str = ""


@dataclass
class DonemKarsilastirma:
    """Tüm metriklerin dönem karşılaştırması."""
    harcama:   MetrikKarsilastirma = None
    gosterim:  MetrikKarsilastirma = None
    tiklama:   MetrikKarsilastirma = None
    ctr:       MetrikKarsilastirma = None
    cpc:       MetrikKarsilastirma = None
    cpm:       MetrikKarsilastirma = None
    erisim:    MetrikKarsilastirma = None
    frequency: MetrikKarsilastirma = None
    donusum:   MetrikKarsilastirma = None
    genel_trend: str = ""   # "İyileşiyor", "Kötüleşiyor", "Stabil"


# ── Yüzde Değişim Hesabı ─────────────────────────────────────────────────────

def _degisim_hesapla(simdi: float, once: float) -> tuple[float, str]:
    """
    İki değer arasındaki yüzde değişimi ve trend okunu döndürür.
    Sıfıra bölme hatası olmaz.
    """
    if once == 0:
        if simdi > 0:
            return 100.0, "↑"
        return 0.0, "→"

    degisim = ((simdi - once) / once) * 100

    if degisim > 2:
        trend = "↑"
    elif degisim < -2:
        trend = "↓"
    else:
        trend = "→"

    return round(degisim, 1), trend


def _float_al(veri: dict, anahtar: str) -> float:
    """Dict'ten güvenli float çekme."""
    deger = veri.get(anahtar, 0)
    try:
        return float(deger or 0)
    except (TypeError, ValueError):
        return 0.0


def _donusum_al(veri: dict) -> float:
    """Actions listesinden toplam dönüşüm sayısını çeker."""
    actions = veri.get("actions") or []
    donusum_tipleri = {"purchase", "lead", "complete_registration", "submit_application"}
    toplam = 0.0
    for a in actions:
        if a.get("action_type") in donusum_tipleri:
            try:
                toplam += float(a.get("value", 0) or 0)
            except (TypeError, ValueError):
                pass
    return toplam


# ── Ana Karşılaştırma Fonksiyonu ──────────────────────────────────────────────

def donem_karsilastir(simdi_veri: dict, once_veri: dict) -> DonemKarsilastirma:
    """
    İki dönemin verilerini alır, tam karşılaştırma üretir.

    Parametreler:
    - simdi_veri : Mevcut dönem özeti (meta_api.hesap_ozeti())
    - once_veri  : Önceki dönem özeti (meta_api.onceki_donem_ozeti())
    """
    karsilastirma = DonemKarsilastirma()

    # ── Harcama ───────────────────────────────────────────────────────────────
    s_harcama = _float_al(simdi_veri, "spend")
    o_harcama = _float_al(once_veri,  "spend")
    d, t = _degisim_hesapla(s_harcama, o_harcama)
    karsilastirma.harcama = MetrikKarsilastirma(
        isim="Harcama", simdi=s_harcama, once=o_harcama,
        degisim_yuzde=d, trend=t,
        iyi_mi=True,  # Harcama artışı genellikle nötr
        aciklama=f"Önceki dönem: {o_harcama:,.2f} ₺ → Şimdi: {s_harcama:,.2f} ₺",
    )

    # ── Gösterim ──────────────────────────────────────────────────────────────
    s_gosterim = _float_al(simdi_veri, "impressions")
    o_gosterim = _float_al(once_veri,  "impressions")
    d, t = _degisim_hesapla(s_gosterim, o_gosterim)
    karsilastirma.gosterim = MetrikKarsilastirma(
        isim="Gösterim", simdi=s_gosterim, once=o_gosterim,
        degisim_yuzde=d, trend=t, iyi_mi=(t == "↑"),
        aciklama=f"{o_gosterim:,.0f} → {s_gosterim:,.0f}",
    )

    # ── Tıklama ───────────────────────────────────────────────────────────────
    s_tiklama = _float_al(simdi_veri, "clicks")
    o_tiklama = _float_al(once_veri,  "clicks")
    d, t = _degisim_hesapla(s_tiklama, o_tiklama)
    karsilastirma.tiklama = MetrikKarsilastirma(
        isim="Tıklama", simdi=s_tiklama, once=o_tiklama,
        degisim_yuzde=d, trend=t, iyi_mi=(t == "↑"),
        aciklama=f"{o_tiklama:,.0f} → {s_tiklama:,.0f}",
    )

    # ── CTR (Yükselmesi iyi) ──────────────────────────────────────────────────
    s_ctr = _float_al(simdi_veri, "ctr")
    o_ctr = _float_al(once_veri,  "ctr")
    d, t = _degisim_hesapla(s_ctr, o_ctr)
    karsilastirma.ctr = MetrikKarsilastirma(
        isim="CTR", simdi=s_ctr, once=o_ctr,
        degisim_yuzde=d, trend=t, iyi_mi=(t == "↑"),
        aciklama=f"%{o_ctr:.2f} → %{s_ctr:.2f}",
    )

    # ── CPC (Düşmesi iyi) ─────────────────────────────────────────────────────
    s_cpc = _float_al(simdi_veri, "cpc")
    o_cpc = _float_al(once_veri,  "cpc")
    d, t = _degisim_hesapla(s_cpc, o_cpc)
    karsilastirma.cpc = MetrikKarsilastirma(
        isim="TBM (CPC)", simdi=s_cpc, once=o_cpc,
        degisim_yuzde=d, trend=t,
        iyi_mi=(t == "↓"),  # CPC düşmesi iyi!
        aciklama=f"{o_cpc:.2f} ₺ → {s_cpc:.2f} ₺",
    )

    # ── CPM (Düşmesi iyi) ─────────────────────────────────────────────────────
    s_cpm = _float_al(simdi_veri, "cpm")
    o_cpm = _float_al(once_veri,  "cpm")
    d, t = _degisim_hesapla(s_cpm, o_cpm)
    karsilastirma.cpm = MetrikKarsilastirma(
        isim="CPM", simdi=s_cpm, once=o_cpm,
        degisim_yuzde=d, trend=t,
        iyi_mi=(t == "↓"),
        aciklama=f"{o_cpm:.2f} ₺ → {s_cpm:.2f} ₺",
    )

    # ── Erişim ────────────────────────────────────────────────────────────────
    s_erisim = _float_al(simdi_veri, "reach")
    o_erisim = _float_al(once_veri,  "reach")
    d, t = _degisim_hesapla(s_erisim, o_erisim)
    karsilastirma.erisim = MetrikKarsilastirma(
        isim="Erişim", simdi=s_erisim, once=o_erisim,
        degisim_yuzde=d, trend=t, iyi_mi=(t == "↑"),
        aciklama=f"{o_erisim:,.0f} → {s_erisim:,.0f} kişi",
    )

    # ── Frekans (Düşmesi iyi) ─────────────────────────────────────────────────
    s_freq = _float_al(simdi_veri, "frequency")
    o_freq = _float_al(once_veri,  "frequency")
    d, t = _degisim_hesapla(s_freq, o_freq)
    karsilastirma.frequency = MetrikKarsilastirma(
        isim="Frekans", simdi=s_freq, once=o_freq,
        degisim_yuzde=d, trend=t,
        iyi_mi=(t == "↓"),
        aciklama=f"{o_freq:.1f}x → {s_freq:.1f}x",
    )

    # ── Dönüşüm ───────────────────────────────────────────────────────────────
    s_don = _donusum_al(simdi_veri)
    o_don = _donusum_al(once_veri)
    d, t = _degisim_hesapla(s_don, o_don)
    karsilastirma.donusum = MetrikKarsilastirma(
        isim="Dönüşüm", simdi=s_don, once=o_don,
        degisim_yuzde=d, trend=t, iyi_mi=(t == "↑"),
        aciklama=f"{o_don:.0f} → {s_don:.0f} dönüşüm",
    )

    # ── Genel Trend ───────────────────────────────────────────────────────────
    karsilastirma.genel_trend = _genel_trend_hesapla(karsilastirma)

    return karsilastirma


def _genel_trend_hesapla(k: DonemKarsilastirma) -> str:
    """
    Tüm metriklere bakarak genel trendi belirler.
    İyi değişimleri sayar — çoğunluk kazanır.
    """
    metrikler = [k.ctr, k.cpc, k.cpm, k.tiklama, k.erisim]
    iyi = sum(1 for m in metrikler if m and m.iyi_mi and m.trend != "→")
    kotu = sum(1 for m in metrikler if m and not m.iyi_mi and m.trend != "→")

    if iyi > kotu + 1:
        return "📈 İyileşiyor"
    elif kotu > iyi + 1:
        return "📉 Kötüleşiyor"
    else:
        return "📊 Stabil"


# ── Rapor Bölümü Üret ─────────────────────────────────────────────────────────

def karsilastirma_bolumu_yaz(k: DonemKarsilastirma) -> str:
    """Karşılaştırma verilerini Markdown bölümüne dönüştürür."""
    if not k:
        return ""

    satirlar = [
        "## 📊 Dönem Karşılaştırması\n",
        f"> Genel Trend: **{k.genel_trend}**\n",
        "| Metrik | Önceki Dönem | Bu Dönem | Değişim | Durum |",
        "|---|---|---|---|---|",
    ]

    def satir(m, format_fn):
        if not m:
            return ""
        yon  = "✅" if m.iyi_mi and m.trend != "→" else ("❌" if not m.iyi_mi and m.trend != "→" else "➖")
        isk  = f"+{m.degisim_yuzde:.1f}%" if m.degisim_yuzde > 0 else f"{m.degisim_yuzde:.1f}%"
        return f"| {m.isim} | {format_fn(m.once)} | {format_fn(m.simdi)} | {m.trend} {isk} | {yon} |"

    def para(v):  return f"{v:,.2f} ₺"
    def sayi(v):  return f"{v:,.0f}"
    def yuzde(v): return f"%{v:.2f}"
    def kere(v):  return f"{v:.1f}x"

    satirlar.append(satir(k.harcama,   para))
    satirlar.append(satir(k.gosterim,  sayi))
    satirlar.append(satir(k.tiklama,   sayi))
    satirlar.append(satir(k.ctr,       yuzde))
    satirlar.append(satir(k.cpc,       para))
    satirlar.append(satir(k.cpm,       para))
    satirlar.append(satir(k.erisim,    sayi))
    if k.frequency and k.frequency.simdi > 0:
        satirlar.append(satir(k.frequency, kere))
    if k.donusum and (k.donusum.simdi > 0 or k.donusum.once > 0):
        satirlar.append(satir(k.donusum, sayi))

    satirlar.append("")
    return "\n".join(s for s in satirlar if s != "")
