# Pusula · LGS Takip

Telefon odaklı, tek ekranda günlük soru girişi. Flask + SQLite backend, sade HTML/CSS/JavaScript arayüzü ve kurulabilir PWA. Öğrenci ders başına doğru, yanlış ve boş soru sayılarını girer; sunucu öğretmen ve babaya ayrı WhatsApp şablon mesajı gönderir. E-posta gönderilmez.

## Çalıştırma

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv/Scripts/python.exe app.py
```

Tarayıcı: http://localhost:5000. `.env` dosyasına rastgele ve kalıcı bir `SECRET_KEY` yazın. Varsayılan yerel kullanımda anahtar `data/.session-secret` dosyasında oluşturulur. Üretimde Waitress sunucusu kullanılır.

## WhatsApp kurulumu

Twilio WhatsApp hesabında gönderici numarası ve onaylı Content Template oluşturun. `.env` içindeki `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` (ör. +1415...), `TWILIO_DAILY_CONTENT_SID` alanlarını doldurun. `TEACHER_PHONE` tanımlarsanız öğretmen numarası sunucudan alınır; aksi halde öğrenci girer. Gerçek anahtarları kaynak koda eklemeyin.

Şablon örneği:

> {{1}} adlı öğrencinin {{2}} tarihli günlük çalışma kaydı: {{3}} soru. Ders özeti: {{4}}.

Değişkenler sırasıyla öğrenci, çalışma tarihi, bu kayıttaki toplam soru ve derslerin doğru/yanlış/boş özetidir. Günlük takip için yeni bir onaylı şablon oluşturup `TWILIO_DAILY_CONTENT_SID` olarak tanımlayın; eski deneme şablonu kullanılmaz. Aynı gün birden fazla girişte her bildirim yalnızca yeni çalışma kaydını içerir; günlük toplam geçmişte birleştirilir. Alıcıların WhatsApp bildirim izni olmalıdır. Sandbox kullanıyorsanız her alıcı sandbox'a katılmalıdır; üretimde onaylı gönderici ve şablon gereklidir. [Twilio şablon mesajı belgeleri](https://www.twilio.com/docs/whatsapp/tutorial/send-whatsapp-notification-messages-templates).

Gönderim, kayıt sonrasında otomatik yapılır. Ekran iki alıcı için ayrı durum gösterir: yapılandırılmadı, sağlayıcıya iletildi, reddedildi, belirsiz veya bekliyor. Sağlayıcının kabulü, cihaza teslim edildiği anlamına gelmez; teslim webhook'u bu sürümde yoktur. Belirsiz istekler otomatik yeniden gönderilmez. Aynı kayıt kimliğiyle yeniden denemek ikinci kayıt veya ikinci mesaj oluşturmaz. Sunucu gönderim sırasında kapanırsa bekliyor durumu kalabilir; otomatik yeniden deneme kuyruğu yoktur.

## Veri ve PWA

- 6 ders için günlük doğru, yanlış ve boş sayısı. Toplam = doğru + yanlış + boş. Deneme adı, sabit 90 soru sınırı ve net hesabı yoktur. Her sayı 0–9999 arası tam sayıdır; boş alanlar sıfır kabul edilir, tamamen boş kayıt reddedilir. Aynı güne ait kayıtlar günlük toplam altında gruplandırılır.
- Soru sayıları, tarih, telefon, onay ve CSRF sunucuda doğrulanır.
- Sonuçlar `data/tracker.sqlite3` içinde kalıcı tutulur. Tarayıcı oturumuna özel geçmiş ve Excel dışa aktarma sunulur. Aynı cihazı paylaşan kullanıcılar aynı tarayıcı geçmişini görür. Cihazlar arası hesap/eşitleme yoktur; çerezler silinirse geçmişe erişim kaybolur.
- Taslak ve iletişim alanları cihazın yerel depolamasında saklanır. Çevrimdışı giriş yapılabilir; kayıt ve bildirim için internet gerekir. Çevrimiçi olunca kullanıcı yeniden kaydeder; arka planda izinsiz otomatik gönderim yapılmaz.
- PWA kurulumu HTTPS veya localhost gerektirir. iPhone: Safari → Paylaş → Ana Ekrana Ekle. Android: Chrome → Uygulamayı yükle.
- `/qr` uygulama adresini açar. `PUBLIC_URL` dışarıdan erişilen HTTPS adresi olmalıdır. Localhost QR kodu başka telefonda bilgisayarı açmaz.
- Mevcut `data/student_tracker.xlsx` korunur; eski kayıtlar yeni oturumlara otomatik aktarılmaz.

## Yayına alma

`render.yaml`, kalıcı diskli **ücretli Starter** Render servisi tanımlar; bu çalışma sırasında dağıtım yapılmaz. `PUBLIC_URL`, WhatsApp ortam değişkenleri ve isteğe bağlı `TEACHER_PHONE` değerlerini Render üzerinden girin. Kalıcı disk `/var/data` konumundadır; düzenli yedekleyin. HTTPS ortamında `COOKIE_SECURE=1` kullanın. SQLite nedeniyle tek sunucu örneği kullanın; yatay ölçek için PostgreSQL ve paylaşımlı oturum/rate-limit altyapısı gerekir.

### Vercel

1. GitHub reposunu Vercel'e aktarın; kök dizin proje kökü, framework Flask. Vercel kökteki `app.py` içindeki `app` nesnesini otomatik algılar; özel build/output komutu gerekmez.
2. Vercel Storage / Marketplace üzerinden Neon veya Supabase PostgreSQL bağlayın. Bağlantı dizesini `DATABASE_URL` ortam değişkenine ekleyin (`POSTGRES_URL` da desteklenir). Sağlayıcının SSL içeren bağlantı dizesini kullanın.
3. Uzun ve rastgele, kalıcı `SECRET_KEY` tanımlayın. Örnek üretim: `python -c "import secrets; print(secrets.token_hex(32))"`.
4. `PUBLIC_URL` değerini uygulamanın HTTPS adresi yapın. Oturum çerezleri Vercel'de otomatik olarak Secure olur.
5. WhatsApp için `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_DAILY_CONTENT_SID` ve isteğe bağlı `TEACHER_PHONE` ekleyin; ardından Deploy/Redeploy yapın.

Vercel'de DATABASE_URL veya SECRET_KEY eksikse uygulama açık bir yapılandırma hatasıyla durur; geçici SQLite dosyasına kayıt yapmaz. Tablo ilk veritabanı erişiminde oluşturulur. Yerel SQLite kayıtları PostgreSQL'e otomatik aktarılmaz. Önizleme ve üretim ortamları için ayrı veritabanları kullanın. PostgreSQL adaptörü taklit bağlantıyla test edildi; gerçek sunucu bağlantısı dağıtımda doğrulanmalıdır.

[Resmî Flask dağıtım rehberi](https://vercel.com/docs/frameworks/backend/flask) · [PostgreSQL bağlantısı](https://vercel.com/docs/postgres)

Kullanıcı hesabı ve genel spam koruması eklenmeden uygulamayı sınırsız kamuya açık bir WhatsApp gönderim servisi olarak işletmeyin; mevcut kayıt limiti tarayıcı oturumu başına günlük 20'dir.

## Test

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Testler geçici veritabanı ve taklit WhatsApp sağlayıcısı kullanır; gerçek mesaj göndermez.

Önceki deneme kayıtları veritabanında korunur; günlük soru geçmişine ve yeni Excel çıktısına dahil edilmez. Günlük taslaklar ayrı anahtarda tutulur; eski deneme taslakları otomatik olarak günlük kayda dönüştürülmez.

## Mobil kullanım

Soru giriş ekranı 320×568, 375×667 ve 390×844 boyutlarında klavye kapalıyken dikey kaydırmadan kullanılacak şekilde düzenlendi. Sayısal klavye açıkken alanlara erişmek için doğal sayfa kaydırması korunur. Öğrenci bilgileri, telefonlar ve paylaşım onayı Bilgilerim penceresinde saklanır; not ayrı pencereden eklenir. Sola/sağa kaydırarak veya alt menüden Soru gir → Raporlar → Günlüğüm ekranları arasında geçilir. Raporlar son 7 günün soru toplamlarını ve ders dağılımını gösterir.
