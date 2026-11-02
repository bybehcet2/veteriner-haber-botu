# 🩺 Besi ve Ruminant Hekimliği Anlık Takip Otomasyonu Kurulum Rehberi

Bu sistem; bir **Besi İşletmesinde** çalışan veteriner hekimlerin ihtiyaçlarına göre özel olarak yapılandırılmıştır:
- Sadece **Sığır, Koyun, Keçi** ve ruminant hastalıkları (Şap, PPR, Mavi Dil vb.)
- **Karkas et kesim fiyatları**, **UKON bültenleri** ve besi piyasası
- **İl ve İlçe Tarım Müdürlükleri** karantina ve aşılama verileri (1. Öncelik)
- **PubMed, WOAH (Dünya Sağlık Örgütü), LinkedIn ve Reddit** içeriklerinin **otomatik Türkçe çevirisi**

---

## 🚀 1. Adım: 2 Dakikada Telegram Botu Oluşturma

1. Telegram'da **`@BotFather`** botunu açın ve `/newbot` komutunu gönderin.
2. Botunuza bir isim ve sonu `bot` ile biten bir kullanıcı adı verin (Örn: `besi_takip_bot`).
3. Size verilen **API Token**'ı kopyalayın.
4. Telegram'da **`@userinfobot`** botuna `/start` diyerek **Chat ID**'nizi öğrenin.
5. Oluşturduğunuz botunuzu Telegram'da bulup **BAŞLAT (Start)** butonuna basın.

---

## ⚙️ 2. Adım: Yapılandırma (`.env` Dosyası)

`veterinary_news_bot/.env` dosyasını açıp bilgilerinizi girin:

```env
TELEGRAM_BOT_TOKEN=buraya_bot_tokeninizi_yapistirin
TELEGRAM_CHAT_ID=buraya_chat_idnizi_yapistirin

CHECK_INTERVAL_MINUTES=15
MAX_ITEMS_PER_CHECK=15

ENABLE_GOV_NEWS=True       # İl/İlçe Tarım & Bakanlık Verileri
ENABLE_WOAH_NEWS=True      # Dünya Hayvan Sağlığı Örgütü (Türkçe Çevirili)
ENABLE_GOOGLE_NEWS=True    # Karkas, Kesim Fiyatları ve Besi Haberleri
ENABLE_PUBMED=True         # Sığır/Koyun/Keçi Bilimsel Makaleleri (Türkçe Çevirili)
ENABLE_REDDIT=True         # Reddit r/Cattle, r/livestock (Türkçe Çevirili)
ENABLE_LINKEDIN=True       # LinkedIn Sektörel Paylaşımlar
```

---

## 🏃 3. Adım: Çalıştırma Yöntemleri

### Yöntem A: Menülü Başlatıcı (`start_bot.bat`)
Klasördeki **`start_bot.bat`** dosyasına çift tıklayarak:
- `[3]` ile bağlantınızı test edin (Telegramınıza test mesajı gelecektir).
- `[1]` ile botu sürekli dinleme modunda başlatın.

### Yöntem B: Terminal Komutları
```bash
# Telegram bağlantısını test et
python main.py --test-telegram

# Önizleme modu (Telegram'a göndermez, terminale basar)
python main.py --dry-run

# Sürekli dinleme modu
python main.py
```

---

## 📊 Bildirim Rozetleri ve Öncelik Sıralaması

Telefonunuza düşecek bildirimler önem sırasına göre şu şekildedir:

1. 🇹🇷 **[İL/İLÇE TARIM & BAKANLIK VERİSİ]** *(En Yüksek Öncelik)*: İlçe Tarım karantinaları, hayvan pazarı kapatma/açma kararları, şap sero-surveyans ve aşı takvimleri.
2. 🥩 **[ET VE BESİ PİYASASI / KARKAS]**: Dana ve kuzu karkas kesim fiyatları, UKON haftalık bültenleri, canlı baskül ve besilik dana fiyatları.
3. 🚨 **[SIĞIR/KOYUN/KEÇİ SALGIN ALARMI]**: Yerel ve bölgesel şap, PPR, mavi dil alarmları.
4. 🌍 **[DÜNYA HAYVAN SAĞLIĞI (WOAH)]**: Küresel ruminant salgınları (Türkçe çevirili).
5. 🔬 **[BİLİMSEL YAYIN (PubMed)]**: Besi sığırcılığı, rasyon, mastitis, buzağı sağlığı araştırmaları (Türkçe çevirili).
6. 💼 **[LINKEDIN SEKTÖREL GÜNDEM]**: Sektör uzmanlarının ve hekimlerin paylaşımları.
7. 💬 **[REDDIT BESİ & HEKİMLİK TARTIŞMASI]**: `r/Cattle` ve `r/livestock` vakaları (Türkçe çevirili).
