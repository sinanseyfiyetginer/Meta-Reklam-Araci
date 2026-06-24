"""
derinlemesine.py — AdSet, Creative, Placement ve Dönüşüm derin analiz modülü.

Görev: Kampanya altındaki katmanları analiz eder.
       "Hangi kitle çalışıyor?" → AdSet analizi
       "Hangi görsel daha iyi?" → Creative analizi
       "Nerede gösterelim?" → Placement analizi
       "Kaç satış / lead geldi?" → Dönüşüm analizi
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ── Placement Türkçe İsimleri ─────────────────────────────────────────────────

PLACEMENT_ISIMLERI = {
    ("facebook",  "feed"):                "Facebook Ana Akış",
    ("facebook",  "right_hand_column"):   "Facebook Sağ Sütun",
    ("facebook",  "marketplace"):         "Facebook Marketplace",
    ("facebook",  "video_feeds"):         "Facebook Video Akışı",
    ("facebook",  "story"):               "Facebook Hikaye",
    ("facebook",  "search"):              "Facebook Arama",
    ("instagram", "stream"):              "Instagram Ana Akış",
    ("instagram", "story"):               "Instagram Hikaye",
    ("instagram", "explore"):             "Instagram Keşfet",
    ("instagram", "reels"):               "Instagram Reels",
    ("instagram", "explore_home"):        "Instagram Keşfet Anasayfa",
    ("audience_network", "classic"):      "Audience Network",
    ("audience_network", "rewarded_video"): "Audience Network Video",
    ("messenger",  "messenger_home"):     "Messenger Ana Sayfa",
    ("messenger",  "story"):              "Messenger Hikaye",
}

# Dönüşüm olay isimleri
DONUSUM_ISIMLERI = {
    "purchase":                                  "Satın Alma",
    "lead":                                      "Form / Lead",
    "complete_registration":                     "Kayıt Tamamlama",
    "add_to_cart":                               "Sepete Ekleme",
    "initiate_checkout":                         "Ödeme Başlatma",
    "view_content":                              "İçerik Görüntüleme",
    "search":                                    "Arama",
    "submit_application":                        "Başvuru",
    "offsite_conversion.fb_pixel_purchase":      "Piksel Satın Alma",
    "offsite_conversion.fb_pixel_lead":          "Piksel Lead",
    "offsite_conversion.fb_pixel_add_to_cart":   "Piksel Sepete Ekle",
}


# ── Veri Yapıları ─────────────────────────────────────────────────────────────

@dataclass
class AdSetSonuc:
    id: str
    isim: str
    kampanya_isim: str
    durum: str
    harcama: float = 0.0
    gosterim: int = 0
    tiklama: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    erisim: int = 0
    frequency: float = 0.0
    donusum: float = 0.0
    skor: int = 0
    oneri: str = ""


@dataclass
class CreativeSonuc:
    id: str
    isim: str
    adset_isim: str
    kampanya_isim: str
    durum: str
    gorsel_url: str = ""
    baslik: str = ""
    metin: str = ""
    harcama: float = 0.0
    gosterim: int = 0
    tiklama: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    video_mu: bool = False
    video_izlenme: float = 0.0   # ThruPlay sayısı
    hook_rate: float = 0.0       # İlk 3 sn izlenme / gösterim
    skor: int = 0
    oneri: str = ""


@dataclass
class PlacementSonuc:
    platform: str
    konum: str
    isim: str
    harcama: float = 0.0
    gosterim: int = 0
    tiklama: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    donusum: float = 0.0
    verimlilik: str = ""   # "Yüksek", "Orta", "Düşük"


@dataclass
class DonusumSonuc:
    olay_tipi: str
    isim: str
    sayi: float = 0.0
    deger: float = 0.0         # Toplam gelir
    maliyet_basina: float = 0.0  # Her dönüşüm kaça mal oldu


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _float(veri, key):
    try: return float(veri.get(key) or 0)
    except: return 0.0

def _int(veri, key):
    try: return int(float(veri.get(key) or 0))
    except: return 0

def _icgoru(ham):
    """Meta'nın iç içe insights formatını düzleştirir."""
    if not ham: return {}
    if "data" in ham:
        lst = ham["data"]
        return lst[0] if lst else {}
    return ham

def _donusum_say(actions, tipler=None):
    """Actions listesinden belirli tipteki dönüşümleri toplar."""
    if tipler is None:
        tipler = {"purchase", "lead", "complete_registration",
                  "submit_application", "offsite_conversion.fb_pixel_purchase",
                  "offsite_conversion.fb_pixel_lead"}
    toplam = 0.0
    for a in (actions or []):
        if a.get("action_type") in tipler:
            try: toplam += float(a.get("value", 0) or 0)
            except: pass
    return toplam

