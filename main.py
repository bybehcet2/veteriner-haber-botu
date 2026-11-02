"""
Veteriner Hekim Besi ve Ruminant Takip Otomasyonu - Ana Çalıştırıcı (Main)
Odak: Sadece UKON resmi et fiyatı, İl/İlçe karantinaları, PubMed bilimsel buluşları ve gerçek vakalar.
Boş haber, tekrar, taziye, komik görsel veya spekülasyon KESİNLİKLE gönderilmez.
"""

import argparse
import logging
import sys
import time
from typing import List, Dict, Any

# Windows konsolunda UTF-8 karakterlerin ve emojilerin hatasız basılması için
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    CHECK_INTERVAL_MINUTES,
    MAX_ITEMS_PER_CHECK,
    ENABLE_GOV_NEWS,
    ENABLE_WOAH_NEWS,
    ENABLE_GOOGLE_NEWS,
    ENABLE_PUBMED,
    ENABLE_REDDIT,
    ENABLE_LINKEDIN,
    CATEGORIES,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID
)
import database
from fetchers.ukon_fetcher import fetch_ukon_prices
from fetchers.rss_fetcher import fetch_google_news, fetch_linkedin_news, fetch_reddit_news
from fetchers.gov_fetcher import fetch_gkgm_announcements, fetch_tvhb_announcements
from fetchers.woah_fetcher import fetch_woah_news
from fetchers.pubmed_fetcher import fetch_pubmed_articles
from notifier.telegram_notifier import (
    send_news_item,
    check_bot_credentials,
    send_startup_alert
)

# Konsol Log Yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("vet_bot")


def collect_all_news() -> List[Dict[str, Any]]:
    """Etkinleştirilmiş tüm ruminant & besi kaynaklarından sadece elenmiş haberleri toplar."""
    all_items: List[Dict[str, Any]] = []

    # 1. UKON Resmi Haftalık Karkas Fiyatları (Haftada 1 Resmi Rapor)
    logger.info("UKON resmi kombina kesim fiyatları taranıyor...")
    ukon_items = fetch_ukon_prices()
    logger.info(f"-> UKON: {len(ukon_items)} adet resmi rapor bulundu.")
    all_items.extend(ukon_items)

    # 2. T.C. Tarım ve Orman Bakanlığı GKGM & TVHB (Sadece gerçek mevzuat/karantina)
    if ENABLE_GOV_NEWS:
        logger.info("Tarım Bakanlığı ve TVHB verileri taranıyor...")
        gkgm_items = fetch_gkgm_announcements()
        tvhb_items = fetch_tvhb_announcements()
        logger.info(f"-> GKGM: {len(gkgm_items)} adet | TVHB: {len(tvhb_items)} adet bulundu.")
        all_items.extend(gkgm_items)
        all_items.extend(tvhb_items)

    # 3. Google News: Sadece İl/İlçe Tarım Karantina & Hayvan Pazarı (Son 7 Gün)
    if ENABLE_GOOGLE_NEWS:
        logger.info("İl/İlçe Tarım karantina ve pazar kararları taranıyor...")
        gnews_items = fetch_google_news()
        logger.info(f"-> İl/İlçe Tarım Kararları: {len(gnews_items)} adet haber bulundu.")
        all_items.extend(gnews_items)

    # 4. WOAH (Dünya Hayvan Sağlığı Örgütü - Salgınlar + Türkçe Çeviri)
    if ENABLE_WOAH_NEWS:
        logger.info("WOAH küresel hayvan sağlığı bültenleri taranıyor...")
        woah_items = fetch_woah_news()
        logger.info(f"-> WOAH: {len(woah_items)} adet bülten bulundu.")
        all_items.extend(woah_items)

    # 5. PubMed: Sığır, Koyun, Keçi Bilimsel Buluşları & Tedaviler (Türkçe Çeviri)
    if ENABLE_PUBMED:
        logger.info("PubMed sığır/koyun/keçi bilimsel buluşları taranıyor...")
        pubmed_items = fetch_pubmed_articles()
        logger.info(f"-> PubMed: {len(pubmed_items)} adet makale bulundu.")
        all_items.extend(pubmed_items)

    # 6. LinkedIn: Büyükbaş ve Besi Sektörel Paylaşımları
    if ENABLE_LINKEDIN:
        logger.info("LinkedIn sektörel paylaşımları taranıyor...")
        linkedin_items = fetch_linkedin_news()
        logger.info(f"-> LinkedIn: {len(linkedin_items)} adet içerik bulundu.")
        all_items.extend(linkedin_items)

    # 7. Reddit: r/Cattle, r/livestock (Sadece ciddi klinik/vaka - Türkçe Çeviri)
    if ENABLE_REDDIT:
        logger.info("Reddit sığır klinik tartışmaları taranıyor...")
        reddit_items = fetch_reddit_news()
        logger.info(f"-> Reddit: {len(reddit_items)} adet başlık bulundu.")
        all_items.extend(reddit_items)

    return all_items


