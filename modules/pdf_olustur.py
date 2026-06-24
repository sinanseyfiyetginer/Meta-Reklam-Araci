"""
pdf_olustur.py — Markdown raporunu profesyonel PDF'e dönüştürür.

Görev: rapor.py'nin ürettiği Markdown dosyasını alır,
       stillenmiş HTML'e çevirir, Playwright ile PDF basar.
       Tasarım müşteriye gönderilebilir düzeydedir.
"""

from __future__ import annotations
import html
import re
from pathlib import Path


# ── Markdown → HTML Dönüştürücü ──────────────────────────────────────────────

def _inline(text: str) -> str:
    """Satır içi Markdown öğelerini HTML'e çevirir."""
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    return text


def _ikon_sinif(satir: str) -> str:
    """Durum ikonlarına CSS sınıfı ekler."""
    satir = satir.replace('✅', '<span class="ok">✅</span>')
    satir = satir.replace('⚠️', '<span class="warn">⚠️</span>')
    satir = satir.replace('❌', '<span class="err">❌</span>')
    satir = satir.replace('🚨', '<span class="err">🚨</span>')
    satir = satir.replace('🟢', '<span class="ok">🟢</span>')
    satir = satir.replace('🟡', '<span class="warn">🟡</span>')
    satir = satir.replace('🟠', '<span class="warn">🟠</span>')
    satir = satir.replace('🔴', '<span class="err">🔴</span>')
    satir = satir.replace('🚀', '<span class="buyut">🚀</span>')
    return satir


def _tablo_satiri(satir: str, baslik: bool = False) -> str:
    hucreler = [h.strip() for h in satir.strip().strip('|').split('|')]
    etiket = 'th' if baslik else 'td'
    ic = ''.join(
        f'<{etiket}>{_ikon_sinif(_inline(h))}</{etiket}>'
        for h in hucreler
    )
    return f'<tr>{ic}</tr>'


def markdown_to_html(md: str) -> str:
    """Markdown metnini HTML'e dönüştürür."""
    satirlar = md.splitlines()
    parcalar: list[str] = []
    i = 0
    liste_acik = False
    blockquote_acik = False

    def liste_kapat():
        nonlocal liste_acik
        if liste_acik:
            parcalar.append('</ul>')
            liste_acik = False

    def blockquote_kapat():
        nonlocal blockquote_acik
        if blockquote_acik:
            parcalar.append('</blockquote>')
            blockquote_acik = False

    while i < len(satirlar):
        satir = satirlar[i]

        # Kod bloğu
        if satir.strip().startswith('```'):
            liste_kapat(); blockquote_kapat()
            dil = satir.strip()[3:].strip()
            sinif = f' class="language-{dil}"' if dil else ''
            satirlar_kod = []
            i += 1
            while i < len(satirlar) and not satirlar[i].strip().startswith('```'):
                satirlar_kod.append(html.escape(satirlar[i]))
                i += 1
            parcalar.append(
                f'<pre><code{sinif}>' + '\n'.join(satirlar_kod) + '</code></pre>'
            )
            i += 1
            continue

        # Yatay çizgi
        if re.match(r'^-{3,}$', satir.strip()):
            liste_kapat(); blockquote_kapat()
            parcalar.append('<hr>')
            i += 1
            continue

        # Başlıklar
        m = re.match(r'^(#{1,6})\s+(.*)', satir)
        if m:
            liste_kapat(); blockquote_kapat()
            seviye = len(m.group(1))
            icerik = _ikon_sinif(_inline(m.group(2)))
            parcalar.append(f'<h{seviye}>{icerik}</h{seviye}>')
            i += 1
            continue

        # Blockquote
        if satir.startswith('> '):
            liste_kapat()
            if not blockquote_acik:
                parcalar.append('<blockquote>')
                blockquote_acik = True
            parcalar.append(f'<p>{_inline(satir[2:])}</p>')
            i += 1
            continue

        # Madde listesi
        if re.match(r'^[-*]\s+', satir):
            blockquote_kapat()
            if not liste_acik:
                parcalar.append('<ul>')
                liste_acik = True
            icerik = _ikon_sinif(_inline(re.sub(r'^[-*]\s+', '', satir)))
            parcalar.append(f'<li>{icerik}</li>')
            i += 1
            continue

        # Tablo
        if '|' in satir and satir.strip().startswith('|'):
            liste_kapat(); blockquote_kapat()
            satirlar_tablo = [_tablo_satiri(satir, baslik=True)]
            i += 1
            if i < len(satirlar) and re.match(r'^\|[-| :]+\|$', satirlar[i].strip()):
                i += 1
            govde = []
            while i < len(satirlar) and '|' in satirlar[i] and satirlar[i].strip().startswith('|'):
                govde.append(_tablo_satiri(satirlar[i]))
                i += 1
            parcalar.append(
                '<table><thead>' + ''.join(satirlar_tablo) + '</thead>'
                + '<tbody>' + ''.join(govde) + '</tbody></table>'
            )
            continue

        # Boş satır
        if satir.strip() == '':
            liste_kapat(); blockquote_kapat()
            i += 1
            continue

        # Paragraf
        liste_kapat(); blockquote_kapat()
        parcalar.append(f'<p>{_ikon_sinif(_inline(satir))}</p>')
        i += 1

    liste_kapat(); blockquote_kapat()
    return '\n'.join(parcalar)


