"""
Dünya Hayvan Sağlığı Örgütü (WOAH - Eski OIE) Bültenleri Toplayıcısı
Filtre: Sadece güncel, sığır/koyun/keçi salgınları ve One Health + Otomatik Türkçe Çeviri
"""

import logging
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS, HTTP_TIMEOUT, is_acceptable_news, get_priority
from translator import translate_to_turkish

logger = logging.getLogger("vet_bot.woah")


def fetch_woah_news() -> List[Dict[str, Any]]:
    """WOAH resmi salgın haberlerini çeker, süzer ve Türkçe'ye çevirir."""
    items: List[Dict[str, Any]] = []
    url = "https://www.woah.org/en/media/news/"

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"WOAH sayfasına ulaşılamadı ({resp.status_code}): {url}")
            return items

        soup = BeautifulSoup(resp.content, "html.parser")
        cards = soup.select(".c-card, article, .card")
        if not cards:
            cards = soup.select("h2 a, h3 a, a.c-card__link")

        for card in cards[:12]:
            link_tag = card if card.name == "a" else card.find("a", href=True)
            if not link_tag:
                continue

            link = link_tag.get("href", "").strip()
            title = link_tag.get_text(strip=True)

            if not title or len(title) < 6 or not link:
                continue

            full_link = link if link.startswith("http") else f"https://www.woah.org{link}"

            summary_tag = card.find("p") if card.name != "a" else None
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            # SIKI SÜZGEÇ: Taziye, kutlama, eski haberleri ele
            if not is_acceptable_news(title, summary, "WOAH", url=full_link):
                continue

            # Otomatik Türkçe Çeviri
            tr_title, was_en = translate_to_turkish(title)
            tr_summary, _ = translate_to_turkish(summary) if summary else ("", False)

            display_title = f"🌍 [WOAH - Türkçe] {tr_title}"
            if was_en and tr_title != title:
                display_title += f"\n<i>(Orijinal: {title[:75]}...)</i>"

            items.append({
                "title": display_title,
                "link": full_link,
                "source": "Dünya Hayvan Sağlığı Örgütü (WOAH)",
                "category": "WOAH",
                "priority": get_priority("WOAH"),
                "summary": tr_summary or "WOAH küresel hayvan sağlığı bülteni.",
                "published_at": ""
            })

    except Exception as e:
        logger.error(f"WOAH haberleri alınırken hata: {e}")

    return items