def _donusum_deger(action_values, tipler=None):
    """Action values listesinden gelir toplar."""
    if tipler is None:
        tipler = {"purchase", "offsite_conversion.fb_pixel_purchase"}
    toplam = 0.0
    for a in (action_values or []):
        if a.get("action_type") in tipler:
            try: toplam += float(a.get("value", 0) or 0)
            except: pass
    return toplam

def _skor(ctr, cpc, frequency=0):
    """Basit 0-100 skor."""
    puan = 0
    if ctr >= 2.0:   puan += 40
    elif ctr >= 1.0: puan += 25
    elif ctr >= 0.5: puan += 10
    if cpc <= 5:     puan += 30
    elif cpc <= 10:  puan += 20
    elif cpc <= 20:  puan += 10
    if frequency == 0 or frequency <= 2:   puan += 20
    elif frequency <= 3.5: puan += 12
    elif frequency <= 5:   puan += 5
    puan += 10  # temel puan
    return min(100, puan)

def _oneri(skor, frequency=0):
    if skor >= 80: return "🚀 Büyüt"
    if frequency >= 5: return "👥 Kitleyi Değiştir"
    if skor >= 60: return "✅ Sürdür"
    if skor >= 40: return "🎨 Kreatif Yenile"
    return "🔴 Durdur"


# ── AdSet Analizi ─────────────────────────────────────────────────────────────

def adset_analiz_et(ham_liste: list) -> list[AdSetSonuc]:
    """meta_api.adset_analiz() çıktısını AdSetSonuc listesine dönüştürür."""
    sonuclar = []
    for a in ham_liste:
        ig = _icgoru(a.get("insights", {}))
        kampanya = a.get("campaign") or {}

        harcama   = _float(ig, "spend")
        gosterim  = _int(ig, "impressions")
        tiklama   = _int(ig, "clicks")
        erisim    = _int(ig, "reach")
        frequency = _float(ig, "frequency")

        ctr = _float(ig, "ctr") or (tiklama / gosterim * 100 if gosterim else 0)
        cpc = _float(ig, "cpc") or (harcama / tiklama if tiklama else 0)

        donusum = _donusum_say(ig.get("actions"))
        s = _skor(ctr, cpc, frequency)

        sonuclar.append(AdSetSonuc(
            id=a.get("id", ""),
            isim=a.get("name", "İsimsiz AdSet"),
            kampanya_isim=kampanya.get("name", ""),
            durum=a.get("status", ""),
            harcama=harcama, gosterim=gosterim, tiklama=tiklama,
            ctr=ctr, cpc=cpc, erisim=erisim, frequency=frequency,
            donusum=donusum, skor=s, oneri=_oneri(s, frequency),
        ))

    sonuclar.sort(key=lambda x: x.harcama, reverse=True)
    return sonuclar


# ── Creative Analizi ──────────────────────────────────────────────────────────

def creative_analiz_et(ham_liste: list) -> list[CreativeSonuc]:
    """meta_api.reklam_analiz() çıktısını CreativeSonuc listesine dönüştürür."""
    sonuclar = []
    for a in ham_liste:
        ig       = _icgoru(a.get("insights", {}))
        creative = a.get("creative") or {}
        adset    = a.get("adset") or {}
        kampanya = a.get("campaign") or {}

        harcama  = _float(ig, "spend")
        gosterim = _int(ig, "impressions")
        tiklama  = _int(ig, "clicks")
        ctr = _float(ig, "ctr") or (tiklama / gosterim * 100 if gosterim else 0)
        cpc = _float(ig, "cpc") or (harcama / tiklama if tiklama else 0)

        # Video metrikleri
        thruplay = 0.0
        for v in (ig.get("video_thruplay_watched_actions") or []):
            try: thruplay += float(v.get("value", 0) or 0)
            except: pass

        hook = 0.0
        for v in (ig.get("video_play_actions") or []):
            try: hook = float(v.get("value", 0) or 0)
            except: pass
        hook_rate = (hook / gosterim * 100) if gosterim and hook else 0.0
        video_mu  = thruplay > 0 or hook > 0

        s = _skor(ctr, cpc)
        # Video bonus: hook rate yüksekse skor artır
        if video_mu and hook_rate >= 30:
            s = min(100, s + 10)

        sonuclar.append(CreativeSonuc(
            id=a.get("id", ""),
            isim=a.get("name", "İsimsiz Reklam"),
            adset_isim=adset.get("name", ""),
            kampanya_isim=kampanya.get("name", ""),
            durum=a.get("status", ""),
            gorsel_url=creative.get("image_url", "") or creative.get("thumbnail_url", ""),
            baslik=creative.get("title", ""),
            metin=creative.get("body", ""),
            harcama=harcama, gosterim=gosterim, tiklama=tiklama,
            ctr=ctr, cpc=cpc,
            video_mu=video_mu, video_izlenme=thruplay, hook_rate=hook_rate,
            skor=s, oneri=_oneri(s),
        ))

    sonuclar.sort(key=lambda x: x.harcama, reverse=True)
    return sonuclar


