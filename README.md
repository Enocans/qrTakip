# QR LGS Takip Projesi

Bu proje, QR kod ile açılan tek sayfalık formdan öğrenci verilerini toplayıp Excel dosyasına kaydeder.

## Özellikler

- QR kod ile form erişimi
- Öğrenci bilgisi kaydı
- LGS ders bazlı takip (Türkçe, Matematik, Fen, İnkılap, İngilizce, Din)
- Günlük net ve toplam soru takibi
- Excel dosyasına otomatik kayıt
- Rapor sayfası

## Çalıştırma

1. Sanal ortam oluşturun
2. Kurulum:
   ```bash
   pip install -r requirements.txt
   ```
3. Uygulamayı çalıştırın:
   ```bash
   python app.py
   ```
4. Tarayıcıda açın:
   - http://localhost:5000/
   - http://localhost:5000/report
   - http://localhost:5000/qr

## Dosya yapısı

- app.py: Flask uygulaması
- templates/index.html: giriş formu
- templates/report.html: Excel raporu
- data/student_tracker.xlsx: otomatik oluşturulan dosya