# ── HTML Şablonu — Reklam Raporu Tasarımı ─────────────────────────────────────

_SABLON = """\
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Meta Reklam Performans Raporu</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ font-size: 10.5pt; }}
  body {{
    font-family: "Helvetica Neue", Arial, "Noto Sans", sans-serif;
    color: #1c1c2e;
    background: #fff;
    line-height: 1.65;
  }}

  .sayfa {{
    max-width: 880px;
    margin: 0 auto;
    padding: 36px 44px 52px;
  }}

  /* ── Üst Bant (Marka Rengi) ── */
  .ust-bant {{
    background: linear-gradient(135deg, #1877f2 0%, #0a5dc7 100%);
    color: #fff;
    padding: 22px 28px 18px;
    border-radius: 10px 10px 0 0;
    margin-bottom: 0;
  }}
  .ust-bant h1 {{
    font-size: 17pt;
    font-weight: 700;
    color: #fff;
    border: none;
    padding: 0;
    margin: 0 0 6px;
  }}
  .ust-bant .meta-bilgi {{
    font-size: 9pt;
    opacity: 0.88;
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
  }}
  .ust-bant .meta-bilgi span {{ display: flex; align-items: center; gap: 4px; }}

  /* ── Başlıklar ── */
  h1 {{
    font-size: 18pt;
    font-weight: 700;
    color: #1c1c2e;
    border-bottom: 3px solid #1877f2;
    padding-bottom: 8px;
    margin: 0 0 16px;
    page-break-after: avoid;
  }}
  h2 {{
    font-size: 13pt;
    font-weight: 700;
    color: #fff;
    background: linear-gradient(90deg, #1877f2, #0a5dc7);
    padding: 8px 16px;
    margin: 26px 0 14px;
    border-radius: 6px;
    page-break-after: avoid;
  }}
  h3 {{
    font-size: 11pt;
    font-weight: 600;
    color: #1c1c2e;
    border-left: 3px solid #1877f2;
    padding-left: 10px;
    margin: 18px 0 10px;
    page-break-after: avoid;
  }}
  h4, h5, h6 {{
    font-size: 10pt;
    font-weight: 600;
    color: #444;
    margin: 12px 0 6px;
  }}

  /* ── Meta Bilgiler Bloğu ── */
  .meta-blok {{
    background: #f0f6ff;
    border-radius: 0 0 8px 8px;
    padding: 12px 18px;
    margin: 0 0 22px;
    font-size: 9.5pt;
    color: #444;
    border: 1px solid #d0e4ff;
    border-top: none;
  }}
  .meta-blok p {{ margin: 2px 0; }}
  .meta-blok strong {{ color: #1877f2; }}

  /* ── Acil Kutusu ── */
  .acil-kutu {{
    background: #fff5f5;
    border: 2px solid #fca5a5;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 0 0 20px;
  }}
  .acil-kutu h2 {{
    background: linear-gradient(90deg, #dc2626, #b91c1c);
    margin-top: 0;
  }}

  /* ── Paragraf & Liste ── */
  p {{ margin: 5px 0; }}
  ul {{ margin: 6px 0 10px 22px; }}
  li {{ margin: 4px 0; }}

  /* ── Yatay Çizgi ── */
  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 20px 0;
  }}

  /* ── Blockquote ── */
  blockquote {{
    background: #f8faff;
    border-left: 4px solid #93c5fd;
    padding: 10px 16px;
    margin: 10px 0 14px;
    border-radius: 0 6px 6px 0;
    color: #334155;
    font-size: 9.5pt;
  }}
  blockquote p {{ margin: 2px 0; }}

  /* ── Kod ── */
  code {{
    font-family: "SF Mono", "Consolas", monospace;
    font-size: 8.5pt;
    background: #eff6ff;
    color: #1d4ed8;
    padding: 2px 5px;
    border-radius: 3px;
  }}
  pre {{
    background: #0f172a;
    color: #7dd3fc;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 8px 0 14px;
    font-size: 11pt;
    font-weight: 700;
    letter-spacing: 1px;
    page-break-inside: avoid;
  }}
  pre code {{
    background: transparent;
    color: inherit;
    padding: 0;
    font-size: inherit;
  }}

  /* ── Tablolar ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    margin: 10px 0 18px;
    page-break-inside: auto;
    border-radius: 8px;
    overflow: hidden;
  }}
  thead {{ background: linear-gradient(90deg, #1877f2, #0a5dc7); color: #fff; }}
  thead th {{
    padding: 9px 11px;
    text-align: left;
    font-weight: 600;
    font-size: 8.5pt;
    letter-spacing: 0.3px;
  }}
  tbody tr:nth-child(even) {{ background: #f0f6ff; }}
  tbody tr:hover {{ background: #dbeafe; }}
  td {{
    padding: 7px 11px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
  }}

  /* ── Durum İkonları ── */
  .ok   {{ color: #16a34a; }}
  .warn {{ color: #d97706; }}
  .err  {{ color: #dc2626; }}
  .buyut {{ color: #7c3aed; }}

  /* ── Skor Çubuğu ── */
  .skor-blok {{
    font-family: "SF Mono", "Consolas", monospace;
    font-size: 11pt;
    font-weight: 700;
    background: #0f172a;
    color: #34d399;
    padding: 10px 18px;
    border-radius: 8px;
    margin: 6px 0 12px;
    display: inline-block;
    letter-spacing: 1px;
  }}

  /* ── Footer ── */
  .footer {{
    font-size: 7.5pt;
    color: #94a3b8;
    text-align: center;
    margin-top: 30px;
    padding-top: 12px;
    border-top: 1px solid #e2e8f0;
  }}

  /* ── Sayfa Sonu ── */
  h2, h3 {{ page-break-after: avoid; }}
  table, pre, blockquote {{ page-break-inside: avoid; }}

  @page {{
    size: A4;
    margin: 14mm 14mm 16mm;
  }}
  @media print {{
    body {{ background: #fff; }}
    .sayfa {{ padding: 0; }}
    pre {{ white-space: pre-wrap; word-break: break-word; }}
  }}
</style>
</head>
<body>
<div class="sayfa">
{icerik}
</div>
</body>
</html>
"""


