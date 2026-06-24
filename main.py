"""
main.py — Meta Reklam Aracı ana orkestratör.

Kullanım:
  python main.py --musteri sinan --donem haftalik --pdf
  python main.py --musteri sinan --donem aylik --pdf --optimize
  python main.py --listele
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv()


# ── Dönem → Meta API tarih_araligi eşlemesi ──────────────────────────────────

DONEM_MAP = {
    "bugun":    "today",
    "dun":      "yesterday",
    "gunluk":   "yesterday",
    "haftalik": "last_7d",
    "15gunluk": "last_14d",
    "aylik":    "last_30d",
    "ucaylik":  "last_90d",
    "bu_ay":    "this_month",
    "gecen_ay": "last_month",
}


# ── Müşteri Config Yükleme ────────────────────────────────────────────────────

def musteri_yukle(musteri_id: str) -> dict:
    """config/musteri_{id}.json dosyasını yükler."""
    dosya = Path(f"config/musteri_{musteri_id}.json")
    if not dosya.exists():
        print(f"❌ Müşteri bulunamadı: {musteri_id}")
        print(f"   Beklenen dosya: {dosya}")
        print(f"   Yeni müşteri eklemek için: config/musteri_ISIM.json oluştur")
        sys.exit(1)
    with open(dosya, encoding="utf-8") as f:
        return json.load(f)


def musterileri_listele() -> None:
    """Kayıtlı tüm müşterileri listeler."""
    dosyalar = sorted(Path("config").glob("musteri_*.json"))
    if not dosyalar:
        print("Henüz kayıtlı müşteri yok.")
        print("config/musteri_ISIM.json dosyası oluşturarak müşteri ekleyebilirsin.")
        return

    print(f"\n{'='*50}")
    print(f"  Kayıtlı Müşteriler ({len(dosyalar)} adet)")
    print(f"{'='*50}")
    for d in dosyalar:
        with open(d, encoding="utf-8") as f:
            m = json.load(f)
        print(f"  • {m.get('id'):15} → {m.get('ad')}  [{m.get('hesap_id')}]")
    print()


# ── AI Strateji Yorumu ────────────────────────────────────────────────────────

def ai_yorum_uret(rapor_ozeti: str, musteri_adi: str) -> str:
    """
    Claude'a raporu özetleyip Türkçe strateji yorumu ürettirir.
    Hata olursa boş string döner — yorum olmadan rapor yine üretilir.
    """
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        mesaj = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": (
                    f"Aşağıdaki Meta reklam performans raporu özeti için "
                    f"Türkçe, kısa ve profesyonel bir strateji yorumu yaz. "
                    f"Müşteri adı: {musteri_adi}. "
                    f"3-4 cümle ile: genel durumu değerlendir, "
                    f"en önemli 1-2 aksiyonu vurgula, "
                    f"bir sonraki dönem için tavsiye ver. "
                    f"Teknik jargon kullanma, sade Türkçe yaz.\n\n"
                    f"Rapor özeti:\n{rapor_ozeti[:1500]}"
                ),
            }],
        )
        return mesaj.content[0].text.strip()
    except Exception as e:
        print(f"  ⚠️ AI yorumu üretilemedi: {e}")
        return ""


# ── Ana Akış ──────────────────────────────────────────────────────────────────

def calistir(musteri_id: str, donem: str, pdf: bool, optimize: bool, uygula: bool) -> None:
    """Tüm modülleri sırayla çalıştırır."""

    from modules.meta_api    import MetaAPI
    from modules.analiz      import kampanyalari_analiz_et, hesap_ozeti_analiz
    from modules.kural_motoru import kural_degerlendir, kararlar_yazdir, karar_uygula
    from modules.rapor       import rapor_uret, rapor_kaydet
    from modules.pdf_olustur import markdown_to_pdf

    # Müşteri bilgilerini yükle
    musteri = musteri_yukle(musteri_id)
    musteri_adi   = musteri["ad"]
    hesap_id      = musteri["hesap_id"]
    tarih_araligi = DONEM_MAP.get(donem, "last_30d")

    print(f"\n{'='*55}")
    print(f"  📊 Meta Reklam Aracı")
    print(f"  Müşteri : {musteri_adi}")
    print(f"  Dönem   : {donem} ({tarih_araligi})")
    print(f"  Hesap   : {hesap_id}")
    print(f"{'='*55}\n")

    # 1. VERİ ÇEK
    print("① Veriler Meta'dan çekiliyor...")
    api = MetaAPI(hesap_id=hesap_id)

    if not api.baglanti_test():
        print("❌ Meta API bağlantısı kurulamadı. Token geçerli mi?")
        sys.exit(1)

    ozet      = api.hesap_ozeti(tarih_araligi)
    kampanyalar = api.kampanyalari_cek(tarih_araligi)
    print(f"   ✓ {len(kampanyalar)} kampanya çekildi\n")

    # 2. ANALİZ
    print("② KPI analizi yapılıyor...")
    ozet_kpi      = hesap_ozeti_analiz(ozet)
    kampanya_kpiler = kampanyalari_analiz_et(kampanyalar)

    veri_olan = [k for k in kampanya_kpiler if k.harcama > 0]
    print(f"   ✓ {len(veri_olan)} kampanyada harcama verisi bulundu")
    print(f"   ✓ Hesap sağlık skoru: {ozet_kpi.saglik_skoru}/100 — {ozet_kpi.saglik_etiketi}\n")

    # 3. KURAL MOTORU
    print("③ Kural motoru değerlendiriyor...")
    kararlar = kural_degerlendir(kampanya_kpiler, musteri_id)
    kararlar_yazdir(kararlar)

    # Otomatik uygulama (sadece --optimize --uygula ile)
    if optimize and uygula:
        print("\n⚡ Kararlar uygulanıyor (--uygula aktif)...")
        for k in kararlar:
            if k.tip in ("DURDUR", "BUYUT"):
                k = karar_uygula(k, uygula=True)
                durum = "✅ Uygulandı" if k.uygulandi else f"❌ Hata: {k.hata}"
                print(f"   {k.tip}: {k.kampanya_isim[:40]} → {durum}")
    elif optimize:
        print("\n💡 Optimizasyon önerileri hazır (uygulamak için --uygula ekle)")

    # 4. AI YORUMU
    print("\n④ AI strateji yorumu üretiliyor...")
    ozet_metin = (
        f"Harcama: {ozet_kpi.harcama:.2f} TRY, "
        f"CTR: %{ozet_kpi.ctr:.2f}, "
        f"TBM: {ozet_kpi.cpc:.2f} TRY, "
        f"Sağlık: {ozet_kpi.saglik_skoru}/100. "
        f"Toplam {len(kampanyalar)} kampanya, {len(veri_olan)} aktif."
    )
    if kararlar:
        acil = [k for k in kararlar if k.oncelik == 1]
        buyut = [k for k in kararlar if k.tip == "BUYUT"]
        if acil:
            ozet_metin += f" {len(acil)} kampanya acil müdahale istiyor."
        if buyut:
            ozet_metin += f" {len(buyut)} kampanya büyütmeye hazır."

    ai_yorum = ai_yorum_uret(ozet_metin, musteri_adi)
    if ai_yorum:
        print(f"   ✓ AI yorumu eklendi\n")
    else:
        print(f"   ⚠️ AI yorumu atlandı\n")

    # 5. RAPOR
    print("⑤ Rapor oluşturuluyor...")
    rapor_icerik = rapor_uret(
        hesap_ozeti_kpi=ozet_kpi,
        kampanya_kpiler=kampanya_kpiler,
        kararlar=kararlar,
        musteri_adi=musteri_adi,
        tarih_araligi=tarih_araligi,
        ai_yorum=ai_yorum,
    )
    md_dosya = rapor_kaydet(rapor_icerik, musteri_id, tarih_araligi)

    # 6. PDF
    if pdf:
        print("⑥ PDF oluşturuluyor...")
        pdf_dosya = md_dosya.replace(".md", ".pdf")
        markdown_to_pdf(md_dosya, pdf_dosya)

    # Özet
    print(f"\n{'='*55}")
    print(f"  ✅ Tamamlandı!")
    print(f"  📄 Rapor : {md_dosya}")
    if pdf:
        print(f"  📑 PDF   : {md_dosya.replace('.md', '.pdf')}")
    print(f"{'='*55}\n")


# ── Argüman Ayrıştırıcı ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Meta Reklam Aracı — Profesyonel reklam yönetim sistemi",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--musteri", "-m",
        help="Müşteri ID (config/musteri_ID.json)",
    )
    parser.add_argument(
        "--donem", "-d",
        default="aylik",
        choices=list(DONEM_MAP.keys()),
        help=(
            "Analiz dönemi:\n"
            "  bugun / dun / gunluk\n"
            "  haftalik / 15gunluk\n"
            "  aylik / ucaylik\n"
            "  bu_ay / gecen_ay"
        ),
    )
    parser.add_argument(
        "--pdf", "-p",
        action="store_true",
        help="PDF raporu da oluştur",
    )
    parser.add_argument(
        "--optimize", "-o",
        action="store_true",
        help="Kural motorunu çalıştır (öneri modunda)",
    )
    parser.add_argument(
        "--uygula",
        action="store_true",
        help="Kural kararlarını gerçekten uygula (DİKKAT!)",
    )
    parser.add_argument(
        "--listele", "-l",
        action="store_true",
        help="Kayıtlı müşterileri listele",
    )

    args = parser.parse_args()

    if args.listele:
        musterileri_listele()
        return

    if not args.musteri:
        parser.print_help()
        print("\n❌ --musteri parametresi gerekli.")
        print("   Örnek: python main.py --musteri sinan --donem aylik --pdf")
        sys.exit(1)

    calistir(
        musteri_id=args.musteri,
        donem=args.donem,
        pdf=args.pdf,
        optimize=args.optimize,
        uygula=args.uygula,
    )


if __name__ == "__main__":
    main()
