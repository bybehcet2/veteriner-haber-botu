"""
Veteriner Hekim Besi ve Ruminant Takip Botu - Yapılandırma Dosyası
Öncelik: Adana ve Çukurova Yerel Haberleri (Priority 0)
Odak: Sığır, Koyun, Keçi, Besi İşletmesi, Karkas/Et Fiyatları ve Resmi Tarım Verileri
"""

import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Ayarları
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Çalışma Ayarları (Acil salgınları yakalamak için 20 dk kontrol; spam yoksa sessiz)
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "20"))
MAX_ITEMS_PER_CHECK = int(os.getenv("MAX_ITEMS_PER_CHECK", "10"))

# Zaman Sınırı (Maksimum kaç günlük haberler kabul edilsin)
MAX_AGE_DAYS = 30

# Kaynak Kontrolü
ENABLE_GOV_NEWS = os.getenv("ENABLE_GOV_NEWS", "True").lower() == "true"
ENABLE_WOAH_NEWS = os.getenv("ENABLE_WOAH_NEWS", "True").lower() == "true"
ENABLE_GOOGLE_NEWS = os.getenv("ENABLE_GOOGLE_NEWS", "True").lower() == "true"
ENABLE_PUBMED = os.getenv("ENABLE_PUBMED", "True").lower() == "true"
ENABLE_REDDIT = os.getenv("ENABLE_REDDIT", "True").lower() == "true"
ENABLE_LINKEDIN = os.getenv("ENABLE_LINKEDIN", "True").lower() == "true"

# Veritabanı Yolu (Yerel SQLite)
DB_PATH = BASE_DIR / "data" / "veterinary_news.db"

# Supabase Bulut Veritabanı Ayarları (GitHub Actions ve 7/24 Bulut İçin)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# HTTP Ayarları
HTTP_TIMEOUT = 15
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Kategori İsimleri, Emojileri ve Öncelikleri (0: En Yüksek Öncelik - Adana)
CATEGORIES = {
    "ADANA_LOCAL": {
        "name": "ADANA & ÇUKUROVA YEREL ALARMI",
        "badge": "📍🚨",
        "priority": 0,  # En yüksek öncelik: listenin 1. sırası
        "quota": 4,
        "description": "Adana ve ilçelerindeki şap, karantina, aşılama ve mezbaha kararları",
    },
    "MARKET": {
        "name": "ET VE BESİ PİYASASI / KARKAS",
        "badge": "🥩",
        "priority": 1,
        "quota": 2,
        "description": "Karkas kesim fiyatları, UKON bültenleri, hayvan pazarı durumu ve et piyasası",
    },
    "TR_GOV": {
        "name": "İL/İLÇE TARIM & BAKANLIK VERİSİ",
        "badge": "🇹🇷",
        "priority": 2,
        "quota": 3,
        "description": "Tarım Bakanlığı, GKGM, İl ve İlçe Tarım Müdürlükleri somut aşı/karantina verileri",
    },
    "OUTBREAK": {
        "name": "SIĞIR/KOYUN/KEÇİ SALGIN ALARMI",
        "badge": "🚨",
        "priority": 2,
        "quota": 3,
        "description": "Şap, PPR, mavi dil, şarbon, karantina ve aşılama kararları",
    },
    "WOAH": {
        "name": "DÜNYA HAYVAN SAĞLIĞI (WOAH)",
        "badge": "🌍",
        "priority": 3,
        "quota": 2,
        "description": "WOAH/OIE küresel ruminant ve hayvan sağlığı bültenleri (Türkçe çevirili)",
    },
    "ACADEMIC": {
        "name": "BİLİMSEL YAYIN & BULUŞ (PubMed)",
        "badge": "🔬",
        "priority": 3,
        "quota": 2,
        "description": "Sığır, koyun ve keçi üzerine yeni tedaviler, rasyon ve araştırmalar (Türkçe)",
    },
    "LINKEDIN": {
        "name": "LINKEDIN SEKTÖREL GÜNDEM",
        "badge": "💼",
        "priority": 4,
        "quota": 1,
        "description": "LinkedIn üzerinde hekim ve sektör paylaşımları",
    },
    "REDDIT": {
        "name": "REDDIT BESİ & HEKİMLİK TARTIŞMASI",
        "badge": "💬",
        "priority": 4,
        "quota": 1,
        "description": "Reddit mesleki tartışmaları (Türkçe çevirili)",
    },
    "LIVESTOCK": {
        "name": "BESİ & SÜRÜ YÖNETİMİ",
        "badge": "🐄",
        "priority": 3,
        "quota": 2,
        "description": "Besi sığırcılığı, rasyon, yem, sürü sağlığı ve zootekni",
    },
}

