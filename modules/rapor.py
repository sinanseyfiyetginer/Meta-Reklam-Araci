"""
rapor.py — Türkçe Meta Reklam Performans Raporu üretici.

Görev: KPI ve Karar verilerini alır, Markdown formatında profesyonel rapor üretir.
       Günlük / Haftalık / 15 Günlük / Aylık periyotları destekler.
       Çıktı doğrudan müşteriye gönderilebilir düzeydedir.
"""

from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path


# ── Tarih Aralığı Etiketleri ─────────────────────────────────────────────────

TARIH_ETIKETLERI = {
    "today":        "Bugün",
    "yesterday":    "Dün",
    "last_7d":      "Son 7 Gün",
    "last_14d":     "Son 15 Gün",
    "last_30d":     "Son 30 Gün",
    "this_month":   "Bu Ay",
    "last_month":   "Geçen Ay",
    "last_90d":     "Son 90 Gün",
}

# ── Sağlık Skoru Çubuğu ───────────────────────────────────────────────────────

def _skor_cubugu(skor: int, uzunluk: int = 20) -> str:
    """0-100 arası skoru görsel çubuğa dönüştürür."""
    dolu = int((skor / 100) * uzunluk)
    bos = uzunluk - dolu
    return "█" * dolu + "░" * bos


def _skor_renk(skor: int) -> str:
    if skor >= 85: return "🟢"
    if skor >= 70: return "🟡"
    if skor >= 50: return "🟠"
    return "🔴"


# ── Para Formatı ──────────────────────────────────────────────────────────────

def _para(deger: float) -> str:
    return f"{deger:,.2f} ₺"


def _yuzde(deger: float) -> str:
    return f"%{deger:.2f}"


# ── Ana Rapor Üretici ─────────────────────────────────────────────────────────

