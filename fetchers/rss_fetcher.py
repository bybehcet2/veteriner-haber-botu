"""
Google News, LinkedIn ve Reddit Akışlarını Toplayan ve Çeviren Modül
Filtre: Sadece son 7 gün (Google News) ve son 48 saat (Reddit/LinkedIn).
Yalnızca somut karantina, aşı ve klinik/bilimsel yöntemler kabul edilir.
Komik fotoğraflar, tek kelimelik gönderiler ve spekülasyonlar kesinlikle elenir.
"""

import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any
import feedparser
import requests
from bs4 import BeautifulSoup

from config import (
    DEFAULT_HEADERS,
    HTTP_TIMEOUT,
    is_acceptable_news,
    classify_news,
    get_priority,
    ENABLE_GOOGLE_NEWS,
    ENABLE_LINKEDIN,
    ENABLE_REDDIT
)
from translator import translate_to_turkish

logger = logging.getLogger("vet_bot.rss")

# Google News: Adana & Çukurova Öncelikli Karantina & Hayvan Pazarı (Son 7 Gün)
GOOGLE_NEWS_FEEDS = [
    # 0. ADANA & ÇUKUROVA ÖZEL AKIŞLARI (Öncelik 0)
    {
        "name": "Adana & Çukurova Şap ve Karantina",
        "url": "https://news.google.com/rss/search?q=adana+şap+OR+karantina+OR+aşılama+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        "default_cat": "ADANA_LOCAL"
    },
    {
        "name": "Adana İl/İlçe Tarım ve Hayvan Pazarı",
        "url": "https://news.google.com/rss/search?q=adana+il+tarım+OR+ceyhan+OR+kozan+hayvan+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        "default_cat": "ADANA_LOCAL"
    },
    # 1. Genel İl Tarım Şap ve Karantina
    {
        "name": "İl Tarım Şap ve Karantina",
        "url": "https://news.google.com/rss/search?q=il+tarım+müdürlüğü+şap+OR+karantina+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        "default_cat": "TR_GOV"
    },
    {
        "name": "Hayvan Pazarı ve Borsa Kararları",
        "url": "https://news.google.com/rss/search?q=hayvan+pazarı+kapatıldı+OR+hayvan+borsası+açıldı+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        "default_cat": "TR_GOV"
    },
    {
        "name": "Büyükbaş Aşılama ve Salgın",
        "url": "https://news.google.com/rss/search?q=büyükbaş+şap+aşılama+karantina+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        "default_cat": "OUTBREAK"
    }
]

# LinkedIn Arama Akışı (Son 7 Gün, Sadece Sektörel)
LINKEDIN_FEEDS = [
    {
        "name": "LinkedIn (Büyükbaş & Besi)",
        "url": "https://news.google.com/rss/search?q=site:linkedin.com+büyükbaş+OR+sığır+OR+karkas+OR+besi+when:7d&hl=tr&gl=TR&ceid=TR:tr",
        "default_cat": "LINKEDIN"
    }
]

# Reddit Akışları (Sadece r/Cattle ve r/livestock)
REDDIT_FEEDS = [
    {
        "name": "Reddit r/Cattle",
        "url": "https://www.reddit.com/r/Cattle/new/.rss",
        "default_cat": "REDDIT"
    },
    {
        "name": "Reddit r/livestock",
        "url": "https://www.reddit.com/r/livestock/new/.rss",
        "default_cat": "REDDIT"
    }
]

# Reddit ve LinkedIn için klinik, besleme veya sürü yönetimi ZORUNLU kelimeleri
CLINICAL_MUST_HAVE = [
    "mastitis", "acidosis", "bloat", "ketosis", "pneumonia", "respiratory", "diarrhea",
    "scours", "treatment", "vaccine", "vaccination", "antibiotic", "dose", "dosage",
    "feedlot", "ration", "silage", "weight gain", "adg", "fcr", "carcass", "dystocia",
    "calving", "hypocalcemia", "milk fever", "bvd", "ibr", "clostridium", "foot rot",
    "lameness", "parasite", "lice", "tedavi", "aşı", "hastalık", "rasyon", "silaj",
    "asidoz", "besi", "karkas", "karantina", "protokol", "enfeksiyon", "sürü sağlığı"
]

# Reddit meme / komik resim / boş başlık filtreleri
REDDIT_FLUFF_PATTERNS = [
    r"\bcute\b", r"\bfunny\b", r"\bmeme\b", r"\bphoto\b", r"\bpic\b", r"\blook at\b",
    r"\bname my\b", r"\bjoke\b", r"\bsweet\b", r"\bpetting\b", r"\bbaby\b", r"\bart\b"
]