# 1. ADANA VE ÇUKUROVA BÖLGESİ KELİMELERİ (Öncelik 0)
ADANA_KEYWORDS = [
    r"\badana\b", r"\bseyhan\b", r"\byüreğir\b", r"\bçukurova\b", r"\bsarıçam\b",
    r"\bceyhan\b", r"\bkozan\b", r"\bimamoğlu\b", r"\bkarataş\b", r"\bkaraisalı\b",
    r"\bpozantı\b", r"\bfeke\b", r"\bsaimbeyli\b", r"\btufanbeyli\b", r"\baladağ\b",
    r"\byumurtalık\b"
]

# 2. HEDEF HAYVANLAR VE KONULAR (Sığır, Koyun, Keçi, Besi, Karkas, Ruminant)
TARGET_PATTERNS = [
    r"\bsığır\b", r"\bbüyükbaş\b", r"\bdana\b", r"\btosun\b", r"\bdüve\b", r"\binek\b", r"\bbuzağı\b",
    r"\bbovine\b", r"\bcattle\b", r"\bcalves\b", r"\bcalf\b", r"\bbeef\b", r"\bfeedlot\b", r"\bruminant\b",
    r"\bheifer\b", r"\bsteer\b", r"\bbull\b", r"\bcow\b", r"\bdairy cow\b",
    r"\bkoyun\b", r"\bküçükbaş\b", r"\bkuzu\b", r"\bkoç\b", r"\bkoyunculuk\b",
    r"\bovine\b", r"\bsheep\b", r"\blamb\b",
    r"\bkeçi\b", r"\boğlak\b", r"\bteke\b", r"\bcaprine\b", r"\bgoat\b",
    r"\bkarkas\b", r"\bbesi\b", r"\bbesicilik\b", r"\bbesi danası\b", r"\bbesilik\b",
    r"\bkesim fiyatı\b", r"\bkırmızı et\b", r"\bcanlı baskül\b", r"\bukon\b",
    r"\bet ve süt kurumu\b", r"\bhayvan pazarı\b", r"\bhayvan borsası\b", r"\byem fiyat\b",
    r"\bkesimhane\b", r"\bet fiyat\b", r"\bkarkas et\b",
    r"\bşap\b", r"\bsat-2\b", r"\bppr\b", r"\bmavi dil\b", r"\bbluetongue\b",
    r"\bşarbon\b", r"\banthrax\b", r"\bbrucell\b", r"\bil tarım\b", r"\bilçe tarım\b",
    r"\blumpy skin\b", r"\bnodüler ekzantem\b", r"\bmastitis\b", r"\bketozis\b",
    r"\brumen\b", r"\bruminal\b", r"\btüberküloz\b", r"\bçiçek hastalığı\b",
    r"\benterotoksemi\b", r"\bçelerme\b", r"\bagalaksi\b", r"\bbvd\b", r"\bibr\b"
]

# 3. DIŞLANAN HAYVANLAR (Pet, Kanatlı, Domuz)
EXCLUDE_PATTERNS = [
    r"\bkedi\b", r"\bköpek\b", r"\bcat\b", r"\bdog\b", r"\bfeline\b", r"\bcanine\b", r"\bpet shop\b",
    r"\bsokak köpeği\b", r"\bsokak kedisi\b", r"\bbarınak\b", r"\bfip\b", r"\bparvo\b",
    r"\btavuk\b", r"\byumurta\b", r"\bkanatlı\b", r"\bpoultry\b", r"\bchicken\b", r"\bhindi\b",
    r"\bdomuz\b", r"\bpig\b", r"\bswine\b", r"\bpork\b"
]

# 4. KESİN ELEME: PR, KUTLAMA, SPOR, TAZİYE, DÜNYA X GÜNÜ, PROTOKOL ÇÖPLERİ
NOISE_PATTERNS = [
    r"\bvoleybol\b", r"\bvakıfbank\b", r"\bşampiyon\b", r"\bturnuva\b", r"\bsporcu\b", r"\bmadalya\b",
    r"\bfutbol\b", r"\bbasketbol\b", r"\bligi\b", r"\bkupa\b",
    r"\btaziye\b", r"\bvefat\b", r"\bbaşsağlığı\b", r"\bmerhum\b", r"\bmerhume\b", r"\bcenaze\b",
    r"\brahmetle anıyoruz\b", r"\bhakkın rahmetine\b",
    r"\btebrik\b", r"\bkutlarız\b", r"\bkutlu olsun\b", r"\bkutlama\b", r"\bbaşarılar diler\b",
    r"\byeni görevinde başarı\b", r"\bhayırlı olsun\b",
    r"dünya\s+.*\s+günü", r"farkındalık\s+günü", r"tüberküloz\s+günü", r"veteriner\s+günü",
    r"kuduz\s+günü", r"zoonoz\s+günü", r"zoonotik\s+hastalık\s+günü", r"süt\s+günü", r"çevre\s+günü",
    r"ziyaret\s+etti", r"ziyarette\s+bulundu", r"makamında\s+ağırladı", r"nezaket\s+ziyareti",
    r"plaket\s+takdim", r"iftar\s+programı", r"bayramlaşma", r"kurban\s+bayramınız\s+kutlu",
    r"genel\s+kurul\s+toplantısı", r"divan\s+kurulu", r"oda\s+başkanı\s+seçil",
    r"\biş ilanı\b", r"\btakım arkadaşı arıyoruz\b", r"\bpersonel alımı\b", r"\beleman aranıyor\b"
]