# ── Sonradan İşlemler ─────────────────────────────────────────────────────────

def _meta_blogu_isle(html_icerik: str) -> str:
    """Başlıktan sonraki meta paragrafları meta-blok div'ine taşır."""
    eslesme = re.search(r'((?:<p>.*?</p>\s*)+?)(<hr>)', html_icerik, re.DOTALL)
    if not eslesme:
        return html_icerik
    meta_p = eslesme.group(1)
    rest = html_icerik[eslesme.start(2):]
    meta_div = f'<div class="meta-blok">\n{meta_p.strip()}\n</div>\n'
    return html_icerik[:eslesme.start()] + meta_div + rest


def _acil_kutusu_isle(html_icerik: str) -> str:
    """HEMEN MÜDAHALE bölümünü acil-kutu div'ine alır."""
    baslangic = re.search(r'<h2>.*?HEMEN MÜDAHALE.*?</h2>', html_icerik)
    if not baslangic:
        return html_icerik
    bitis = html_icerik.find('<hr>', baslangic.start())
    if bitis == -1:
        return html_icerik
    bolum = html_icerik[baslangic.start():bitis]
    sarili = f'<div class="acil-kutu">\n{bolum}\n</div>\n'
    return html_icerik[:baslangic.start()] + sarili + html_icerik[bitis:]


def _skor_cubugu_isle(html_icerik: str) -> str:
    """█░ içeren pre bloklarını özel skor-blok div'ine çevirir."""
    def replace(m: re.Match) -> str:
        icerik = m.group(1)
        if '█' in icerik or '░' in icerik:
            return f'<div class="skor-blok">{icerik}</div>'
        return m.group(0)
    return re.sub(r'<pre><code>(.*?)</code></pre>', replace, html_icerik, flags=re.DOTALL)


# ── Ana Fonksiyon ─────────────────────────────────────────────────────────────

def markdown_to_pdf(md_dosya: str | Path, pdf_dosya: str | Path) -> None:
    """
    Markdown dosyasını okur, stillenmiş PDF olarak kaydeder.
    Playwright'ın kurulu olduğu varsayılır.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("Playwright bulunamadı. '.venv/bin/pip install playwright' ile kur.") from e

    md_yolu  = Path(md_dosya)
    pdf_yolu = Path(pdf_dosya)

    md_metin = md_yolu.read_text(encoding='utf-8')

    govde_html = markdown_to_html(md_metin)
    govde_html = _meta_blogu_isle(govde_html)
    govde_html = _acil_kutusu_isle(govde_html)
    govde_html = _skor_cubugu_isle(govde_html)

    tam_html = _SABLON.format(icerik=govde_html)

    html_gecici = pdf_yolu.with_suffix('.html')
    html_gecici.write_text(tam_html, encoding='utf-8')

    try:
        with sync_playwright() as pw:
            tarayici = pw.chromium.launch()
            sayfa = tarayici.new_page()
            sayfa.goto(html_gecici.resolve().as_uri(), wait_until='domcontentloaded')
            sayfa.pdf(
                path=str(pdf_yolu),
                format='A4',
                print_background=True,
                margin={'top': '14mm', 'bottom': '16mm', 'left': '14mm', 'right': '14mm'},
            )
            tarayici.close()
    finally:
        html_gecici.unlink(missing_ok=True)

    print(f"✅ PDF kaydedildi: {pdf_yolu}")
