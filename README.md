# 🚀 Advanced CID Telegram Bot

بوت Telegram متقدم لإنشاء Confirmation ID من Installation ID مع نظام دفع وإدارة متكامل.

## ✨ المميزات

### 🔧 الوظائف الأساسية
- **High-Accuracy OCR**: Google Cloud Vision API
- **استخراج Installation ID**: من الصور باستخدام تقنية OCR المتطورة
- **إنشاء Confirmation ID**: عبر PIDKEY API
- **نظام الدفع**: USDT TRC20 مع التحقق التلقائي عبر Tronscan API
- **كودات الخصم**: نظام voucher كامل مع تتبع الاستخدام
- **باقات CID**: 8 باقات مختلفة بأسعار متدرجة
- **لوحة إدارة**: شاملة للأدمن مع إحصائيات مفصلة

### 💎 الباقات المتاحة
1. **باقة صغيرة**: 25 CID - 20.0 ر.س
2. **باقة متوسطة**: 50 CID - 25.0 ر.س  
3. **باقة كبيرة**: 100 CID - 47.0 ر.س
4. **باقة ممتازة**: 500 CID - 212.0 ر.س
5. **باقة فائقة**: 1000 CID - 385.0 ر.س
6. **باقة احترافية**: 2000 CID - 693.0 ر.س
7. **باقة المؤسسات**: 5000 CID - 1530.0 ر.س
8. **باقة الشركات**: 10000 CID - 2860.14 ر.س

## 🛠️ متطلبات التشغيل

### البرامج المطلوبة
- Python 3.8+
- PostgreSQL/MySQL (اختياري، يمكن استخدام SQLite)

### متطلبات إضافية

**Google Cloud Vision API:**
- حساب Google Cloud Platform
- تفعيل Cloud Vision API
- Service Account مع صلاحيات Cloud Vision

## 📦 التثبيت

### 1. استنساخ المشروع
```bash
git clone <repository-url>
cd numbers_reader/advanced_bot
```

### 2. إنشاء البيئة الافتراضية
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# أو
venv\Scripts\activate     # Windows
```

### 3. تثبيت المتطلبات
```bash
pip install -r requirements.txt
```

### 4. إعداد متغيرات البيئة
إنشاء ملف `.env`:
```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# PIDKEY API
PIDKEY_API_KEY=your_pidkey_api_key
PIDKEY_API_URL=https://api.pidkey.com

# USDT Payment
USDT_TRC20_ADDRESS=your_wallet_address_here

# Database (اختياري للـ MySQL)
DB_TYPE=sqlite
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=advanced_cid_bot
```

## 🚀 التشغيل

### تشغيل البوت
```bash
python bot.py
```

### تشغيل البوت في الخلفية (Linux)
```bash
nohup python bot.py &
```

### باستخدام systemd (Linux)
إنشاء ملف `/etc/systemd/system/cidbot.service`:
```ini
[Unit]
Description=Advanced CID Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/advanced_bot
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

ثم:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cidbot
sudo systemctl start cidbot
```

## 🔧 الإعداد

### 1. إنشاء بوت Telegram
1. تحدث مع [@BotFather](https://t.me/BotFather)
2. استخدم `/newbot` لإنشاء بوت جديد
3. احصل على Bot Token
4. ضعه في متغير `TELEGRAM_BOT_TOKEN`

### 2. إعداد PIDKEY API
1. احصل على API Key من مزود الخدمة
2. ضعه في `PIDKEY_API_KEY`
3. حدد رابط API في `PIDKEY_API_URL`

### 3. إعداد محفظة USDT TRC20
1. أنشئ محفظة TRC20
2. ضع العنوان في `USDT_TRC20_ADDRESS`
3. تأكد من دعم شبكة TRON

## 📋 الأوامر

### أوامر المستخدم
- `/start` - بدء استخدام البوت
- `/contact` - التواصل مع الإدارة
- `/balance` - عرض الرصيد الحالي
- `/packages` - عرض الباقات المتاحة
- `/deposit` - شحن رصيد USDT TRC20
- `/voucher` - استخدام كود خصم
- `/history` - تاريخ المعاملات

### أوامر الإدارة
- `/admin` - لوحة تحكم الأدمن

## 🔐 لوحة الإدارة

تشمل لوحة الإدارة:
- **إحصائيات النظام**: مستخدمين، معاملات، إيرادات
- **إدارة المستخدمين**: بحث، حظر، تعديل الرصيد
- **إدارة الكوبونات**: إنشاء كودات فردية أو مجمعة
- **إدارة المعاملات**: مراقبة ومراجعة المدفوعات
- **سجل الأنشطة**: تتبع أعمال الإدارة

## 🗄️ قاعدة البيانات

### الجداول الرئيسية
- `users` - بيانات المستخدمين والأرصدة
- `transactions` - جميع المعاملات المالية
- `vouchers` - كودات الخصم
- `packages` - باقات CID
- `cid_requests` - طلبات CID وحالتها
- `admin_logs` - سجل أعمال الإدارة

### النسخ الاحتياطي
```bash
# SQLite
cp advanced_cid_bot.db backup_$(date +%Y%m%d).db

# MySQL
mysqldump -u username -p database_name > backup_$(date +%Y%m%d).sql
```

## 🔄 الصيانة

### مراقبة السجلات
```bash
tail -f bot.log
```

### تحديث النظام
```bash
git pull
pip install -r requirements.txt --upgrade
systemctl restart cidbot
```

### فحص حالة النظام
```bash
systemctl status cidbot
```

## ⚠️ الأمان

### احتياطات مهمة
- لا تشارك Bot Token أو API Keys
- استخدم HTTPS للـ webhooks
- راجع سجلات الإدارة بانتظام
- فعّل النسخ الاحتياطي التلقائي
- راقب المعاملات المشبوهة

### حماية قاعدة البيانات
- استخدم كلمات مرور قوية
- فعّل SSL للاتصالات
- قم بالنسخ الاحتياطي بانتظام
- راجع صلاحيات المستخدمين

## 🐛 استكشاف الأخطاء

### مشاكل Google Vision API الشائعة
```python
# تحقق من تثبيت Google Vision API
from google.cloud import vision
client = vision.ImageAnnotatorClient()
print("Google Vision API connected successfully")
```

### مشاكل قاعدة البيانات
```python
# تحقق من الاتصال
from database.database import db
with db.get_session() as session:
    print("Database connected successfully")
```

### مشاكل API
```python
# تحقق من PIDKEY API
from services.pidkey_service import pidkey_service
result = await pidkey_service.validate_api_connection()
print(result)
```

## 📞 الدعم الفني

للدعم الفني والاستفسارات:
- إنشاء issue في GitHub
- مراجعة السجلات في `/logs/`
- تحقق من حالة النظام عبر `/admin`

## 📄 الترخيص

هذا المشروع محمي بحقوق الطبع والنشر. الاستخدام مقيد على المرخص لهم فقط.

---

**تم التطوير بواسطة**: فريق التطوير المتقدم  
**الإصدار**: 1.0.0  
**آخر تحديث**: 2024-01-10