# ── Placement Analizi ─────────────────────────────────────────────────────────

def placement_analiz_et(ham_liste: list) -> list[PlacementSonuc]:
    """meta_api.placement_dagilim() çıktısını PlacementSonuc listesine dönüştürür."""
    sonuclar = []
    for p in ham_liste:
        platform = p.get("publisher_platform", "")
        konum    = p.get("platform_position", "")
        isim     = PLACEMENT_ISIMLERI.get((platform, konum), f"{platform} / {konum}")

        harcama  = _float(p, "spend")
        gosterim = _int(p, "impressions")
        tiklama  = _int(p, "clicks")
        ctr = _float(p, "ctr") or (tiklama / gosterim * 100 if gosterim else 0)
        cpc = _float(p, "cpc") or (harcama / tiklama if tiklama else 0)
        cpm = _float(p, "cpm") or (harcama / gosterim * 1000 if gosterim else 0)
        donusum = _donusum_say(p.get("actions"))

        # Verimlilik skoru
        if ctr >= 1.5 and cpc <= 8:
            verimlilik = "🟢 Yüksek"
        elif ctr >= 0.8 or cpc <= 12:
            verimlilik = "🟡 Orta"
        else:
            verimlilik = "🔴 Düşük"

        if harcama > 0 or gosterim > 0:
            sonuclar.append(PlacementSonuc(
                platform=platform, konum=konum, isim=isim,
                harcama=harcama, gosterim=gosterim, tiklama=tiklama,
                ctr=ctr, cpc=cpc, cpm=cpm, donusum=donusum,
                verimlilik=verimlilik,
            ))

    sonuclar.sort(key=lambda x: x.harcama, reverse=True)
    return sonuclar


# ── Dönüşüm Analizi ───────────────────────────────────────────────────────────

def donusum_analiz_et(ham_veri: dict, toplam_harcama: float) -> list[DonusumSonuc]:
    """
    meta_api.donusum_ozeti() çıktısından dönüşüm türlerini analiz eder.
    Her olay için maliyet, gelir ve ROAS hesaplar.
    """
    actions       = ham_veri.get("actions") or []
    action_values = ham_veri.get("action_values") or []

    # Dönüşüm sayıları
    sayilar = {}
    for a in actions:
        tip = a.get("action_type", "")
        if tip in DONUSUM_ISIMLERI:
            try: sayilar[tip] = sayilar.get(tip, 0) + float(a.get("value", 0) or 0)
            except: pass

    # Dönüşüm değerleri (gelir)
    degerler = {}
    for a in action_values:
        tip = a.get("action_type", "")
        if tip in DONUSUM_ISIMLERI:
            try: degerler[tip] = degerler.get(tip, 0) + float(a.get("value", 0) or 0)
            except: pass

    sonuclar = []
    for tip, sayi in sayilar.items():
        if sayi <= 0:
            continue
        deger = degerler.get(tip, 0)
        maliyet = toplam_harcama / sayi if sayi > 0 else 0

        sonuclar.append(DonusumSonuc(
            olay_tipi=tip,
            isim=DONUSUM_ISIMLERI.get(tip, tip),
            sayi=sayi,
            deger=deger,
            maliyet_basina=maliyet,
        ))

    sonuclar.sort(key=lambda x: x.sayi, reverse=True)
    return sonuclar


# ── Rapor Bölümleri ───────────────────────────────────────────────────────────

