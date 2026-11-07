"""
Veteriner Hekim Haber Botu - Veritabanı, Anlamsal Tekilleştirme ve Dengeli Dağıtım Modülü
Destek: Hem yerel SQLite (çevrimdışı/test) hem de Supabase PostgreSQL REST API (7/24 Bulut & GitHub Actions).
Özellik: Adana öncelikli, UKON et piyasası, PubMed bilimsel yayınları ve ülke gündemini dengeli iletir.
"""

import re
import sqlite3
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set

from config import (
    DB_PATH,
    CATEGORIES,
    SUPABASE_URL,
    SUPABASE_KEY,
    USE_SUPABASE,
    get_priority
)

logger = logging.getLogger(__name__)

STOPWORDS = {
    'için', 'olan', 'olarak', 'dair', 'göre', 'kadar', 'nedeniyle', 'hakkında', 'sonra',
    'önce', 'yeni', 'son', 'durum', 'haber', 'ajans', 'dakika', 'gazete', 'gazetesi',
    'ilgili', 'karşı', 'üzerine', 'etti', 'oldu', 'dedi', 'yaptı', 'aldı', 'başladı',
    'bir', 've', 'ile', 'veya', 'ise', 'bu', 'şu', 'o', 'da', 'de', 'ta', 'te',
    'neden', 'nasıl', 'kim', 'nerede', 'tarafından', 'geldi', 'gitti'
}


