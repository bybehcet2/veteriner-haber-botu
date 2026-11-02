"""
Resmi Kurum Duyuru ve Genelgeleri (Tarım ve Orman Bakanlığı GKGM & TVHB)
Filtre: Sadece güncel (son 30 gün), somut sığır/koyun/keçi, karantina, aşılama ve mevzuat.
Taziye, tebrik, gün kutlaması ve protokol ziyaretleri kesinlikle elenir.
"""

import logging
from typing import List, Dict, Any
import requests
import urllib3
from bs4 import BeautifulSoup

from config import (
    DEFAULT_HEADERS,
    HTTP_TIMEOUT,
    is_acceptable_news,
    classify_news,
    get_priority
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("vet_bot.gov")


def fetch_gkgm_announcements() -> List[Dict[str, Any]]:
    """
    Tarım ve Orman Bakanlığı GKGM duyuru ve haberlerini çeker.
    Yalnızca hayvancılık, karantina, aşılama ve et/yem mevzuatı kabul edilir.
    """
    items: List[Dict[str, Any]] = []
    base_url = "https://www.tarimorman.gov.tr"
    urls_to_check = [
        {"url": f"{base_url}/GKGM/DuyuruArsivi", "type": "GKGM Duyuru"},
        {"url": f"{base_url}/GKGM/HaberArsivi", "type": "GKGM Haber"}
    ]

    for target in urls_to_check:
        try:
            resp = requests.get(
                target["url"],
                headers=DEFAULT_HEADERS,
                timeout=HTTP_TIMEOUT,
                verify=False
            )
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.content, "html.parser")

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/GKGM/Duyuru/" in href or "/GKGM/Haber/" in href:
                    title = a_tag.get_text(strip=True)
                    if not title or len(title) < 6:
                        continue

                    full_url = href if href.startswith("http") else f"{base_url}{href}"

                    # Süzgeç: Protokol, taziye, spor, alakasız gıda ve eski haberleri ele
                    if not is_acceptable_news(title, "", "GKGM", url=full_url):
                        continue

                    items.append({
                        "title": f"🇹🇷 {title}",
                        "link": full_url,
                        "source": f"T.C. Tarım ve Orman Bakanlığı ({target['type']})",
                        "category": "TR_GOV",
                        "priority": get_priority("TR_GOV"),
                        "summary": "Tarım ve Orman Bakanlığı resmi bildirimi.",
                        "published_at": ""
                    })

                    if len(items) >= 8:
                        break

        except Exception as e:
            logger.error(f"GKGM duyuruları hatası ({target['url']}): {e}")

    return items


def fetch_tvhb_announcements() -> List[Dict[str, Any]]:
    """
    Türk Veteriner Hekimleri Birliği (TVHB) duyurularını çeker.
    Taziye, vefat, Dünya X günü ve eski yıllara ait (2022-2025) tüm içerikler elenir.
    """
    items: List[Dict[str, Any]] = []
    url = "https://tvhb.org.tr/kategori/duyurular/"

    try:
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=HTTP_TIMEOUT,
            verify=False
        )
        if resp.status_code != 200:
            return items

        soup = BeautifulSoup(resp.content, "html.parser")

        for article in soup.select("article, .post, .entry-header")[:12]:
            title_tag = article.select_one("h2 a, h3 a, .entry-title a, a.post-title")
            if not title_tag:
                title_tag = article.find("a")

            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = title_tag.get("href", "").strip()

            if not title or not link or len(title) < 5:
                continue

            summary_tag = article.select_one(".entry-summary, .post-excerpt, p")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            # Süzgeç: Taziye, vefat, Dünya Günü, eski yıl (URL'de /2022/, /2023/) ELE
            if not is_acceptable_news(title, summary, "TVHB", url=link):
                continue

            items.append({
                "title": f"🏢 {title}",
                "link": link,
                "source": "Türk Veteriner Hekimleri Birliği (TVHB)",
                "category": "TR_GOV",
                "priority": get_priority("TR_GOV"),
                "summary": summary,
                "published_at": ""
            })

    except Exception as e:
        logger.error(f"TVHB duyuruları hatası: {e}")

    return items
