# 🚀 دليل نشر البوت - Advanced CID Bot

## 📋 المتطلبات الأساسية

### 🔑 البيانات المطلوبة:
- **Token البوت**: من @BotFather
- **عنوان محفظة USDT TRC20**: لاستقبال المدفوعات
- **PIDKEY API Key**: للحصول على CID
- **Admin IDs**: معرفات المديرين

---

## 🌐 خيارات الاستضافة

### 1️⃣ **VPS/السيرفر الخاص (الأفضل)**
```bash
# التحديث والتثبيت
sudo apt update && sudo apt upgrade -y
sudo apt install docker.io docker-compose git python3 python3-pip -y

# تحميل المشروع
git clone <repository-url>
cd advanced_bot

# إعداد متغيرات البيئة
cp .env.example .env
nano .env  # أدخل البيانات الحقيقية

# تشغيل البوت
docker-compose up -d
```

### 2️⃣ **Railway.app (سهل ومجاني)**
1. إنشاء حساب على [Railway.app](https://railway.app)
2. ربط GitHub Repository
3. إضافة متغيرات البيئة في Dashboard
4. Deploy تلقائي!

### 3️⃣ **Heroku**
```bash
# تثبيت Heroku CLI
heroku create advanced-cid-bot
heroku config:set TELEGRAM_BOT_TOKEN=your_token
heroku config:set USDT_TRC20_ADDRESS=your_wallet
heroku config:set PIDKEY_API_KEY=your_key
heroku config:set ADMIN_IDS=your_admin_id
git push heroku main
```

### 4️⃣ **DigitalOcean App Platform**
1. إنشاء App من GitHub
2. اختيار `Dockerfile` deployment
3. إعداد Environment Variables
4. Launch!

---

## ⚙️ إعداد متغيرات البيئة

### ملف `.env`:
```env
TELEGRAM_BOT_TOKEN=7687105300:AAGGYs9L7DVmRZrDftLc-8S7afL_EFmUPpM
ADMIN_IDS=5255786759
USDT_TRC20_ADDRESS=عنوان_محفظة_USDT_الحقيقي
PIDKEY_API_KEY=KaT8lsFLRhYKng6uaReScSptI
```

---

## 🐳 نشر باستخدام Docker

### التشغيل السريع:
```bash
# بناء الصورة
docker build -t advanced-cid-bot .

# تشغيل الحاوية
docker run -d \
  --name advanced-cid-bot \
  --restart unless-stopped \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/advanced_cid_bot.db:/app/advanced_cid_bot.db \
  --env-file .env \
  advanced-cid-bot
```

### استخدام docker-compose:
```bash
docker-compose up -d
```

---

## 📊 مراقبة البوت

### فحص الحالة:
```bash
# حالة الحاوية
docker ps

# السجلات
docker logs advanced-cid-bot -f

# إحصائيات الأداء
docker stats advanced-cid-bot
```

### إعادة التشغيل:
```bash
docker-compose restart
# أو
docker restart advanced-cid-bot
```

---

## 🔧 استكشاف الأخطاء

### مشاكل شائعة:

**1. مشكلة Tesseract OCR:**
```bash
# تحقق من تثبيت tesseract
docker exec advanced-cid-bot tesseract --version
```

**2. مشكلة قاعدة البيانات:**
```bash
# فحص قاعدة البيانات
docker exec advanced-cid-bot python simple_db_viewer.py
```

**3. مشكلة API:**
```bash
# فحص الاتصال
docker exec advanced-cid-bot python -c "import requests; print(requests.get('https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe').json())"
```

---

## 💡 نصائح الأمان

1. **🔐 لا تشارك التوكن أو API Keys**
2. **🛡️ استخدم Firewall على السيرفر**
3. **📱 فعل Two-Factor Authentication**
4. **💾 اعمل نسخ احتياطية من قاعدة البيانات**
5. **🔄 حدث النظام باستمرار**

---

## 📈 التحسينات الاختيارية

### إضافة SSL/TLS:
```bash
sudo apt install certbot
sudo certbot --nginx -d yourdomain.com
```

### إعداد المراقبة:
```bash
# إضافة Prometheus monitoring
docker run -d --name prometheus prom/prometheus
```

### النسخ الاحتياطي التلقائي:
```bash
# Cron job لنسخ قاعدة البيانات
0 2 * * * cp /path/to/advanced_cid_bot.db /backup/
```

---

## 🎯 التشغيل الإنتاجي

### قبل النشر:
- ✅ اختبر جميع الوظائف محلياً
- ✅ تأكد من عنوان المحفظة الصحيح
- ✅ اختبر API Keys
- ✅ راجع إعدادات الأمان

### بعد النشر:
- 📊 راقب السجلات أول 24 ساعة
- 🧪 اختبر جميع الوظائف
- 👥 أضف المستخدمين تدريجياً
- 📈 راقب الأداء والاستخدام

---

## 📞 الدعم الفني

عند مواجهة مشاكل، تحقق من:
1. **السجلات**: `docker logs advanced-cid-bot`
2. **متغيرات البيئة**: تأكد من صحتها
3. **الاتصال بالإنترنت**: اختبر APIs
4. **مساحة القرص**: تأكد من وجود مساحة كافية

---

✨ **البوت جاهز للعمل! استمتع بخدمة CID المتقدمة** ✨