def _supabase_headers(return_minimal: bool = False) -> Dict[str, str]:
    """Supabase REST API için yetkilendirme başlıkları üretir."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    if return_minimal:
        headers["Prefer"] = "return=minimal"
    return headers


def clean_tokens(title: str) -> Set[str]:
    """Başlığı temizler, kaynak ekini (- Ajans) atar ve kök kelime kümesi üretir."""
    clean_title = re.sub(r'\s*[-–|].*$', '', title)
    words = re.findall(r'[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+', clean_title.lower())
    tokens = set()

    for w in words:
        if len(w) < 3 or w in STOPWORDS:
            continue

        for suffix in ['sinde', 'sında', 'sinden', 'sından', 'lerine', 'larına', 'lerde', 'larda',
                       'lerin', 'ların', 'sını', 'sini', 'deki', 'daki', 'ında', 'inde',
                       'ten', 'tan', 'den', 'dan', 'te', 'ta', 'de', 'da',
                       'nin', 'nın', 'nün', 'nun', 'in', 'ın', 'ün', 'un',
                       'ler', 'lar', 'si', 'sı', 'su', 'sü', 'ye', 'ya',
                       'ni', 'nı', 'nu', 'nü', 'li', 'lı', 'lu', 'lü']:
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                w = w[:-len(suffix)]
                break

        tokens.add(w)

    return tokens


def is_similar_topic(tokens1: Set[str], tokens2: Set[str], threshold: float = 0.45) -> bool:
    """İki başlığın aynı konuyu/olayı anlatıp anlatmadığını denetler."""
    if not tokens1 or not tokens2:
        return False

    intersection = tokens1 & tokens2
    min_len = min(len(tokens1), len(tokens2))
    if min_len == 0:
        return False

    similarity = len(intersection) / min_len
    return similarity >= threshold


def is_topic_already_saved(new_title: str, lookback_days: int = 7) -> bool:
    """Veritabanında son 7 gün içinde aynı konudan bahsedilip bahsedilmediğini kontrol eder."""
    # 1. UKON Resmi Bülteni: SADECE yayın tarihiyle (dd.mm.yyyy) tekilleştirilir.
    # Haftalık bülten başlıkları kelime olarak birbirine benzediği için anlamsal örtüşmeye ASLA girmemelidir!
    if "ukon" in new_title.lower():
        date_m = re.search(r'(\d{2}\.\d{2}\.\d{4})', new_title)
        if date_m:
            dt_str = date_m.group(1)
            if USE_SUPABASE:
                try:
                    url = f"{SUPABASE_URL}/rest/v1/news_items"
                    params = {"title": f"ilike.*{dt_str}*", "select": "id", "limit": "1"}
                    resp = requests.get(url, headers=_supabase_headers(), params=params, timeout=10)
                    if resp.status_code == 200 and len(resp.json()) > 0:
                        return True
                    return False  # Bu tarih veritabanında yoksa KESİNLİKLE YENİ bültendir, doğrudan kabul et!
                except Exception as e:
                    logger.warning(f"Supabase UKON kontrolü hatası: {e}")
                    return False
            else:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM news_items WHERE title LIKE ? LIMIT 1", (f"%{dt_str}%",))
                    if cursor.fetchone() is not None:
                        return True
                    return False

    new_tokens = clean_tokens(new_title)
    if not new_tokens:
        return False

    # 2. Son 7 günün başlıklarıyla anlamsal örtüşme kontrolü (UKON başlıkları bu kıyasa sokulmaz)
    if USE_SUPABASE:
        try:
            cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat() + "Z"
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            params = {"created_at": f"gte.{cutoff}", "select": "title", "order": "id.desc", "limit": "60"}
            resp = requests.get(url, headers=_supabase_headers(), params=params, timeout=10)
            if resp.status_code == 200:
                for row in resp.json():
                    existing_title = row.get("title", "")
                    if "ukon" in existing_title.lower():
                        continue
                    if is_similar_topic(new_tokens, clean_tokens(existing_title)):
                        return True
        except Exception as e:
            logger.warning(f"Supabase benzerlik kontrolü hatası: {e}")
    else:
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM news_items WHERE created_at >= ?", (cutoff,))
            rows = cursor.fetchall()
            for row in rows:
                existing_title = row[0]
                if "ukon" in existing_title.lower():
                    continue
                if is_similar_topic(new_tokens, clean_tokens(existing_title)):
                    return True

    return False


def get_db_connection() -> sqlite3.Connection:
    """SQLite veritabanı bağlantısı oluşturur (Yerel modda kullanılır)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Veritabanı yapısını kontrol eder veya ilklendirir."""
    if USE_SUPABASE:
        try:
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            params = {"select": "id", "limit": "1"}
            resp = requests.get(url, headers=_supabase_headers(), params=params, timeout=10)
            if resp.status_code == 200:
                logger.info("☁️ [SUPABASE BULUT AKTİF] Supabase PostgreSQL veritabanına başarıyla bağlanıldı.")
            else:
                logger.warning(f"Supabase bağlantı yanıt kodu: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Supabase bağlantı testi başarısız: {e}")
        return

    # Yerel SQLite İlklendirme
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                priority INTEGER DEFAULT 3,
                summary TEXT,
                published_at TEXT,
                created_at TEXT NOT NULL,
                sent_to_telegram INTEGER DEFAULT 0,
                sent_at TEXT
            )
        """)

        cursor.execute("PRAGMA table_info(news_items)")
        columns = [row[1] for row in cursor.fetchall()]
        if "priority" not in columns:
            cursor.execute("ALTER TABLE news_items ADD COLUMN priority INTEGER DEFAULT 3")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_link ON news_items(link)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_sent ON news_items(sent_to_telegram)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_priority ON news_items(priority)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_category ON news_items(category)")
        conn.commit()


def is_seen(link: str) -> bool:
    """Haber linkinin daha önce kaydedilip kaydedilmediğini sorgular."""
    cleaned_link = link.strip()
    if not cleaned_link:
        return True

    if USE_SUPABASE:
        try:
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            params = {"link": f"eq.{cleaned_link}", "select": "id", "limit": "1"}
            resp = requests.get(url, headers=_supabase_headers(), params=params, timeout=10)
            if resp.status_code == 200 and len(resp.json()) > 0:
                return True
            return False
        except Exception as e:
            logger.warning(f"Supabase is_seen sorgusu hatası: {e}")
            return False

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM news_items WHERE link = ? LIMIT 1", (cleaned_link,))
        return cursor.fetchone() is not None


