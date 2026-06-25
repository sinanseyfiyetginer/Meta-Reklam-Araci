"""
gonder.py — Otomatik rapor gönderimi (E-posta ve WhatsApp).

Görev:
  1. E-posta  → Gmail SMTP ile PDF eki gönder
  2. WhatsApp → Twilio REST API ile Türkçe özet mesaj gönder
  3. rapor_gonder() → her ikisini müşteri config'ine göre otomatik çağırır

Kurulum (tek seferlik):
  E-posta için:
    1. Gmail hesabına gir → Ayarlar → Güvenlik → 2 adımlı doğrulama aç
    2. "Uygulama şifreleri" → Meta Reklam Aracı → 16 haneli şifre al
    3. .env dosyasına ekle:
       GMAIL_EMAIL=sinanseyfiyetginer@gmail.com
       GMAIL_APP_SIFRE=xxxx xxxx xxxx xxxx

  WhatsApp için:
    1. twilio.com'a kaydol → ücretsiz deneme (15$ kredi)
    2. Console → Messaging → Sandbox for WhatsApp
    3. .env dosyasına ekle:
       TWILIO_SID=ACxxxxxx
       TWILIO_TOKEN=xxxxxx
       TWILIO_WHATSAPP_FROM=+14155238886
"""

from __future__ import annotations
import os
import smtplib
import ssl
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders
from pathlib              import Path
from datetime             import datetime


# ── Yardımcı ─────────────────────────────────────────────────────────────────

TARIH_ETIKETLERI = {
    "today": "Bugün", "yesterday": "Dün", "last_7d": "Son 7 Gün",
    "last_14d": "Son 15 Gün", "last_30d": "Son 30 Gün",
    "this_month": "Bu Ay",  "last_month": "Geçen Ay", "last_90d": "Son 90 Gün",
}


def _env(anahtar: str) -> str:
    deger = os.getenv(anahtar, "")
    return deger.strip()


# ── E-POSTA GÖNDERİCİ ────────────────────────────────────────────────────────

