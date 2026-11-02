@echo off
chcp 65001 >nul
title Veteriner Hekim Anlik Haber ve Salgin Takip Botu
cls

echo ============================================================
echo   VETERINER HEKIM ANLIK HABER VE SALGIN TAKIP OTOMASYONU
echo ============================================================
echo.

:: Python kontrolu
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python sisteminizde kurulu degil veya PATH'e eklenmemis!
    echo Lutfen https://www.python.org adresinden Python 3 kurunuz.
    pause
    exit /b 1
)

:: .env dosyasi kontrolu
if not exist ".env" (
    echo [.env] dosyasi bulunamadi, .env.example kopyalaniyor...
    copy .env.example .env >nul
    echo [.env] olusturuldu. Lutfen Telegram bot bilgilerinizi giriniz.
)

:MENU
echo.
echo Lutfen yapmak istediginiz islemi seciniz:
echo.
echo  [1] Botu Surekli Calistir (Arka Planda Dinleme Modu)
echo  [2] Hizli Test / Onizleme (Dry-Run - Telegram'a gondermez)
echo  [3] Telegram Baglanti Testi
echo  [4] Veritabani Istatistiklerini Gor
echo  [5] Cikis
echo.
set /p CHOICE="Seciminiz (1-5): "

if "%CHOICE%"=="1" (
    cls
    echo [BILGI] Veteriner Takip Botu baslatiliyor... (Durdurmak icin Ctrl+C)
    python main.py
    pause
    goto MENU
)

if "%CHOICE%"=="2" (
    cls
    echo [BILGI] Dry-Run onizleme modu calistiriliyor...
    python main.py --dry-run
    pause
    goto MENU
)

if "%CHOICE%"=="3" (
    cls
    echo [BILGI] Telegram baglantisi test ediliyor...
    python main.py --test-telegram
    pause
    goto MENU
)

if "%CHOICE%"=="4" (
    cls
    python main.py --stats
    pause
    goto MENU
)

if "%CHOICE%"=="5" (
    exit /b 0
)

echo Gecersiz secim, lutfen 1-5 arasinda bir deger giriniz.
goto MENU
