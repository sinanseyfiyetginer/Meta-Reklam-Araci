#!/usr/bin/env bash
# calistir.sh — Meta Reklam Aracı giriş noktası
#
# Kullanım örnekleri:
#   bash calistir.sh --musteri sinan --donem aylik --pdf
#   bash calistir.sh --musteri sinan --donem haftalik --pdf --optimize
#   bash calistir.sh --musteri sinan --donem gunluk
#   bash calistir.sh --listele

# Scriptin bulunduğu dizine git
cd "$(dirname "$0")" || exit 1

# Sanal ortam var mı kontrol et
if [ ! -f ".venv/bin/python3" ]; then
  echo ""
  echo "⚠️  İlk kurulum gerekiyor..."
  echo "Çalıştır: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  echo ""
  exit 1
fi

# Sanal ortamı aktif et ve main.py'yi çalıştır
source .venv/bin/activate
python3 main.py "$@"
