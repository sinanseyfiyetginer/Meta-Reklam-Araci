"""
meta_api.py — Meta Graph API ile konuşan modül.

Görev: Meta sunucularına bağlan, reklam verilerini çek, ham JSON olarak döndür.
Bu modül sadece veri çeker — hesaplama yapmaz, karar vermez.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Meta Graph API'nin adresi
API_SURUMU = "v20.0"
API_TABANL = f"https://graph.facebook.com/{API_SURUMU}"


class MetaAPI:
    """Meta Ads API ile bağlantı kuran sınıf."""

    def __init__(self, hesap_id: str = None):
        self.token = os.getenv("META_ACCESS_TOKEN")
        self.hesap_id = hesap_id or os.getenv("META_AD_ACCOUNT_ID")

        if not self.token:
            raise ValueError("META_ACCESS_TOKEN .env dosyasında bulunamadı.")
        if not self.hesap_id:
            raise ValueError("META_AD_ACCOUNT_ID .env dosyasında bulunamadı.")

    # ── Yardımcı: API isteği gönder ───────────────────────────────────────────

    def _istek_gonder(self, url: str, parametreler: dict) -> dict:
        """
        Meta API'ye GET isteği gönderir.
        Hata varsa düzgün bir mesaj döndürür.
        """
        parametreler["access_token"] = self.token
        try:
            yanit = requests.get(url, params=parametreler, timeout=30)
            yanit.raise_for_status()
            return yanit.json()
        except requests.exceptions.HTTPError as e:
            hata_detay = yanit.json().get("error", {}).get("message", str(e))
            raise RuntimeError(f"Meta API Hatası: {hata_detay}")
        except requests.exceptions.ConnectionError:
            raise RuntimeError("İnternet bağlantısı yok veya Meta API erişilemiyor.")
        except requests.exceptions.Timeout:
            raise RuntimeError("Meta API zaman aşımı — tekrar dene.")

    # ── Sayfalama: Tüm sonuçları tek seferde çek ─────────────────────────────

    def _tumunu_cek(self, url: str, parametreler: dict) -> list:
        """
        Meta API sonuçları sayfalara böler (100'er 100'er).
        Bu fonksiyon tüm sayfaları toplayıp tek liste döndürür.
        """
        sonuclar = []
        veri = self._istek_gonder(url, parametreler)
        sonuclar.extend(veri.get("data", []))

        # Sonraki sayfa var mı?
        while "paging" in veri and "next" in veri["paging"]:
            veri = self._istek_gonder(veri["paging"]["next"], {})
            sonuclar.extend(veri.get("data", []))

        return sonuclar

    # ── Hesap Özeti ───────────────────────────────────────────────────────────

    def hesap_ozeti(self, tarih_araligi: str = "last_30d") -> dict:
        """
        Hesabın son X günlük genel özetini döndürür.
        tarih_araligi: 'today', 'yesterday', 'last_7d', 'last_30d', 'this_month'
        """
        url = f"{API_TABANL}/{self.hesap_id}/insights"
        parametreler = {
            "fields": "account_name,impressions,clicks,spend,reach,frequency,ctr,cpc,cpm,actions",
            "date_preset": tarih_araligi,
            "level": "account",
        }
        veri = self._istek_gonder(url, parametreler)
        return veri.get("data", [{}])[0] if veri.get("data") else {}

    # ── Kampanyalar ───────────────────────────────────────────────────────────

    def kampanyalari_cek(self, tarih_araligi: str = "last_30d") -> list:
        """
        Hesaptaki tüm kampanyaları ve performans verilerini döndürür.
        """
        url = f"{API_TABANL}/{self.hesap_id}/campaigns"
        parametreler = {
            "fields": (
                "id,name,status,objective,daily_budget,lifetime_budget,"
                "start_time,stop_time,"
                "insights.date_preset(" + tarih_araligi + ")"
                "{impressions,clicks,spend,reach,frequency,ctr,cpc,cpm,actions}"
            ),
            "limit": 100,
        }
        return self._tumunu_cek(url, parametreler)

    # ── Reklam Setleri ────────────────────────────────────────────────────────

    def reklam_setlerini_cek(self, kampanya_id: str, tarih_araligi: str = "last_30d") -> list:
        """
        Bir kampanyanın içindeki reklam setlerini ve performanslarını döndürür.
        Reklam Seti = kitleyi ve bütçeyi belirleyen katman.
        """
        url = f"{API_TABANL}/{kampanya_id}/adsets"
        parametreler = {
            "fields": (
                "id,name,status,daily_budget,lifetime_budget,targeting,"
                "insights.date_preset(" + tarih_araligi + ")"
                "{impressions,clicks,spend,reach,frequency,ctr,cpc,cpm}"
            ),
            "limit": 100,
        }
        return self._tumunu_cek(url, parametreler)

    # ── Reklamlar (Görseller / Metinler) ──────────────────────────────────────

    def reklamlari_cek(self, reklam_seti_id: str, tarih_araligi: str = "last_30d") -> list:
        """
        Bir reklam setinin içindeki tek tek reklamları döndürür.
        Reklam = kullanıcının gördüğü görsel/video/metin.
        """
        url = f"{API_TABANL}/{reklam_seti_id}/ads"
        parametreler = {
            "fields": (
                "id,name,status,creative{title,body,image_url},"
                "insights.date_preset(" + tarih_araligi + ")"
                "{impressions,clicks,spend,reach,frequency,ctr,cpc,cpm}"
            ),
            "limit": 100,
        }
        return self._tumunu_cek(url, parametreler)

    # ── Saatlik / Günlük Dağılım ──────────────────────────────────────────────

    def saatlik_dagilim(self, tarih_araligi: str = "last_7d") -> list:
        """
        Günün hangi saatlerinde reklamlar daha iyi performans gösteriyor?
        Bu veri bütçeyi doğru saatlere yönlendirmek için kullanılır.
        """
        url = f"{API_TABANL}/{self.hesap_id}/insights"
        parametreler = {
            "fields": "impressions,clicks,spend,ctr,cpc",
            "date_preset": tarih_araligi,
            "breakdowns": "hourly_stats_aggregated_by_advertiser_time_zone",
            "level": "account",
        }
        veri = self._istek_gonder(url, parametreler)
        return veri.get("data", [])

    # ── Hızlı Bağlantı Testi ─────────────────────────────────────────────────

    def baglanti_test(self) -> bool:
        """
        API bağlantısının çalışıp çalışmadığını test eder.
        True = bağlantı sağlıklı, False = sorun var.
        """
        url = f"{API_TABANL}/me"
        parametreler = {"fields": "id,name"}
        try:
            veri = self._istek_gonder(url, parametreler)
            print(f"✅ Bağlantı başarılı — Hesap: {veri.get('name')}")
            return True
        except Exception as e:
            print(f"❌ Bağlantı hatası: {e}")
            return False
