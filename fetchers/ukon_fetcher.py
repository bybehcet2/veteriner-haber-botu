"""
Ulusal Kırmızı Et Konseyi (UKON) Resmi Haftalık Fiyat Toplayıcısı
Özellik: Adana'nın bağlı olduğu Akdeniz Bölgesi fiyatlarını en başa vurgulayarak yerleştirir.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests
import urllib3
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS, HTTP_TIMEOUT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("vet_bot.ukon")

UKON_URL = "https://www.ukon.org.tr/fiyatlar"


def fetch_ukon_prices() -> List[Dict[str, Any]]:
    """UKON resmi haftalık kesim fiyatlarını çeker, Akdeniz (Adana) fiyatını vurgular."""
    items: List[Dict[str, Any]] = []

    try:
        resp = requests.get(
            UKON_URL,
            headers=DEFAULT_HEADERS,
            timeout=HTTP_TIMEOUT,
            verify=False
        )
        if resp.status_code != 200:
            logger.warning(f"UKON sayfasına ulaşılamadı ({resp.status_code})")
            return items

        soup = BeautifulSoup(resp.content, "html.parser")

        # Rapor tarihini bul (Örn: 30.10.2026)
        date_str = ""
        for h in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            m = re.search(r"(\d{2}\.\d{2}\.\d{4})", h.get_text())
            if m:
                date_str = m.group(1)
                break

        # Tarih 8 günden eskiyse gönderme
        if date_str:
            try:
                report_dt = datetime.strptime(date_str, "%d.%m.%Y")
                if (datetime.now() - report_dt).days > 8:
                    logger.info(f"UKON raporu son 7 günden eski ({date_str}), atlanıyor.")
                    return items
            except Exception:
                pass

        table = soup.find("table")
        if not table:
            return items

        rows_data = []
        adana_line = ""
        avg_line = ""

        for tr in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cols) >= 3:
                bolge = cols[0]
                dana = cols[1]
                kuzu = cols[2]

                if bolge.strip().lower() == "bölge" or "değişim" in bolge.lower():
                    continue

                if "ortalama" in bolge.lower():
                    avg_line = f"🇹🇷 TÜRKİYE ORTALAMASI: Dana {dana} TL | Kuzu {kuzu} TL"
                elif "akdeniz" in bolge.lower():
                    # Adana'nın bağlı olduğu Akdeniz Bölgesi özel vurgusu
                    adana_line = f"📍 AKDENİZ BÖLGESİ (ADANA): Dana {dana} TL | Kuzu {kuzu} TL"
                else:
                    clean_bolge = bolge.replace(" Bölgesi", "").strip()
                    rows_data.append(f"• {clean_bolge}: Dana {dana} TL | Kuzu {kuzu} TL")

        if not rows_data and not avg_line and not adana_line:
            return items

        lines = []
        if date_str:
            lines.append(f"📅 Rapor Tarihi: {date_str}")
        if avg_line:
            lines.append(avg_line)
        if adana_line:
            lines.append(adana_line)
            lines.append("─────────────────")
        lines.extend(rows_data[:6])

        summary_text = "\n".join(lines)
        title_text = f"🥩 [UKON RESMİ BÜLTENİ] Haftalık Karkas Kesim Fiyatları ({date_str or 'Güncel'})"
        unique_link = f"{UKON_URL}?tarih={date_str}" if date_str else UKON_URL

        items.append({
            "title": title_text,
            "link": unique_link,
            "source": "Ulusal Kırmızı Et Konseyi (UKON Resmi)",
            "category": "MARKET",
            "priority": 1,
            "summary": summary_text,
            "published_at": date_str
        })

    except Exception as e:
        logger.error(f"UKON fiyatları çekilirken hata: {e}")

    return items