def save_item(item: Dict[str, Any]) -> bool:
    """Haberi veritabanına kaydeder."""
    cleaned_link = item.get("link", "").strip()
    title = item.get("title", "").strip()
    if not cleaned_link or not title:
        return False

    if is_seen(cleaned_link):
        return False

    if is_topic_already_saved(title):
        return False

    category = item.get("category", "LIVESTOCK")
    priority = item.get("priority", get_priority(category))

    if USE_SUPABASE:
        now_iso = datetime.utcnow().isoformat() + "Z"
        payload = {
            "link": cleaned_link,
            "title": title,
            "source": item.get("source", "Bilinmeyen Kaynak").strip(),
            "category": category,
            "priority": priority,
            "summary": item.get("summary", "").strip(),
            "published_at": item.get("published_at", ""),
            "created_at": now_iso,
            "sent_to_telegram": 0
        }
        headers = _supabase_headers(return_minimal=True)
        headers["Prefer"] = "resolution=ignore-duplicates"
        try:
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"Supabase kayıt hatası: {e}")
            return False

    # SQLite Kaydı
    now_iso = datetime.now().isoformat()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO news_items (
                    link, title, source, category, priority, summary, published_at, created_at, sent_to_telegram
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                cleaned_link,
                title,
                item.get("source", "Bilinmeyen Kaynak").strip(),
                category,
                priority,
                item.get("summary", "").strip(),
                item.get("published_at", ""),
                now_iso
            ))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def mark_as_sent(link: str) -> None:
    """Haberi Telegram'a iletildi olarak işaretler."""
    cleaned_link = link.strip()
    if not cleaned_link:
        return

    if USE_SUPABASE:
        now_iso = datetime.utcnow().isoformat() + "Z"
        headers = _supabase_headers(return_minimal=True)
        try:
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            params = {"link": f"eq.{cleaned_link}"}
            payload = {"sent_to_telegram": 1, "sent_at": now_iso}
            requests.patch(url, headers=headers, params=params, json=payload, timeout=10)
        except Exception as e:
            logger.warning(f"Supabase mark_as_sent hatası: {e}")
        return

    now_iso = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE news_items
            SET sent_to_telegram = 1, sent_at = ?
            WHERE link = ?
        """, (now_iso, cleaned_link))
        conn.commit()


def get_unsent_items(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Telegram'a henüz iletilmemiş haberleri çekerken TÜM ALANLARDAN dengeli bir seçki oluşturur:
    1. Adana Yerel Alarmları (En başta - Öncelik 0)
    2. UKON Haftalık Resmi Et Raporu (Öncelik 1)
    3. Bilimsel Araştırma ve Buluşlar (PubMed Türkçe Çeviri - Garanti 2-3 adet)
    4. Ülke Gündemi & Bakanlık/Pazar Kararları (TR_GOV - 2 adet)
    5. Türkiye Geneli Salgın Alarmları (OUTBREAK - 2 adet)
    6. Sektörel / Vaka (LinkedIn & Reddit)
    """
    target_distribution = [
        ("ADANA_LOCAL", 2),  # Adana yerel haberleri
        ("MARKET", 1),       # UKON resmi et bülteni
        ("ACADEMIC", 3),     # PubMed bilimsel araştırmaları (GARANTİ)
        ("TR_GOV", 2),       # Ülke gündemi ve resmi pazar kararları
        ("OUTBREAK", 2),     # Salgın alarmları
        ("WOAH", 1),         # Dünya Hayvan Sağlığı Örgütü
        ("LINKEDIN", 1),     # LinkedIn sektörel
        ("REDDIT", 1)        # Reddit klinik vaka
    ]

    selected: List[Dict[str, Any]] = []
    seen_links = set()

    if USE_SUPABASE:
        try:
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            headers = _supabase_headers()

            # 1. Aşama: Her kategoriden kotası kadar bekleyen haberleri al
            for cat_key, quota in target_distribution:
                params = {
                    "sent_to_telegram": "eq.0",
                    "category": f"eq.{cat_key}",
                    "order": "id.desc",
                    "limit": str(quota),
                    "select": "*"
                }
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        if item["link"] not in seen_links:
                            seen_links.add(item["link"])
                            selected.append(item)

            # 2. Aşama: Kota dolmadıysa diğer bekleyenlerden tamamla
            if len(selected) < limit:
                params = {
                    "sent_to_telegram": "eq.0",
                    "order": "priority.asc,id.desc",
                    "limit": str(limit * 2),
                    "select": "*"
                }
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        if item["link"] not in seen_links:
                            seen_links.add(item["link"])
                            selected.append(item)
                            if len(selected) >= limit:
                                break

            selected.sort(key=lambda x: (x.get("priority", 3), -x.get("id", 0)))
            return selected[:limit]
        except Exception as e:
            logger.warning(f"Supabase get_unsent_items hatası: {e}")
            return []

    # SQLite
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Aşama: Kota
        for cat_key, quota in target_distribution:
            cursor.execute("""
                SELECT id, link, title, source, category, priority, summary, published_at, created_at
                FROM news_items
                WHERE sent_to_telegram = 0 AND category = ?
                ORDER BY id DESC
                LIMIT ?
            """, (cat_key, quota))
            rows = cursor.fetchall()
            for r in rows:
                item = dict(r)
                if item["link"] not in seen_links:
                    seen_links.add(item["link"])
                    selected.append(item)

        # 2. Aşama: Tamamlama
        if len(selected) < limit:
            cursor.execute("""
                SELECT id, link, title, source, category, priority, summary, published_at, created_at
                FROM news_items
                WHERE sent_to_telegram = 0
                ORDER BY priority ASC, id DESC
                LIMIT ?
            """, (limit * 2,))
            remaining_rows = cursor.fetchall()
            for r in remaining_rows:
                item = dict(r)
                if item["link"] not in seen_links:
                    seen_links.add(item["link"])
                    selected.append(item)
                    if len(selected) >= limit:
                        break

        selected.sort(key=lambda x: (x.get("priority", 3), -x.get("id", 0)))
        return selected[:limit]


