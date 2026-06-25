# Meta Reklam Aracı

Meta (Facebook/Instagram) reklam hesaplarını analiz eden, KPI hesaplayan, kural tabanlı optimizasyon önerileri üreten ve Türkçe PDF rapor çıkaran profesyonel bir araç. Hem kişisel hem çok müşterili (ajans) kullanıma uygundur.

---

## Özellikler

- **KPI Analizi** — CTR, CPC, ROAS, Sağlık Skoru (0-100)
- **Kural Motoru** — Otomatik durdur / büyüt / uyar kararları
- **Derin Analiz** — AdSet, Kreatif, Placement, Dönüşüm
- **Dönem Karşılaştırması** — Bu dönem vs önceki dönem trend analizi
- **Anomali Tespiti** — Ani metrik değişikliklerini yakala
- **Kreatif Yorgunluk** — Frequency + CTR + Hook Rate skoru
- **Bütçe Pace Takibi** — Ay ortasında bütçe bitecek mi?
- **Demografik Analiz** — Hangi yaş/cinsiyet daha verimli?
- **Saatlik Performans** — Günün hangi saati en iyi?
- **Bütçe Önerisi** — Kötü kampanyadan iyiye bütçe kaydır
- **AI Yorumu** — Claude ile Türkçe strateji yorumu
- **PDF Rapor** — Profesyonel, paylaşılabilir PDF çıktısı
- **Otomatik Gönderim** — E-posta ve WhatsApp ile müşteriye ilet

---

## Kurulum

### 1. Gereksinimleri Yükle

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. `.env` Dosyasını Oluştur

`.env.example` dosyasını kopyala, gerçek değerleri yaz:

```bash
cp .env.example .env
```

```env
META_ACCESS_TOKEN=EAAV...         # Meta Graph API token (60 günde yenile)
META_AD_ACCOUNT_ID=act_123456789  # act_ ile başlar

ANTHROPIC_API_KEY=sk-ant-...      # Claude API anahtarı

# Opsiyonel — e-posta gönderimi için
GMAIL_EMAIL=sen@gmail.com
GMAIL_APP_SIFRE=xxxx xxxx xxxx xxxx

# Opsiyonel — WhatsApp gönderimi için
TWILIO_SID=ACxxxxxxx
TWILIO_TOKEN=xxxxxxx
TWILIO_WHATSAPP_FROM=+14155238886
```

### 3. Müşteri Ekle

`config/musteri_ISIM.json` oluştur:

```json
{
  "id": "sinan",
  "ad": "Sinan Seyfi Yetginer",
  "hesap_id": "act_247840856",
  "para_birimi": "TRY",
  "saat_dilimi": "Europe/Istanbul",
  "rapor_dili": "tr",
  "aylik_butce": 5000,
  "email": "musteri@email.com",
  "telefon": "+905551234567"
}
```

---

## Kullanım

### Temel Rapor

```bash
python main.py --musteri sinan --donem aylik --pdf
```

### Tam Analiz (Tüm Özellikler)

```bash
python main.py --musteri sinan --donem aylik --pdf --derinlemesine --karsilastir
```

### Raporu Müşteriye Gönder

```bash
python main.py --musteri sinan --donem aylik --pdf --gonder
```

### Kayıtlı Müşterileri Listele

```bash
python main.py --listele
```

---

## Dönem Seçenekleri

| Parametre | Açıklama |
|-----------|----------|
| `bugun` | Bugün |
| `gunluk` | Dün |
| `haftalik` | Son 7 gün |
| `15gunluk` | Son 15 gün |
| `aylik` | Son 30 gün |
| `ucaylik` | Son 90 gün |
| `bu_ay` | Bu ay |
| `gecen_ay` | Geçen ay |

---

## Tüm Parametreler

| Parametre | Kısayol | Açıklama |
|-----------|---------|----------|
| `--musteri` | `-m` | Müşteri ID |
| `--donem` | `-d` | Analiz dönemi (varsayılan: aylik) |
| `--pdf` | `-p` | PDF rapor oluştur |
| `--optimize` | `-o` | Kural motorunu çalıştır |
| `--uygula` | — | Kararları gerçekten uygula (**dikkat!**) |
| `--derinlemesine` | `-D` | AdSet + Kreatif + Placement + Dönüşüm analizi |
| `--karsilastir` | `-k` | Önceki dönemle karşılaştır + anomali tespiti |
| `--gonder` | `-g` | Raporu e-posta ve WhatsApp ile gönder |
| `--listele` | `-l` | Kayıtlı müşterileri listele |

---

## Proje Yapısı

```
meta-reklam-araci/
├── main.py                  # Ana orkestratör
├── calistir.sh              # Kolay başlatma scripti
├── config/
│   └── musteri_*.json       # Müşteri konfigürasyonları
├── modules/
│   ├── meta_api.py          # Meta Graph API bağlantısı
│   ├── analiz.py            # KPI hesaplama ve sağlık skoru
│   ├── kural_motoru.py      # Otomatik karar motoru
│   ├── rapor.py             # Türkçe rapor üretici
│   ├── pdf_olustur.py       # PDF dönüştürücü
│   ├── derinlemesine.py     # AdSet / Kreatif / Placement / Dönüşüm
│   ├── karsilastir.py       # Dönem karşılaştırması
│   ├── anomali_kreatif.py   # Anomali tespiti + kreatif yorgunluk
│   ├── butce_ve_zaman.py    # Bütçe pace + demografik + saatlik
│   └── gonder.py            # E-posta ve WhatsApp gönderimi
└── raporlar/                # Üretilen MD ve PDF raporlar
```

---

## Meta API Token Yenileme

Token yaklaşık **60 günde bir** süresi dolar. Süresi dolduğunda:

1. [Meta for Developers](https://developers.facebook.com) → Graph API Explorer
2. Hesabını seç → `ads_read` iznini ver → Token oluştur
3. `.env` dosyasındaki `META_ACCESS_TOKEN` satırını güncelle

---

## Gereksinimler

- Python 3.9+
- Meta Business hesabı ve `ads_read` izinli token
- Anthropic API anahtarı (AI yorum için)
- Gmail uygulama şifresi (e-posta gönderimi için, opsiyonel)
- Twilio hesabı (WhatsApp gönderimi için, opsiyonel)