def email_gonder(
    pdf_dosya: str,
    alici_email: str,
    musteri_adi: str,
    tarih_araligi: str = "last_30d",
    ozet_metin: str = "",
) -> bool:
    """
    PDF raporu Gmail SMTP üzerinden e-posta olarak gönderir.

    Gerekli .env değişkenleri:
      GMAIL_EMAIL      → gönderici Gmail adresi
      GMAIL_APP_SIFRE  → Gmail uygulama şifresi (normal şifre değil!)

    Döndürür: True = başarılı, False = hata
    """
    gmail  = _env("GMAIL_EMAIL")
    sifre  = _env("GMAIL_APP_SIFRE")

    if not gmail or not sifre:
        print("  ⚠️ E-posta gönderilemedi: .env'de GMAIL_EMAIL veya GMAIL_APP_SIFRE yok.")
        print("     Rehber için: 'email kurulum' yaz.")
        return False

    if not alici_email:
        print("  ⚠️ E-posta gönderilemedi: müşteri config'inde 'email' alanı yok.")
        return False

    donem_tr = TARIH_ETIKETLERI.get(tarih_araligi, tarih_araligi)
    tarih_str = datetime.now().strftime("%d.%m.%Y")

    konu = f"📊 {donem_tr} Meta Reklam Raporu — {musteri_adi} ({tarih_str})"

    # E-posta gövdesi (HTML)
    govde_html = f"""
    <html><body style="font-family: Arial, sans-serif; color: #333;">
    <div style="max-width:600px; margin:0 auto; padding:20px;">

      <div style="background: linear-gradient(135deg, #1877f2, #0a5dc7);
                  padding: 24px; border-radius: 12px; text-align:center; color:white;">
        <h1 style="margin:0; font-size:22px;">📊 Meta Reklam Raporu</h1>
        <p style="margin:8px 0 0; opacity:0.9;">{donem_tr} | {tarih_str}</p>
      </div>

      <div style="padding: 24px 0;">
        <p>Merhaba <strong>{musteri_adi}</strong>,</p>
        <p>{donem_tr} dönemi Meta reklam performans raporunuz hazır.
           PDF rapor bu e-postaya eklenmiştir.</p>

        {f'<div style="background:#f8f9fa; padding:16px; border-radius:8px; margin:16px 0;"><p style="margin:0; font-size:14px; color:#555;">{ozet_metin}</p></div>' if ozet_metin else ''}

        <p style="margin-top:24px; font-size:13px; color:#888;">
          Bu rapor Meta Reklam Aracı tarafından otomatik oluşturulmuştur.
        </p>
      </div>

    </div>
    </body></html>
    """

    # Mesaj oluştur
    msg = MIMEMultipart("alternative")
    msg["Subject"] = konu
    msg["From"]    = gmail
    msg["To"]      = alici_email

    msg.attach(MIMEText(govde_html, "html", "utf-8"))

    # PDF ek
    pdf_path = Path(pdf_dosya)
    if pdf_path.exists():
        with open(pdf_path, "rb") as f:
            ek = MIMEBase("application", "octet-stream")
            ek.set_payload(f.read())
        encoders.encode_base64(ek)
        ek.add_header(
            "Content-Disposition",
            f'attachment; filename="{pdf_path.name}"',
        )
        msg.attach(ek)
    else:
        print(f"  ⚠️ PDF dosyası bulunamadı: {pdf_dosya} — sadece e-posta gövdesi gönderilecek.")

    # Gönder
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail, sifre)
            server.sendmail(gmail, alici_email, msg.as_bytes())
        print(f"  ✅ E-posta gönderildi → {alici_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("  ❌ Gmail kimlik doğrulama hatası!")
        print("     Gmail şifresi değil, Uygulama Şifresi gerekli.")
        print("     Gmail → Güvenlik → Uygulama şifreleri → Yeni şifre oluştur")
        return False
    except Exception as e:
        print(f"  ❌ E-posta gönderilemedi: {e}")
        return False


# ── WHATSAPP GÖNDERİCİ ───────────────────────────────────────────────────────

def whatsapp_gonder(
    alici_numara: str,
    mesaj: str,
) -> bool:
    """
    Twilio Sandbox üzerinden WhatsApp mesajı gönderir.
    Not: PDF gönderimi için dosyanın internet üzerinde erişilebilir olması gerekir.
         Bu versiyon metin özeti gönderir.

    Gerekli .env değişkenleri:
      TWILIO_SID             → Twilio Account SID
      TWILIO_TOKEN           → Twilio Auth Token
      TWILIO_WHATSAPP_FROM   → Twilio WhatsApp numarası (örn. +14155238886)
    """
    sid    = _env("TWILIO_SID")
    token  = _env("TWILIO_TOKEN")
    gonderen = _env("TWILIO_WHATSAPP_FROM")

    if not sid or not token or not gonderen:
        print("  ⚠️ WhatsApp gönderilemedi: .env'de TWILIO_SID, TWILIO_TOKEN "
              "veya TWILIO_WHATSAPP_FROM yok.")
        return False

    if not alici_numara:
        print("  ⚠️ WhatsApp gönderilemedi: müşteri config'inde 'telefon' alanı yok.")
        return False

    # Numara formatını düzelt
    if not alici_numara.startswith("+"):
        alici_numara = "+90" + alici_numara.lstrip("0")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {
        "From": f"whatsapp:{gonderen}",
        "To":   f"whatsapp:{alici_numara}",
        "Body": mesaj,
    }

    try:
        r = requests.post(url, data=data, auth=(sid, token), timeout=10)
        if r.status_code in (200, 201):
            print(f"  ✅ WhatsApp gönderildi → {alici_numara}")
            return True
        else:
            hata = r.json().get("message", r.text[:100])
            print(f"  ❌ WhatsApp gönderilemedi: {hata}")
            if "not joined" in hata.lower() or "sandbox" in hata.lower():
                print("     Müşterinin önce Sandbox'a katılması gerekiyor.")
                print(f"     Müşteri şu WhatsApp'a mesaj atsın: {gonderen}")
                print("     Mesaj: join (Twilio Sandbox kodunuzu buraya yazın)")
            return False
    except Exception as e:
        print(f"  ❌ WhatsApp bağlantı hatası: {e}")
        return False


# ── ANA GÖNDERME FONKSİYONU ──────────────────────────────────────────────────

def rapor_gonder(
    pdf_dosya: str,
    musteri: dict,
    tarih_araligi: str,
    ozet_kpi=None,
    kararlar: list = None,
) -> dict:
    """
    Müşteri config'ine bakarak uygun kanallardan raporu gönderir.

    musteri : config/musteri_{id}.json içeriği
              'email' alanı varsa → e-posta gönderir
              'telefon' alanı varsa → WhatsApp gönderir

    Döndürür: {'email': True/False, 'whatsapp': True/False}
    """
    musteri_adi = musteri.get("ad", "Müşteri")
    email       = musteri.get("email", "")
    telefon     = musteri.get("telefon", "")
    donem_tr    = TARIH_ETIKETLERI.get(tarih_araligi, tarih_araligi)

    sonuc = {"email": False, "whatsapp": False}

    # Özet metin oluştur
    ozet_metin = ""
    if ozet_kpi:
        ozet_metin = (
            f"Dönem: {donem_tr} | "
            f"Harcama: {ozet_kpi.harcama:,.2f} ₺ | "
            f"CTR: %{ozet_kpi.ctr:.2f} | "
            f"TBM: {ozet_kpi.cpc:.2f} ₺ | "
            f"Sağlık Skoru: {ozet_kpi.saglik_skoru}/100"
        )

    # WhatsApp için kısa mesaj
    wa_mesaj = _whatsapp_mesaj_olustur(musteri_adi, donem_tr, ozet_kpi, kararlar or [])

    print("\n📤 Rapor gönderiliyor...")

    # E-posta
    if email:
        sonuc["email"] = email_gonder(
            pdf_dosya=pdf_dosya,
            alici_email=email,
            musteri_adi=musteri_adi,
            tarih_araligi=tarih_araligi,
            ozet_metin=ozet_metin,
        )
    else:
        print("  ℹ️ E-posta atlandı: müşteri config'inde 'email' alanı yok.")

    # WhatsApp
    if telefon:
        sonuc["whatsapp"] = whatsapp_gonder(
            alici_numara=telefon,
            mesaj=wa_mesaj,
        )
    else:
        print("  ℹ️ WhatsApp atlandı: müşteri config'inde 'telefon' alanı yok.")

    return sonuc


def _whatsapp_mesaj_olustur(
    musteri_adi: str,
    donem_tr: str,
    ozet_kpi,
    kararlar: list,
) -> str:
    """WhatsApp için kısa Türkçe özet mesaj üretir."""
    satirlar = [
        f"📊 *{donem_tr} Meta Reklam Raporu*",
        f"Merhaba {musteri_adi}!",
        "",
    ]

    if ozet_kpi:
        skor_ikon = (
            "🟢" if ozet_kpi.saglik_skoru >= 85 else
            "🟡" if ozet_kpi.saglik_skoru >= 70 else
            "🟠" if ozet_kpi.saglik_skoru >= 50 else "🔴"
        )
        satirlar += [
            f"{skor_ikon} Sağlık Skoru: *{ozet_kpi.saglik_skoru}/100*",
            f"💰 Harcama: *{ozet_kpi.harcama:,.0f} ₺*",
            f"👆 CTR: *%{ozet_kpi.ctr:.2f}*",
            f"💵 TBM: *{ozet_kpi.cpc:.2f} ₺*",
            "",
        ]

    # Kritik aksiyonlar
    if kararlar:
        acil = [k for k in kararlar if k.oncelik == 1]
        buyut = [k for k in kararlar if k.tip == "BUYUT"]
        if acil:
            satirlar.append(f"🚨 *{len(acil)} kampanya acil müdahale bekliyor*")
        if buyut:
            satirlar.append(f"🚀 *{len(buyut)} kampanya büyütmeye hazır*")
        satirlar.append("")

    satirlar += [
        "📄 Detaylı PDF rapor e-posta ile gönderildi.",
        "",
        "_Meta Reklam Aracı_",
    ]

    return "\n".join(satirlar)