def get_stats() -> Dict[str, Any]:
    """Sistem istatistiklerini döndürür."""
    if USE_SUPABASE:
        try:
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            params = {"select": "category,sent_to_telegram"}
            resp = requests.get(url, headers=_supabase_headers(), params=params, timeout=10)
            if resp.status_code == 200:
                rows = resp.json()
                total = len(rows)
                sent = sum(1 for r in rows if r.get("sent_to_telegram") == 1)
                by_category = {}
                for r in rows:
                    cat = r.get("category", "OTHER")
                    by_category[cat] = by_category.get(cat, 0) + 1
                return {
                    "total_seen": total,
                    "total_sent": sent,
                    "unsent": total - sent,
                    "by_category": by_category,
                    "backend": "Supabase PostgreSQL (Bulut)"
                }
        except Exception as e:
            logger.warning(f"Supabase stats hatası: {e}")

    # SQLite
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM news_items")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM news_items WHERE sent_to_telegram = 1")
        sent = cursor.fetchone()[0]

        cursor.execute("SELECT category, COUNT(*) FROM news_items GROUP BY category")
        by_category = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total_seen": total,
            "total_sent": sent,
            "unsent": total - sent,
            "by_category": by_category,
            "backend": "SQLite (Yerel)"
        }


def cleanup_old_items(days: int = 30) -> int:
    """Belirtilen günden eski ve iletilmiş haberleri silerek veritabanını temiz tutar."""
    if USE_SUPABASE:
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
            url = f"{SUPABASE_URL}/rest/v1/news_items"
            params = {"sent_to_telegram": "eq.1", "created_at": f"lt.{cutoff}"}
            headers = _supabase_headers(return_minimal=True)
            headers["Prefer"] = "return=representation"
            resp = requests.delete(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                return len(resp.json())
            return 0
        except Exception as e:
            logger.warning(f"Supabase temizlik hatası: {e}")
            return 0

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM news_items
            WHERE sent_to_telegram = 1 AND created_at < ?
        """, (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        return deleted


init_db()
