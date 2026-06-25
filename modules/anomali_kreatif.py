"""
anomali_kreatif.py — Anomali tespiti, kreatif yorgunluk ve bütçe dağılım önerileri.

Görev:
  1. Anomali Tespiti      → Ani metrik değişikliklerini yakala (CTR düştü, harcama patladı)
  2. Kreatif Yorgunluk    → Frequency + CTR + Hook Rate'e göre kreatiflerin "bitip bitmediğini" ölç
  3. Bütçe Önerisi        → Düşük performanslı kampanyadan yüksek performanslıya bütçe kaydır
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ── Eşik Değerleri ────────────────────────────────────────────────────────────

ANOMALI_ESIKLER = {
    "ctr_dusus":       -30,   # CTR bu kadar düşerse anomali
    "cpc_artis":        40,   # CPC bu kadar artarsa anomali
    "harcama_artis":    60,   # Harcama bu kadar artarsa anomali
    "gosterim_dusus":  -40,   # Gösterim bu kadar düşerse anomali
    "donusum_dusus":   -35,   # Dönüşüm bu kadar düşerse anomali
}

YORGUNLUK_ESIKLER = {
    "frequency_uyari":  3.0,  # Bu üstü sarı uyarı
    "frequency_kritik": 5.0,  # Bu üstü kırmızı
    "ctr_dusuk":        0.8,  # Frequency yüksekken CTR bu altındaysa yorgun
    "hook_rate_dusuk": 20.0,  # İlk 3 saniye izleme oranı < %20 = kreatifsiz
    "video_tamamlama":  15.0, # ThruPlay oranı < %15 = video ilgi çekmiyor
}


# ── Veri Yapıları ─────────────────────────────────────────────────────────────

@dataclass
class Anomali:
    kampanya_isim: str = ""
    metrik: str = ""            # "CTR", "CPC", "Harcama", "Gösterim", "Dönüşüm"
    onceki_deger: float = 0.0
    simdi_deger: float = 0.0
    degisim_yuzde: float = 0.0
    yön: str = ""               # "↓" veya "↑"
    siddet: str = ""            # "🔴 KRİTİK", "🟡 UYARI", "🔵 BİLGİ"
    aciklama: str = ""


@dataclass
class KreatifYorgunluk:
    kreatif_isim: str = ""
    kreatif_id: str = ""
    yorgunluk_skoru: int = 0    # 0-100 (100 = tamamen bitmiş)
    yorgunluk_etiketi: str = "" # "Taze", "Dikkat", "Yorgun", "Değiştir"
    sebepler: list = field(default_factory=list)
    oneri: str = ""
    frequency: float = 0.0
    ctr: float = 0.0
    hook_rate: float = 0.0


@dataclass
class ButceOneri:
    kaynak_kampanya: str = ""   # Buradan al
    kaynak_butce: float = 0.0
    kaynak_skor: int = 0
    hedef_kampanya: str = ""    # Buraya ver
    hedef_butce: float = 0.0
    hedef_skor: int = 0
    oneri_miktar: float = 0.0   # Taşınacak günlük bütçe (₺)
    beklenen_kazan: str = ""    # Ne kazanılır


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _degisim(onceki: float, simdi: float) -> float:
    if onceki == 0:
        return 0.0
    return ((simdi - onceki) / onceki) * 100


def _siddet(yuzde: float) -> str:
    abs_y = abs(yuzde)
    if abs_y >= 50:
        return "🔴 KRİTİK"
    if abs_y >= 30:
        return "🟡 UYARI"
    return "🔵 BİLGİ"


# ── 1. ANOMALİ TESPİTİ ────────────────────────────────────────────────────────

def anomali_tespit_et(
    simdi_kampanyalar: list,
    onceki_kampanyalar: list,
) -> list[Anomali]:
    """
    İki dönem arasında metrik değişikliklerini karşılaştırır.

    simdi_kampanyalar  : meta_api.kampanyalari_cek(tarih_araligi) çıktısı
    onceki_kampanyalar : meta_api.kampanyalari_cek(onceki_tarih) çıktısı
    """
    anomaliler = []

    # ID bazında eşleştir
    onceki_map = {}
    for k in onceki_kampanyalar:
        kid = k.get("id", "")
        ig  = k.get("insights", {})
        if isinstance(ig, dict) and "data" in ig:
            ig = ig["data"][0] if ig["data"] else {}
        onceki_map[kid] = ig

    for k in simdi_kampanyalar:
        kid  = k.get("id", "")
        isim = k.get("name", kid[:40])
        ig   = k.get("insights", {})
        if isinstance(ig, dict) and "data" in ig:
            ig = ig["data"][0] if ig["data"] else {}

        if kid not in onceki_map:
            continue

        oig = onceki_map[kid]

        def _f(d, key):
            try: return float(d.get(key) or 0)
            except: return 0.0

        def _don(d):
            tipler = {"purchase","lead","complete_registration"}
            t = 0.0
            for a in (d.get("actions") or []):
                if a.get("action_type") in tipler:
                    try: t += float(a.get("value", 0) or 0)
                    except: pass
            return t

        kontroller = [
            ("CTR",       _f(ig,"ctr"),         _f(oig,"ctr"),       True,  "ctr_dusus"),
            ("CPC (TBM)", _f(ig,"cpc"),         _f(oig,"cpc"),       False, "cpc_artis"),
            ("Harcama",   _f(ig,"spend"),       _f(oig,"spend"),     False, "harcama_artis"),
            ("Gösterim",  _f(ig,"impressions"), _f(oig,"impressions"), True, "gosterim_dusus"),
            ("Dönüşüm",   _don(ig),             _don(oig),           True,  "donusum_dusus"),
        ]

        for metrik_adi, simdi_v, onceki_v, dusus_kotu, esik_adi in kontroller:
            if onceki_v == 0 or simdi_v == 0:
                continue

            degisim = _degisim(onceki_v, simdi_v)
            esik    = ANOMALI_ESIKLER.get(esik_adi, -30)

            # Kötü yön: dusus_kotu=True ise düşüş kötü, False ise artış kötü
            tetiklendi = (dusus_kotu and degisim <= esik) or \
                         (not dusus_kotu and degisim >= abs(esik))

            if not tetiklendi:
                continue

            yon = "↓" if degisim < 0 else "↑"
            siddet = _siddet(degisim)
            aciklama = (
                f"{metrik_adi} önceki döneme göre "
                f"{'düştü' if degisim < 0 else 'arttı'}: "
                f"{onceki_v:.2f} → {simdi_v:.2f} ({degisim:+.0f}%)"
            )

            anomaliler.append(Anomali(
                kampanya_isim=isim,
                metrik=metrik_adi,
                onceki_deger=onceki_v,
                simdi_deger=simdi_v,
                degisim_yuzde=degisim,
                yön=yon,
                siddet=siddet,
                aciklama=aciklama,
            ))

    # Kritikleri öne al
    anomaliler.sort(key=lambda x: abs(x.degisim_yuzde), reverse=True)
    return anomaliler


# ── 2. KREATİF YORGUNLUK ─────────────────────────────────────────────────────

def kreatif_yorgunluk_hesapla(creativeler: list) -> list[KreatifYorgunluk]:
    """
    derinlemesine.creative_analiz_et() çıktısındaki CreativeSonuc listesini alır.
    Her kreatif için 0-100 yorgunluk skoru üretir.
    """
    sonuclar = []

    for c in creativeler:
        sebepler = []
        skor = 0

        frequency  = getattr(c, "frequency", 0.0)
        ctr        = getattr(c, "ctr", 0.0)
        hook_rate  = getattr(c, "hook_rate", 0.0)
        video_izlenme = getattr(c, "video_izlenme", 0.0)
        harcama    = getattr(c, "harcama", 0.0)

        # Frekans puanı (40 puan)
        if frequency >= YORGUNLUK_ESIKLER["frequency_kritik"]:
            skor += 40
            sebepler.append(f"Frekans kritik seviyede: {frequency:.1f}x (kişi başı {frequency:.0f} kez gördü)")
        elif frequency >= YORGUNLUK_ESIKLER["frequency_uyari"]:
            skor += 20
            sebepler.append(f"Frekans yüksek: {frequency:.1f}x — yakında yorgunluk başlar")

        # CTR düşüklüğü (30 puan) — sadece yeterli harcama varsa değerlendir
        if harcama > 50 and ctr < YORGUNLUK_ESIKLER["ctr_dusuk"]:
            skor += 30
            sebepler.append(f"CTR çok düşük: %{ctr:.2f} — izleyici reklama tepki vermiyor")
        elif harcama > 50 and ctr < 1.0:
            skor += 15
            sebepler.append(f"CTR zayıf: %{ctr:.2f}")

        # Hook Rate (video için 20 puan)
        if hook_rate > 0 and hook_rate < YORGUNLUK_ESIKLER["hook_rate_dusuk"]:
            skor += 20
            sebepler.append(f"İlk 3 saniye izlenme oranı düşük: %{hook_rate:.0f} (hedef %20+)")

        # ThruPlay (video için 10 puan)
        if video_izlenme > 0 and video_izlenme < YORGUNLUK_ESIKLER["video_tamamlama"]:
            skor += 10
            sebepler.append(f"Video tamamlanma oranı düşük: %{video_izlenme:.0f}")

        # Etiket
        if skor >= 70:
            etiket = "🔴 Değiştir"
            oneri  = "Bu kreatifi yeni bir görselle/mesajla değiştir. Benzer hedef kitleye göster."
        elif skor >= 40:
            etiket = "🟡 Yorgun"
            oneri  = "Kreatifi değiştir veya hedef kitleyi yenile (Lookalike audi.). Şu an bütçeyi düşür."
        elif skor >= 20:
            etiket = "🟠 Dikkat"
            oneri  = "Bir sonraki dönem takip et. Şimdilik devam et ama alternatif hazırla."
        else:
            etiket = "🟢 Taze"
            oneri  = "İyi performans devam ediyor."

        isim = getattr(c, "isim", "")
        kid  = getattr(c, "id", "")

        sonuclar.append(KreatifYorgunluk(
            kreatif_isim=isim,
            kreatif_id=kid,
            yorgunluk_skoru=min(100, skor),
            yorgunluk_etiketi=etiket,
            sebepler=sebepler,
            oneri=oneri,
            frequency=frequency,
            ctr=ctr,
            hook_rate=hook_rate,
        ))

    # En yorgundan en tazee
    sonuclar.sort(key=lambda x: x.yorgunluk_skoru, reverse=True)
    return sonuclar


# ── 3. BÜTÇE YENİDEN DAĞILIM ÖNERİSİ ────────────────────────────────────────

def butce_yeniden_dagit(kampanya_kpiler: list, min_harcama: float = 100.0) -> list[ButceOneri]:
    """
    Düşük performanslı kampanyalardan yüksek performanslılara bütçe taşı.

    min_harcama : Bu dönem en az bu kadar harcayan kampanyaları değerlendir.
    """
    # Yeterli veri olan kampanyaları filtrele
    aktif = [k for k in kampanya_kpiler if k.harcama >= min_harcama]

    if len(aktif) < 2:
        return []

    # Sağlık skoruna göre sırala
    dusuler = sorted([k for k in aktif if k.saglik_skoru < 50], key=lambda x: x.saglik_skoru)
    yuksekler = sorted([k for k in aktif if k.saglik_skoru >= 70], key=lambda x: x.saglik_skoru, reverse=True)

    oneriler = []

    for kaynak in dusuler[:3]:    # En kötü 3
        for hedef in yuksekler[:3]:  # En iyi 3
            # Taşınacak miktar: kaynağın günlük harcamasının %20'si
            gunluk_harcama = kaynak.harcama / 30   # 30 günlük veriden günlük tahmin
            tasinan = round(gunluk_harcama * 0.20, 0)

            if tasinan < 10:
                continue

            skor_farki = hedef.saglik_skoru - kaynak.saglik_skoru
            beklenen = (
                f"Günlük {tasinan:.0f} ₺ taşıyarak "
                f"skor {skor_farki:.0f} puan daha iyi olan "
                f"kampanyaya yatır. CTR artışı beklenir."
            )

            oneriler.append(ButceOneri(
                kaynak_kampanya=kaynak.isim,
                kaynak_butce=kaynak.harcama,
                kaynak_skor=kaynak.saglik_skoru,
                hedef_kampanya=hedef.isim,
                hedef_butce=hedef.harcama,
                hedef_skor=hedef.saglik_skoru,
                oneri_miktar=tasinan,
                beklenen_kazan=beklenen,
            ))

    # En büyük fırsatı öne al
    oneriler.sort(key=lambda x: x.hedef_skor - x.kaynak_skor, reverse=True)
    return oneriler[:5]  # En fazla 5 öneri


# ── RAPOR BÖLÜMLERİ ──────────────────────────────────────────────────────────

def anomali_bolumu_yaz(anomaliler: list[Anomali]) -> str:
    if not anomaliler:
        return ""

    kritikler = [a for a in anomaliler if "KRİTİK" in a.siddet]
    uyarilar  = [a for a in anomaliler if "UYARI"  in a.siddet]
    bilgiler  = [a for a in anomaliler if "BİLGİ"  in a.siddet]

    satirlar = [
        "## 🚨 Anomali Tespiti\n",
        "> Önceki döneme kıyasla anormal metrik değişimleri aşağıda listelendi.\n",
    ]

    if kritikler:
        satirlar.append("### 🔴 Kritik Anomaliler — Hemen Bak!\n")
        for a in kritikler:
            satirlar.append(
                f"**{a.kampanya_isim[:50]}** — {a.metrik} {a.yön}  \n"
                f"> {a.aciklama}\n"
            )

    if uyarilar:
        satirlar.append("### 🟡 Uyarılar\n")
        for a in uyarilar:
            satirlar.append(
                f"- **{a.metrik}** {a.yön} — {a.kampanya_isim[:45]}  \n"
                f"  {a.aciklama}\n"
            )

    if bilgiler:
        satirlar.append("### 🔵 Bilgi (İzle)\n")
        for a in bilgiler[:5]:
            satirlar.append(
                f"- {a.metrik} {a.yön} {a.degisim_yuzde:+.0f}% — {a.kampanya_isim[:40]}"
            )

    if not kritikler and not uyarilar:
        satirlar.append("> ✅ Bu dönemde anormal değişim tespit edilmedi.\n")

    satirlar.append("")
    return "\n".join(satirlar)


def yorgunluk_bolumu_yaz(sonuclar: list[KreatifYorgunluk]) -> str:
    if not sonuclar:
        return ""

    degistir = [s for s in sonuclar if "Değiştir" in s.yorgunluk_etiketi]
    yorgun   = [s for s in sonuclar if "Yorgun"   in s.yorgunluk_etiketi]
    taze     = [s for s in sonuclar if "Taze"     in s.yorgunluk_etiketi]

    satirlar = [
        "## 😴 Kreatif Yorgunluk Analizi\n",
        "> Yüksek frekans + düşük CTR kombinasyonu = yorulmuş kreatif.\n",
    ]

    if degistir:
        satirlar.append(f"### 🔴 Hemen Değiştir ({len(degistir)} kreatif)\n")
        for s in degistir:
            satirlar.append(f"**{s.kreatif_isim[:55]}**")
            satirlar.append(f"Yorgunluk Skoru: {s.yorgunluk_skoru}/100 | "
                            f"Frekans: {s.frequency:.1f}x | CTR: %{s.ctr:.2f}")
            for neden in s.sebepler:
                satirlar.append(f"- {neden}")
            satirlar.append(f"> 💡 {s.oneri}\n")

    if yorgun:
        satirlar.append(f"### 🟡 Yakında Değiştir ({len(yorgun)} kreatif)\n")
        for s in yorgun:
            satirlar.append(
                f"- **{s.kreatif_isim[:50]}** — Skor: {s.yorgunluk_skoru}/100 | "
                f"Frekans: {s.frequency:.1f}x | CTR: %{s.ctr:.2f}  \n"
                f"  {s.oneri}"
            )
        satirlar.append("")

    taze_sayi = len(taze)
    if taze_sayi > 0:
        satirlar.append(f"> ✅ {taze_sayi} kreatif iyi durumda, değişiklik gerekmiyor.\n")

    return "\n".join(satirlar)


def butce_oneri_bolumu_yaz(oneriler: list[ButceOneri]) -> str:
    if not oneriler:
        return ""

    satirlar = [
        "## 💡 Bütçe Yeniden Dağılım Önerileri\n",
        "> Düşük performanslı kampanyalardan yüksek performanslılara bütçe taşı.\n",
        "| Buradan Al | Skor | Buraya Ver | Skor | Günlük Taşı |",
        "|---|---|---|---|---|",
    ]

    for o in oneriler:
        satirlar.append(
            f"| {o.kaynak_kampanya[:30]} "
            f"| 🔴 {o.kaynak_skor}/100 "
            f"| {o.hedef_kampanya[:30]} "
            f"| 🟢 {o.hedef_skor}/100 "
            f"| {o.oneri_miktar:.0f} ₺ |"
        )

    satirlar.append("")
    satirlar.append("**En Önemli Öneri:**\n")
    if oneriler:
        o = oneriler[0]
        satirlar.append(
            f"> 📌 **{o.kaynak_kampanya[:50]}** kampanyasından günlük **{o.oneri_miktar:.0f} ₺** al,  \n"
            f"> **{o.hedef_kampanya[:50]}** kampanyasına ekle.  \n"
            f"> {o.beklenen_kazan}\n"
        )

    return "\n".join(satirlar)