def process_and_dispatch(dry_run: bool = False) -> int:
    """Haberleri toplar, tekilleştirir ve Telegram'a seçici olarak iletir."""
    start_time = time.time()
    logger.info("=== Besi & Ruminant Seçici Tarama Döngüsü Başlatıldı ===")

    items = collect_all_news()
    logger.info(f"Toplam {len(items)} adet elenmiş içerik toplandı. Anlamsal tekilleştirme yapılıyor...")

    # Tarama içindeki mükerrer haberleri ele (Örn. Ajans344 ve Mersin Haber aynı Elbistan karantinasını yazdıysa sadece ilkini al)
    unique_batch_items = []
    seen_batch_tokens = []

    for item in items:
        title = item.get("title", "")
        toks = database.clean_tokens(title)

        is_dup = False
        if "ukon" not in title.lower():
            for seen_toks in seen_batch_tokens:
                if database.is_similar_topic(toks, seen_toks):
                    is_dup = True
                    break

        if not is_dup:
            seen_batch_tokens.append(toks)
            unique_batch_items.append(item)

    new_saved_count = 0
    for item in unique_batch_items:
        is_new = database.save_item(item)
        if is_new:
            new_saved_count += 1

    logger.info(f"Yeni keşfedilen benzersiz olay/haber sayısı: {new_saved_count}")

    # Dengeli dağıtım havuzundan en önemli haberleri çek (Maksimum 3-4 adet)
    unsent_items = database.get_unsent_items(limit=MAX_ITEMS_PER_CHECK)

    if not unsent_items:
        logger.info("🎯 İletilmeyi bekleyen yeni önemli haber bulunmuyor. Boş bildirim gönderilmeyecek.")
        return 0

    logger.info(f"İletilmeyi bekleyen öncelikli haber sayısı: {len(unsent_items)}")

    if dry_run:
        print("\n" + "=" * 65)
        print("🔍 [DRY-RUN / TEST MODU] - Seçici Hekim Bülteni Önizlemesi:")
        print(f"Toplam Seçilen Haber Sayısı: {len(unsent_items)} (Maks: {MAX_ITEMS_PER_CHECK})")
        print("=" * 65)
        for i, it in enumerate(unsent_items, 1):
            cat_badge = CATEGORIES.get(it["category"], {}).get("badge", "📌")
            cat_name = CATEGORIES.get(it["category"], {}).get("name", it["category"])
            priority = it.get("priority", 3)
            print(f"\n{i}. {cat_badge} [{cat_name}] (Öncelik: {priority})")
            print(f"   Başlık : {it['title']}")
            print(f"   Kaynak : {it['source']}")
            print(f"   Link   : {it['link']}")
            if it.get("summary"):
                lines = it['summary'].split("\n")
                preview = "\n            ".join(lines[:6])
                print(f"   Özet   : {preview}")
        print("\n" + "=" * 65)
        logger.info(f"Dry-run tamamlandı. Süre: {time.time() - start_time:.2f} sn.")
        return len(unsent_items)

    # Gerçek iletim
    sent_count = 0
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram token veya chat id ayarlanmamış! Gönderim yapılamıyor.")
        logger.warning(".env dosyasını doldurunuz. Ayrıntılar için setup_guide.md dosyasına bakınız.")
        return 0

    for it in unsent_items:
        success = send_news_item(it)
        if success:
            database.mark_as_sent(it["link"])
            sent_count += 1
            cat_name = CATEGORIES.get(it["category"], {}).get("name", it["category"])
            logger.info(f"Telegram'a iletildi ({cat_name}): {it['title'][:40]}...")
        else:
            logger.error(f"İletim başarısız: {it['title'][:40]}...")

    logger.info(f"Döngü bitti. {sent_count} adet haber Telegram'a iletildi. Süre: {time.time() - start_time:.2f} sn.")
    return sent_count


