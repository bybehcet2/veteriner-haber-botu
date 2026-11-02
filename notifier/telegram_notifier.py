"""
Telegram Bildirim Gönderici Modülü
Sığır, Koyun, Keçi, Besi ve Karkas Haberlerini Estetik Kartlarla İletir.
"""

import html
import json
import logging
import time
from typing import Dict, Any, Tuple
import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CATEGORIES, HTTP_TIMEOUT

logger = logging.getLogger("vet_bot.telegram")


def escape_html(text: str) -> str:
    """Telegram HTML formatında hata vermemesi için özel karakterleri kaçırır."""
    if not text:
        return ""
    # <i> ve </i> etiketleri çeviri orijinalleri için korunsun
    escaped = html.escape(text, quote=False)
    escaped = escaped.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    return escaped


def check_bot_credentials() -> Tuple[bool, str]:
    """
    Telegram bot token ve chat id'sinin geçerli olup olmadığını doğrular.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID .env dosyasında tanımlı değil."

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        data = resp.json()
        if data.get("ok"):
            bot_name = data.get("result", {}).get("first_name", "Bot")
            username = data.get("result", {}).get("username", "")
            return True, f"Bot bağlantısı başarılı! Bot: @{username} ({bot_name})"
        else:
            return False, f"Telegram hatası: {data.get('description', 'Bilinmeyen hata')}"
    except Exception as e:
        return False, f"Telegram API'ye ulaşılamadı: {e}"


def send_telegram_raw(text: str, reply_markup: Dict[str, Any] = None) -> bool:
    """Telegram Bot API'ye doğrudan HTTP POST isteği gönderir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        resp = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
        data = resp.json()
        if data.get("ok"):
            return True
        else:
            logger.error(f"Telegram mesaj gönderme hatası: {data.get('description')}")
            return False
    except Exception as e:
        logger.error(f"Telegram isteği sırasında ağ hatası: {e}")
        return False


def format_news_html(item: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Haberi görsel olarak zengin ve okunaklı bir HTML kartına dönüştürür."""
    category_key = item.get("category", "LIVESTOCK")
    cat_info = CATEGORIES.get(category_key, CATEGORIES["LIVESTOCK"])
    badge = cat_info["badge"]
    category_name = cat_info["name"]

    raw_title = item.get("title", "Başlıksız")
    title = escape_html(raw_title)
    source = escape_html(item.get("source", "Bilinmeyen Kaynak"))
    summary = escape_html(item.get("summary", ""))
    pub_date = escape_html(item.get("published_at", ""))
    link = item.get("link", "").strip()

    lines = [
        f"{badge} <b>[{category_name}]</b>",
        "",
        f"📌 <b>{title}</b>",
        "",
        f"🏛️ <b>Kaynak:</b> {source}"
    ]

    if pub_date:
        lines.append(f"📅 <b>Tarih:</b> {pub_date}")

    if summary and summary != raw_title:
        lines.append("")
        lines.append(f"📝 <i>{summary}</i>")

    lines.append("")
    lines.append("────────────────")
    lines.append("🥩 <i>Besi & Ruminant Hekimliği Takip Sistemi</i>")

    text = "\n".join(lines)

    reply_markup = None
    if link.startswith("http"):
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🔗 Haberin Kaynağına Git", "url": link}]
            ]
        }

    return text, reply_markup


def send_news_item(item: Dict[str, Any]) -> bool:
    """Tek bir haber öğesini Telegram'a iletir."""
    text, reply_markup = format_news_html(item)
    success = send_telegram_raw(text, reply_markup)
    if success:
        time.sleep(0.4)
    return success


def send_startup_alert() -> bool:
    """Sistem başlatıldığında Telegram'a durum bildirimi gönderir."""
    text = (
        "🟢 <b>Besi & Ruminant Hekimliği Takip Sistemi Aktif!</b>\n\n"
        "🎯 <b>Takip Alanları:</b>\n"
        "• 🇹🇷 İl/İlçe Tarım & Bakanlık verileri (Şap, karantina, aşı)\n"
        "• 🥩 Karkas et ve kesim fiyatları, UKON bültenleri\n"
        "• 🌍 Dünya Hayvan Sağlığı (WOAH) salgınları (Türkçe çeviri)\n"
        "• 🔬 PubMed Sığır/Koyun/Keçi makaleleri (Türkçe çeviri)\n"
        "• 💼 LinkedIn ve Reddit mesleki paylaşımları (Türkçe çeviri)\n\n"
        "Pet ve kanatlı haberleri filtrelenmiş olup sadece sığır, koyun, keçi ve et piyasası iletilecektir."
    )
    return send_telegram_raw(text)
