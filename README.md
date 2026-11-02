# 🩺 Veteriner Hekim Anlık Haber ve Salgın Takip Botu

Veteriner hekimler için resmi duyuruları, salgın alarmlarını, mevzuat değişikliklerini, akademik makaleleri ve sosyal medya gündemini tek bir merkezde toplayıp doğrudan **Telegram** üzerinden cep telefonunuza ileten hafif ve akıllı otomasyon sistemi.

## 🌟 Öne Çıkan Özellikler

- **Resmi Kurumlar:** T.C. Tarım ve Orman Bakanlığı (GKGM) & TVHB duyuruları.
- **Küresel Salgın Takibi:** Dünya Hayvan Sağlığı Örgütü (WOAH - OIE) anlık bültenleri.
- **Gündem & Basın:** Google News veteriner hekimlik, şap, kuduz, kuş gribi, sürü sağlığı akışları.
- **Akademik Yayınlar:** PubMed E-utilities üzerinden son hakemli araştırmalar.
- **Sosyal Medya:** Reddit `r/veterinary` ve `r/vettech` hekim tartışmaları.
- **SQLite Tekilleştirme:** Daha önce gönderilen bir haberi asla tekrar göndermez.
- **Akıllı Kategorilendirme:** Haberleri 🚨 Salgın, 🐄 Çiftlik, ⚖️ Mevzuat, 🔬 Bilimsel, 🐾 Pet ve 📢 Sektörel olarak etiketler.
- **Zengin Bildirim:** Her mesajda haberin kaynağına tek tıkla giden doğrudan link butonu.

## 📂 Dosya Yapısı

- `main.py`: Orkestrasyon ve döngü çalıştırıcısı
- `config.py`: Anahtar kelimeler, kategoriler ve ayarlar
- `database.py`: SQLite veritabanı ve tekilleştirme motoru
- `fetchers/`: Haber toplayıcı modüller (RSS, GKGM, TVHB, WOAH, PubMed)
- `notifier/`: Telegram API mesaj ve buton formatlayıcı
- `start_bot.bat`: Windows için menülü kolay başlatıcı
- `setup_guide.md`: Adım adım 2 dakikalık Telegram kurulum rehberi
- `.env`: API anahtarları ve yapılandırma dosyası

## 🚀 Hızlı Başlangıç

1. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
2. `.env` dosyasını `setup_guide.md` rehberine göre doldurun.
3. Botu başlatın:
   - `start_bot.bat` çift tıklayarak VEYA
   - `python main.py` komutuyla.