def run_daemon() -> None:
    """Belirli aralıklarla çalışan seçici arka plan döngüsü."""
    logger.info("🥩 Besi & Ruminant Seçici Takip Botu Arka Planda Başlatılıyor...")
    logger.info(f"Tarama Aralığı: {CHECK_INTERVAL_MINUTES} dakikada bir (Günde ~3-4 kontrol).")

    valid, msg = check_bot_credentials()
    if valid:
        logger.info(f"Telegram Durumu: {msg}")
        send_startup_alert()
    else:
        logger.warning(f"Telegram Uyarısı: {msg}")

    try:
        while True:
            try:
                process_and_dispatch(dry_run=False)
            except Exception as e:
                logger.error(f"Döngü sırasında hata: {e}", exc_info=True)

            logger.info(f"Sonraki kontrol için {CHECK_INTERVAL_MINUTES} dakika bekleniyor...")
            time.sleep(CHECK_INTERVAL_MINUTES * 60)
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu (Ctrl+C). Çıkılıyor...")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Veteriner Hekim Besi ve Ruminant Takip Botu")
    parser.add_argument("--dry-run", action="store_true", help="Mesaj göndermeden haberleri tara ve konsola bas")
    parser.add_argument("--once", action="store_true", help="Tek bir döngü çalıştırıp çık")
    parser.add_argument("--test-telegram", action="store_true", help="Telegram bağlantısını test et")
    parser.add_argument("--stats", action="store_true", help="Veritabanı istatistiklerini göster")
    parser.add_argument("--reset-db", action="store_true", help="Eski veritabanını temizle ve sıfırdan başlat")

    args = parser.parse_args()

    if args.reset_db:
        import sqlite3
        from config import DB_PATH
        if DB_PATH.exists():
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM news_items")
                conn.commit()
            print("Veritabanı temizlendi. Sistem yeni filtrelerle sıfırdan başlayacak.")
        return

    if args.stats:
        stats = database.get_stats()
        print("\n📊 VERİTABANI İSTATİSTİKLERİ:")
        print(f"Toplam Görülen Haber : {stats['total_seen']}")
        print(f"Telegram'a İletilen  : {stats['total_sent']}")
        print(f"İletilmeyi Bekleyen  : {stats['unsent']}")
        print("Kategorilere Göre Dağılım:")
        for cat, cnt in stats["by_category"].items():
            info = CATEGORIES.get(cat, {})
            print(f"  {info.get('badge', '•')} {info.get('name', cat)}: {cnt} adet")
        return

    if args.test_telegram:
        valid, msg = check_bot_credentials()
        print(f"\nTelegram Bağlantı Testi: {'BAŞARILI' if valid else 'BAŞARISIZ'}")
        print(f"Açıklama: {msg}")
        if valid:
            ok = send_startup_alert()
            print(f"Test Mesajı Gönderimi: {'BAŞARILI' if ok else 'BAŞARISIZ'}")
        return

    if args.dry_run:
        process_and_dispatch(dry_run=True)
        return

    if args.once:
        process_and_dispatch(dry_run=False)
        return

    run_daemon()


if __name__ == "__main__":
    main()
