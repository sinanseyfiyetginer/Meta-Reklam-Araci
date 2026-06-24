# Meta Reklam Aracı — Claude Talimatları

## Bu Proje Ne Yapar
Meta (Facebook/Instagram) reklam hesaplarını analiz eder, KPI hesaplar,
kural tabanlı optimizasyon önerileri üretir ve Türkçe PDF rapor çıkarır.
Hem kişisel hem çok müşterili (ajans) kullanıma uygundur.

## Standart Kullanım Komutu
```bash
bash calistir.sh --musteri sinan --donem aylik --pdf
```

## Dönem Seçenekleri
gunluk · haftalik · 15gunluk · aylik · ucaylik · bu_ay · gecen_ay

## Yeni Müşteri Eklemek
config/musteri_ISIM.json dosyası oluştur. Şablonu kullan:
```json
{
  "id": "musteri_id",
  "ad": "Müşteri Adı",
  "hesap_id": "act_HESAP_ID",
  "para_birimi": "TRY",
  "saat_dilimi": "Europe/Istanbul",
  "rapor_dili": "tr",
  "notlar": ""
}
```

## Proje Yapısı
- modules/meta_api.py      → Meta API bağlantısı
- modules/analiz.py        → KPI hesaplama ve sağlık skoru
- modules/kural_motoru.py  → Otomatik karar motoru
- modules/rapor.py         → Türkçe rapor üretici
- modules/pdf_olustur.py   → PDF dönüştürücü
- config/musteri_*.json    → Müşteri konfigürasyonları
- raporlar/                → Üretilen raporlar

## Önemli Notlar
- .env dosyasında META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, ANTHROPIC_API_KEY var
- Token yaklaşık 60 günde bir yenilenmeli
- --uygula bayrağı gerçek değişiklik yapar, dikkatli kullan
- Sanal ortam: .venv/  (git'e gitmez)