def clean_html_summary(html_text: str, max_length: int = 240) -> str:
    """HTML etiketlerini temizler ve kısa bir özet bırakır."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def fetch_google_news() -> List[Dict[str, Any]]:
    """İl/İlçe Tarım somut pazar kapatma/açma ve aşılama kararlarını çeker."""
    if not ENABLE_GOOGLE_NEWS:
        return []

    items: List[Dict[str, Any]] = []

    for feed_info in GOOGLE_NEWS_FEEDS:
        try:
            resp = requests.get(feed_info["url"], headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                continue

            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:8]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = clean_html_summary(entry.get("summary", ""))
                pub_date = entry.get("published", "")
                parsed_time = entry.get("published_parsed")

                if not title or not link:
                    continue

                # SIKI SÜZGEÇ
                if not is_acceptable_news(title, summary, feed_info["name"], pub_date, link, parsed_time):
                    continue

                category = classify_news(title, summary, feed_info["name"])
                if category == "GENERAL" or category == "LIVESTOCK":
                    def_cat = feed_info.get("default_cat", "TR_GOV")
                    if def_cat == "ADANA_LOCAL" and not is_acceptable_news(title, summary, ""):
                        category = "TR_GOV"
                    else:
                        category = def_cat

                items.append({
                    "title": title,
                    "link": link,
                    "source": feed_info["name"],
                    "category": category,
                    "priority": get_priority(category),
                    "summary": summary,
                    "published_at": pub_date
                })
        except Exception as e:
            logger.error(f"Google News ({feed_info['name']}) hatası: {e}")

    return items


def fetch_linkedin_news() -> List[Dict[str, Any]]:
    """LinkedIn üzerindeki veterinerlik ve besi paylaşımlarını çeker (Sadece ciddi içerik)."""
    if not ENABLE_LINKEDIN:
        return []

    items: List[Dict[str, Any]] = []

    for feed_info in LINKEDIN_FEEDS:
        try:
            resp = requests.get(feed_info["url"], headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                continue

            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:6]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = clean_html_summary(entry.get("summary", ""))
                pub_date = entry.get("published", "")
                parsed_time = entry.get("published_parsed")

                if not title or not link:
                    continue

                if "/in/" in link or "/pub/" in link or "at Akbank" in title or "Pazarlama Uzmanı" in title:
                    continue

                if not is_acceptable_news(title, summary, "LinkedIn", pub_date, link, parsed_time):
                    continue

                tr_title, was_en = translate_to_turkish(title)
                tr_summary, _ = translate_to_turkish(summary) if summary else ("", False)

                display_title = f"💼 [LinkedIn] {tr_title}"
                if was_en and tr_title != title:
                    display_title += f"\n<i>(Orijinal: {title[:75]}...)</i>"

                items.append({
                    "title": display_title,
                    "link": link,
                    "source": "LinkedIn Sektörel Paylaşım",
                    "category": "LINKEDIN",
                    "priority": get_priority("LINKEDIN"),
                    "summary": tr_summary or summary,
                    "published_at": pub_date
                })
        except Exception as e:
            logger.error(f"LinkedIn akışı hatası: {e}")

    return items


def fetch_reddit_news() -> List[Dict[str, Any]]:
    """
    Reddit sığır tartışmalarını çeker.
    Komik görseller, meme'ler ve boş gönderiler KESİNLİKLE elenir.
    Yalnızca gerçek bir klinik vaka, hastalık veya rasyon sorusu içeren başlıklar kabul edilir.
    """
    if not ENABLE_REDDIT:
        return []

    items: List[Dict[str, Any]] = []
    reddit_headers = {"User-Agent": "VetBesiBot/3.0 by VetAssistant"}
    now = datetime.now()

    for feed_info in REDDIT_FEEDS:
        try:
            resp = requests.get(feed_info["url"], headers=reddit_headers, timeout=HTTP_TIMEOUT)
            if resp.status_code != 200:
                continue

            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:10]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = clean_html_summary(entry.get("summary", ""))
                parsed_time = entry.get("published_parsed")

                if not title or not link:
                    continue

                # 1. Başlık çok kısaysa (Örn: "Cow", "Look at him") doğrudan ELE
                if len(title.split()) < 4 or len(title) < 20:
                    continue

                # 2. Komik resim, meme veya sevimlilik içeriyorsa ELE
                title_lower = title.lower()
                if any(re.search(p, title_lower) for p in REDDIT_FLUFF_PATTERNS):
                    continue

                # 3. Son 48 saatten eskiyse ELE (Sadece güncel)
                if parsed_time:
                    try:
                        pub_dt = datetime.fromtimestamp(time.mktime(parsed_time))
                        if (now - pub_dt).total_seconds() > 48 * 3600:
                            continue
                    except Exception:
                        pass

                # 4. Klinik, hastalık, tedavi veya rasyon terimi ZORUNLU
                combined = f"{title} {summary}".lower()
                if not any(k in combined for k in CLINICAL_MUST_HAVE):
                    continue

                # 5. Genel süzgeç
                if not is_acceptable_news(title, summary, feed_info["name"], url=link, struct_time_obj=parsed_time):
                    continue

                # Otomatik Türkçe Çeviri
                tr_title, was_en = translate_to_turkish(title)
                tr_summary, _ = translate_to_turkish(summary) if summary else ("", False)

                display_title = f"💬 [Reddit Vaka & Tartışma] {tr_title}"
                if was_en and tr_title != title:
                    display_title += f"\n<i>(Orijinal: {title[:75]}...)</i>"

                items.append({
                    "title": display_title,
                    "link": link,
                    "source": feed_info["name"],
                    "category": "REDDIT",
                    "priority": get_priority("REDDIT"),
                    "summary": tr_summary or summary,
                    "published_at": ""
                })
        except Exception as e:
            logger.error(f"Reddit akışı ({feed_info['name']}) hatası: {e}")

    return items