def rapor_uret(
    hesap_ozeti_kpi,
    kampanya_kpiler: list,
    kararlar: list,
    musteri_adi: str = "Müşteri",
    tarih_araligi: str = "last_30d",
    ai_yorum: str = "",
    karsilastirma_bolumu: str = "",
    derinlemesine_bolumler: dict = None,
) -> str:
    """
    Tüm verileri birleştirerek Markdown rapor üretir.

    Parametreler:
    - hesap_ozeti_kpi : Hesap geneli KPI nesnesi
    - kampanya_kpiler : Kampanya KPI listesi
    - kararlar        : Kural motorunun ürettiği karar listesi
    - musteri_adi     : Raporda görünecek müşteri adı
    - tarih_araligi   : 'last_7d', 'last_30d' vb.
    - ai_yorum        : Claude'un Türkçe yorumu (opsiyonel)
    """
    simdi = datetime.now()
    tarih_str = simdi.strftime("%d.%m.%Y %H:%M")
    donem = TARIH_ETIKETLERI.get(tarih_araligi, tarih_araligi)

    parcalar = []

    # ── Başlık ────────────────────────────────────────────────────────────────
    parcalar.append(f"# 📊 Meta Reklam Performans Raporu\n")
    parcalar.append(f"**Müşteri:** {musteri_adi}  ")
    parcalar.append(f"**Dönem:** {donem}  ")
    parcalar.append(f"**Oluşturulma:** {tarih_str}  ")
    parcalar.append(f"**Hazırlayan:** Meta Reklam Aracı\n")
    parcalar.append("---\n")

    # ── Acil Aksiyonlar (varsa en üste) ───────────────────────────────────────
    acil = [k for k in kararlar if k.oncelik == 1]
    if acil:
        parcalar.append("## 🚨 HEMEN MÜDAHALE GEREKİYOR\n")
        parcalar.append("> Aşağıdaki kampanyalar acil aksiyon bekliyor. Diğerlerine geçmeden önce bunları çözün.\n")
        for k in acil:
            parcalar.append(f"**{k.tip} → {k.kampanya_isim[:60]}**  ")
            parcalar.append(f"{k.neden}\n")
        parcalar.append("---\n")

    # ── Hesap Genel Özeti ─────────────────────────────────────────────────────
    oz = hesap_ozeti_kpi
    parcalar.append("## 📈 Hesap Genel Özeti\n")

    skor_cubugu = _skor_cubugu(oz.saglik_skoru)
    skor_ikon   = _skor_renk(oz.saglik_skoru)
    parcalar.append(f"### Reklam Sağlık Skoru: {oz.saglik_skoru}/100 — {oz.saglik_etiketi}")
    parcalar.append(f"```\n{skor_cubugu} {oz.saglik_skoru}%\n```\n")

    # Özet metrikler tablosu
    parcalar.append("| Metrik | Değer | Türkiye Ortalaması |")
    parcalar.append("|---|---|---|")
    parcalar.append(f"| 💰 Toplam Harcama | {_para(oz.harcama)} | — |")
    parcalar.append(f"| 👁️ Gösterim | {oz.gosterim:,} | — |")
    parcalar.append(f"| 👆 Tıklama | {oz.tiklama:,} | — |")

    ctr_durum  = "✅" if oz.ctr  >= 1.5  else ("⚠️" if oz.ctr  >= 0.8  else "❌")
    cpc_durum  = "✅" if oz.cpc  <= 5.0  else ("⚠️" if oz.cpc  <= 10.0 else "❌")
    cpm_durum  = "✅" if oz.cpm  <= 40.0 else ("⚠️" if oz.cpm  <= 80.0 else "❌")
    freq_durum = "✅" if oz.frequency <= 2.0 else ("⚠️" if oz.frequency <= 3.5 else "❌")

    parcalar.append(f"| {ctr_durum} Tıklama Oranı (CTR) | {_yuzde(oz.ctr)} | %0.8 – 1.5 |")
    parcalar.append(f"| {cpc_durum} Tıklama Başına Maliyet | {_para(oz.cpc)} | 5 – 10 ₺ |")
    parcalar.append(f"| {cpm_durum} 1000 Gösterim Maliyeti | {_para(oz.cpm)} | 40 – 80 ₺ |")
    if oz.frequency > 0:
        parcalar.append(f"| {freq_durum} Frekans | {oz.frequency:.1f}x | 1 – 2x |")
    if oz.roas > 0:
        roas_durum = "✅" if oz.roas >= 3.0 else ("⚠️" if oz.roas >= 1.0 else "❌")
        parcalar.append(f"| {roas_durum} ROAS | {oz.roas:.2f}x | 3x+ |")
    parcalar.append("")

    # Hesap düzeyi uyarılar
    if oz.uyarilar:
        for uyari in oz.uyarilar:
            parcalar.append(f"> {uyari}\n")

    parcalar.append("---\n")

    # ── Kampanya Performans Tablosu ───────────────────────────────────────────
    veri_olan = [k for k in kampanya_kpiler if k.harcama > 0]
    veri_yok  = [k for k in kampanya_kpiler if k.harcama == 0]

    if veri_olan:
        parcalar.append(f"## 🎯 Kampanya Performansı ({len(veri_olan)} aktif)\n")
        parcalar.append("| Kampanya | Skor | Harcama | CTR | TBM | Frekans | Öneri |")
        parcalar.append("|---|---|---|---|---|---|---|")
        for k in veri_olan:
            isim_kisa = k.isim[:35] + "…" if len(k.isim) > 35 else k.isim
            skor_ikon = _skor_renk(k.saglik_skoru)
            freq_str  = f"{k.frequency:.1f}x" if k.frequency > 0 else "—"
            parcalar.append(
                f"| {isim_kisa} "
                f"| {skor_ikon} {k.saglik_skoru}/100 "
                f"| {_para(k.harcama)} "
                f"| {_yuzde(k.ctr)} "
                f"| {_para(k.cpc)} "
                f"| {freq_str} "
                f"| {k.oneri} |"
            )
        parcalar.append("")

    # ── Kahraman ve Sorunlu Kampanyalar ──────────────────────────────────────
    if veri_olan:
        en_iyi  = sorted(veri_olan, key=lambda x: x.saglik_skoru, reverse=True)[:3]
        en_kotu = sorted(veri_olan, key=lambda x: x.saglik_skoru)[:3]
        en_kotu = [k for k in en_kotu if k.saglik_skoru < 70]

        if en_iyi:
            parcalar.append("### 🏆 En İyi Performanslı Kampanyalar\n")
            for i, k in enumerate(en_iyi, 1):
                parcalar.append(
                    f"**{i}. {k.isim[:55]}**  \n"
                    f"Skor: {k.saglik_skoru}/100 | CTR: {_yuzde(k.ctr)} | "
                    f"TBM: {_para(k.cpc)} | Harcama: {_para(k.harcama)}\n"
                )

        if en_kotu:
            parcalar.append("### ⚠️ Dikkat Gerektiren Kampanyalar\n")
            for i, k in enumerate(en_kotu, 1):
                parcalar.append(
                    f"**{i}. {k.isim[:55]}**  \n"
                    f"Skor: {k.saglik_skoru}/100 | CTR: {_yuzde(k.ctr)} | "
                    f"TBM: {_para(k.cpc)}"
                )
                if k.uyarilar:
                    for uyari in k.uyarilar:
                        parcalar.append(f"> {uyari}")
                parcalar.append("")

    parcalar.append("---\n")

    # ── Kural Motoru Kararları ────────────────────────────────────────────────
    parcalar.append("## 🤖 Otomatik Kural Motoru Kararları\n")

    buyut_k  = [k for k in kararlar if k.tip == "BUYUT"]
    durdur_k = [k for k in kararlar if k.tip == "DURDUR"]
    uyari_k  = [k for k in kararlar if k.tip in ("UYAR", "KREATİF_YENİ", "KİTLE_DEĞİŞ")]
    tamam_k  = [k for k in kararlar if k.tip == "TAMAM"]

    if buyut_k:
        parcalar.append(f"### 🚀 Büyütülmesi Önerilen ({len(buyut_k)} kampanya)\n")
        for k in buyut_k:
            parcalar.append(f"- **{k.kampanya_isim[:55]}**  \n  {k.neden}\n")

    if durdur_k:
        parcalar.append(f"### 🔴 Durdurulması Önerilen ({len(durdur_k)} kampanya)\n")
        for k in durdur_k:
            parcalar.append(f"- **{k.kampanya_isim[:55]}**  \n  {k.neden}\n")

    if uyari_k:
        parcalar.append(f"### ⚠️ Aksiyon Bekleyen ({len(uyari_k)} kampanya)\n")
        for k in uyari_k:
            ikon = {"KREATİF_YENİ": "🎨", "KİTLE_DEĞİŞ": "👥"}.get(k.tip, "⚠️")
            parcalar.append(f"- {ikon} **{k.kampanya_isim[:55]}**  \n  {k.neden}\n")

    parcalar.append(f"> Toplam {len(tamam_k)} kampanya iyi durumda, müdahale gerekmiyor.\n")
    parcalar.append("---\n")

    # ── Dönem Karşılaştırması ─────────────────────────────────────────────────
    if karsilastirma_bolumu:
        parcalar.append(karsilastirma_bolumu)
        parcalar.append("---\n")

    # ── Derin Analiz Bölümleri ────────────────────────────────────────────────
    if derinlemesine_bolumler:
        # Grup 2: Bütçe pace
        if derinlemesine_bolumler.get("butce"):
            parcalar.append(derinlemesine_bolumler["butce"])
            parcalar.append("---\n")
        # Grup 3: Anomali tespiti (karşılaştırma sonrası)
        if derinlemesine_bolumler.get("anomali"):
            parcalar.append(derinlemesine_bolumler["anomali"])
            parcalar.append("---\n")
        # Grup 3: Bütçe yeniden dağılım önerisi
        if derinlemesine_bolumler.get("butce_oneri"):
            parcalar.append(derinlemesine_bolumler["butce_oneri"])
            parcalar.append("---\n")
        # Grup 1: Dönüşüm
        if derinlemesine_bolumler.get("donusum"):
            parcalar.append(derinlemesine_bolumler["donusum"])
            parcalar.append("---\n")
        # Grup 3: Kreatif yorgunluk
        if derinlemesine_bolumler.get("yorgunluk"):
            parcalar.append(derinlemesine_bolumler["yorgunluk"])
            parcalar.append("---\n")
        # Grup 2: Demografik
        if derinlemesine_bolumler.get("demografik"):
            parcalar.append(derinlemesine_bolumler["demografik"])
            parcalar.append("---\n")
        # Grup 2: Saatlik
        if derinlemesine_bolumler.get("saatlik"):
            parcalar.append(derinlemesine_bolumler["saatlik"])
            parcalar.append("---\n")
        # Grup 1: AdSet + Kreatif + Placement
        if derinlemesine_bolumler.get("adset"):
            parcalar.append(derinlemesine_bolumler["adset"])
            parcalar.append("---\n")
        if derinlemesine_bolumler.get("creative"):
            parcalar.append(derinlemesine_bolumler["creative"])
            parcalar.append("---\n")
        if derinlemesine_bolumler.get("placement"):
            parcalar.append(derinlemesine_bolumler["placement"])
            parcalar.append("---\n")

    # ── AI Yorumu ─────────────────────────────────────────────────────────────
    if ai_yorum:
        parcalar.append("## 🧠 AI Strateji Yorumu\n")
        parcalar.append(f"{ai_yorum}\n")
        parcalar.append("---\n")

    # ── Paused / Arşiv Kampanyalar ────────────────────────────────────────────
    if veri_yok:
        parcalar.append(f"## 📁 Duraklatılmış Kampanyalar ({len(veri_yok)} adet)\n")
        parcalar.append("> Bu dönemde harcama yapılmadı.\n")
        for k in veri_yok:
            durum_ikon = "🔴" if k.durum == "PAUSED" else "⚫"
            parcalar.append(f"- {durum_ikon} {k.isim[:60]}")
        parcalar.append("")

    # ── Footer ────────────────────────────────────────────────────────────────
    parcalar.append("---\n")
    parcalar.append(
        f"*Bu rapor **Sinan Seyfi Yetginer**'in Meta Reklam Aracı tarafından otomatik oluşturulmuştur — {tarih_str}*  \n"
        f"*Veriler Meta Graph API v20.0 üzerinden çekilmiştir. © {tarih_str[:4]} Sinan Seyfi Yetginer — Global Trading Services LLC*"
    )

    return "\n".join(parcalar)


# ── Dosyaya Kaydet ────────────────────────────────────────────────────────────

def rapor_kaydet(icerik: str, musteri_id: str, tarih_araligi: str) -> str:
    """
    Raporu raporlar/ klasörüne kaydeder.
    Dosya adı: raporlar/rapor_{musteri}_{donem}_{tarih}.md
    """
    os.makedirs("raporlar", exist_ok=True)
    simdi = datetime.now().strftime("%Y-%m-%d_%H-%M")
    donem = tarih_araligi.replace("_", "-")
    dosya_adi = f"raporlar/rapor_{musteri_id}_{donem}_{simdi}.md"

    Path(dosya_adi).write_text(icerik, encoding="utf-8")
    print(f"✅ Rapor kaydedildi: {dosya_adi}")
    return dosya_adi