def adset_bolumu_yaz(adsetler: list[AdSetSonuc]) -> str:
    veri_olan = [a for a in adsetler if a.harcama > 0]
    if not veri_olan:
        return ""

    satirlar = [
        "## 👥 Reklam Seti (Kitle) Analizi\n",
        "> Hangi kitle segmenti daha verimli çalışıyor?\n",
        "| Reklam Seti | Kampanya | Skor | Harcama | CTR | TBM | Frekans | Öneri |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for a in veri_olan[:10]:
        isim = a.isim[:30] + "…" if len(a.isim) > 30 else a.isim
        kamp = a.kampanya_isim[:25] + "…" if len(a.kampanya_isim) > 25 else a.kampanya_isim
        freq = f"{a.frequency:.1f}x" if a.frequency > 0 else "—"
        skor_ikon = "🟢" if a.skor >= 70 else ("🟡" if a.skor >= 50 else "🔴")
        satirlar.append(
            f"| {isim} | {kamp} | {skor_ikon} {a.skor} "
            f"| {a.harcama:,.2f} ₺ | %{a.ctr:.2f} "
            f"| {a.cpc:.2f} ₺ | {freq} | {a.oneri} |"
        )
    satirlar.append("")
    return "\n".join(satirlar)


def creative_bolumu_yaz(creativeler: list[CreativeSonuc]) -> str:
    veri_olan = [c for c in creativeler if c.harcama > 0]
    if not veri_olan:
        return ""

    satirlar = [
        "## 🎨 Reklam Kreatifleri (Görseller / Metinler)\n",
        "> Hangi reklam görseli veya metni daha iyi performans gösteriyor?\n",
    ]

    # En iyi 3
    en_iyi = sorted(veri_olan, key=lambda x: x.skor, reverse=True)[:3]
    if en_iyi:
        satirlar.append("### 🏆 En İyi Performanslı Reklamlar\n")
        for i, c in enumerate(en_iyi, 1):
            video_bilgi = f" | Hook Rate: %{c.hook_rate:.1f}" if c.video_mu else ""
            satirlar.append(
                f"**{i}. {c.isim[:50]}**  \n"
                f"Skor: {c.skor}/100 | CTR: %{c.ctr:.2f} | TBM: {c.cpc:.2f} ₺"
                f" | Harcama: {c.harcama:,.2f} ₺{video_bilgi}  \n"
                f"AdSet: {c.adset_isim[:40]}\n"
            )

    # Tablo
    satirlar += [
        "### Tüm Reklamlar\n",
        "| Reklam | Skor | Harcama | CTR | TBM | Video | Öneri |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in veri_olan[:15]:
        isim = c.isim[:28] + "…" if len(c.isim) > 28 else c.isim
        video = f"✅ %{c.hook_rate:.0f} hook" if c.video_mu else "—"
        skor_ikon = "🟢" if c.skor >= 70 else ("🟡" if c.skor >= 50 else "🔴")
        satirlar.append(
            f"| {isim} | {skor_ikon} {c.skor} "
            f"| {c.harcama:,.2f} ₺ | %{c.ctr:.2f} "
            f"| {c.cpc:.2f} ₺ | {video} | {c.oneri} |"
        )
    satirlar.append("")
    return "\n".join(satirlar)


def placement_bolumu_yaz(placementler: list[PlacementSonuc]) -> str:
    if not placementler:
        return ""

    satirlar = [
        "## 📍 Yerleşim (Placement) Analizi\n",
        "> Feed mi, Stories mi, Reels mi daha verimli?\n",
        "| Yerleşim | Harcama | Gösterim | CTR | TBM | CPM | Verimlilik |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in placementler:
        satirlar.append(
            f"| {p.isim} "
            f"| {p.harcama:,.2f} ₺ "
            f"| {p.gosterim:,} "
            f"| %{p.ctr:.2f} "
            f"| {p.cpc:.2f} ₺ "
            f"| {p.cpm:.2f} ₺ "
            f"| {p.verimlilik} |"
        )
    satirlar.append("")
    return "\n".join(satirlar)


def donusum_bolumu_yaz(donusumler: list[DonusumSonuc], toplam_harcama: float) -> str:
    if not donusumler:
        return ""

    satirlar = [
        "## 💰 Dönüşüm Analizi\n",
        "> Tıklama değil — satış, form, sepet takibi.\n",
        "| Dönüşüm Türü | Adet | Gelir | Dönüşüm Başı Maliyet |",
        "|---|---|---|---|",
    ]
    for d in donusumler:
        gelir = f"{d.deger:,.2f} ₺" if d.deger > 0 else "—"
        satirlar.append(
            f"| {d.isim} | {d.sayi:.0f} | {gelir} | {d.maliyet_basina:,.2f} ₺ |"
        )

    # Toplam ROAS
    toplam_gelir = sum(d.deger for d in donusumler)
    if toplam_gelir > 0 and toplam_harcama > 0:
        roas = toplam_gelir / toplam_harcama
        satirlar.append(f"\n**Toplam ROAS: {roas:.2f}x** _(1 ₺ harcamaya karşı {roas:.2f} ₺ gelir)_\n")

    satirlar.append("")
    return "\n".join(satirlar)