def is_adana_related(text: str) -> bool:
    """Metnin Adana veya ilçeleriyle ilgili olup olmadığını denetler."""
    t = text.lower()
    return any(re.search(p, t, re.IGNORECASE) for p in ADANA_KEYWORDS)


def is_noise(text: str) -> bool:
    """Protokol, taziye, spor, tebrik ve gün kutlaması gibi PR gürültülerini tespit eder."""
    t = text.lower()
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return True
    return False


def is_fresh(pub_date_str: str = "", url: str = "", struct_time_obj: time.struct_time = None) -> bool:
    """Haberin son 30 gün içinde yayınlanıp yayınlanmadığını denetler."""
    now = datetime.now()
    current_year = now.year

    if url:
        for old_year in range(2015, current_year):
            if f"/{old_year}/" in url or f"-{old_year}/" in url or f"_{old_year}_" in url:
                return False

    if struct_time_obj:
        try:
            pub_dt = datetime.fromtimestamp(time.mktime(struct_time_obj))
            if (now - pub_dt).days > MAX_AGE_DAYS:
                return False
            return True
        except Exception:
            pass

    if pub_date_str:
        for old_year in range(2015, current_year):
            if str(old_year) in pub_date_str:
                return False

    return True


def is_target_ruminant(text: str) -> bool:
    """Metnin Sığır, Koyun, Keçi, Besi veya Karkas konusuyla ilgili olup olmadığını denetler."""
    t = text.lower()
    has_target = any(re.search(pattern, t, re.IGNORECASE) for pattern in TARGET_PATTERNS)
    return has_target


def is_acceptable_news(title: str, summary: str = "", source: str = "", pub_date: str = "", url: str = "", struct_time_obj: time.struct_time = None) -> bool:
    """Tüm süzgeçleri tek noktada uygulayan ana filtreleme fonksiyonu."""
    combined = f"{title} {summary}"

    if is_noise(combined):
        return False

    if not is_fresh(pub_date, url, struct_time_obj):
        return False

    if not is_target_ruminant(combined):
        return False

    return True


def classify_news(title: str, summary: str = "", source: str = "") -> str:
    """Haber başlığı, özeti ve kaynağına göre ilgili kategoriyi belirler."""
    content_text = f"{title} {summary}".lower()
    combined = f"{title} {summary} {source}".lower()

    # 0. EN ÜST ÖNCELİK: Adana ve Çukurova Yerel Haberleri (Priority 0)
    # Sadece haber başlığı ve özetinde Adana/ilçeleri geçiyorsa kabul edilir
    if is_adana_related(content_text) and is_target_ruminant(combined):
        return "ADANA_LOCAL"

    # 1. Et ve Besi Piyasası (UKON, Karkas)
    if any(k in combined for k in ["ukon", "karkas", "kesim fiyat", "kırmızı et", "et fiyat", "baskül", "besi danası"]):
        return "MARKET"

    # 2. T.C. İl/İlçe Tarım veya Bakanlık
    if any(k in combined for k in ["il tarım", "ilçe tarım", "gkgm", "tarım ve orman bak", "tarimorman"]):
        return "TR_GOV"

    # 3. WOAH / Dünya Sağlık Örgütü
    if "woah" in source.lower() or "oie" in source.lower():
        return "WOAH"

    # 4. PubMed
    if "pubmed" in source.lower():
        return "ACADEMIC"

    # 5. LinkedIn
    if "linkedin" in source.lower():
        return "LINKEDIN"

    # 6. Reddit
    if "reddit" in source.lower():
        return "REDDIT"

    # 7. Salgın Hastalık
    if any(re.search(p, combined, re.IGNORECASE) for p in [r"\bşap\b", r"\bsat-2\b", r"\bppr\b", r"\bmavi dil\b", r"\bşarbon\b", r"\bkarantina\b"]):
        return "OUTBREAK"

    return "LIVESTOCK"


def get_priority(category: str) -> int:
    """Kategoriye göre öncelik puanı döndürür (0 en yüksek - Adana)."""
    return CATEGORIES.get(category, {}).get("priority", 3)
