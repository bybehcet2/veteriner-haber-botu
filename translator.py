"""
Otomatik Çeviri Modülü (Google Translate Web API)
İngilizce makale, salgın bülteni ve sosyal medya gönderilerini akıcı Türkçe'ye çevirir.
"""

import logging
import urllib.parse
from typing import Tuple
import requests

logger = logging.getLogger("vet_bot.translator")


def translate_to_turkish(text: str, max_chars: int = 1500) -> Tuple[str, bool]:
    """
    Verilen metni Türkçe'ye çevirir.
    Döndürdüğü değer: (ceviri_metni, cevrildi_mi_boolean)
    Eğer metin zaten Türkçe ise cevrildi_mi=False döner.
    """
    if not text or not text.strip():
        return "", False

    cleaned_text = text.strip()[:max_chars]

    try:
        url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx&sl=auto&tl=tr&dt=t&q="
            + urllib.parse.quote(cleaned_text)
        )
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            detected_lang = data[2] if len(data) > 2 else "auto"

            # Parçaları birleştir
            translated = "".join([part[0] for part in data[0] if part and part[0]])

            # Eğer kaynak dil İngilizce veya başka yabancı bir dilse
            if detected_lang and detected_lang.lower() != "tr":
                return translated, True
            else:
                return text, False
    except Exception as e:
        logger.warning(f"Çeviri sırasında hata oluştu: {e}")

    # Hata durumunda orijinal metni döndür
    return text, False
