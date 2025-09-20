# 🚀 دليل النشر الشامل - Advanced CID Bot

## 📋 المتطلبات الأساسية

### ✅ **متغيرات البيئة المطلوبة:**
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=7687105300:AAGGYs9L7DVmRZrDftLc-8S7afL_EFmUPpM
ADMIN_IDS=5255786759

# Payment Configuration  
USDT_TRC20_ADDRESS=TFHirK1z8VTss4oDLeyQJ4JwQceMembFrQ

# API Keys
PIDKEY_API_KEY=KaT8lsFLRhYKng6uaReScSptI

# Google Cloud Vision API
GOOGLE_CLOUD_CREDENTIALS_PATH=./seismic-octane-471921-n4-1dca51f146a8.json
```

---

## 🎯 خيارات النشر

### 1. **Railway (الأسهل والمجاني)** ⭐
```bash
# 1. انشئ حساب على Railway.app
# 2. اربط حسابك بـ GitHub
# 3. ارفع المشروع إلى GitHub
# 4. اربط المشروع بـ Railway
# 5. أضف متغيرات البيئة
```

**الخطوات:**
1. اذهب إلى [Railway.app](https://railway.app)
2. اضغط "Deploy Now" → "Deploy from GitHub repo"
3. اختر المشروع
4. في Variables أضف جميع متغيرات البيئة
5. أرفع ملف `seismic-octane-471921-n4-1dca51f146a8.json`

### 2. **Heroku** 
```bash
# تثبيت Heroku CLI
# heroku login
# heroku create your-bot-name
# git push heroku main
```

### 3. **VPS/Cloud Server**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip
git clone your-repo
cd advanced_bot
pip3 install -r requirements.txt
python3 bot.py
```

### 4. **Docker**
```bash
# تشغيل مباشر
docker build -t cid-bot .
docker run -d --name cid-bot cid-bot

# أو استخدام docker-compose
docker-compose up -d
```

---

## 🗄️ قاعدة البيانات

### **SQLite (افتراضي - مدمج)**
- ✅ **تعمل فوراً** - لا تحتاج إعداد
- ✅ **ملف واحد**: `advanced_cid_bot.db`
- ✅ **النسخ الاحتياطي**: انسخ الملف
- ⚠️ **محدودة للاستخدام المتوسط**

### **PostgreSQL (للإنتاج)**
```env
# في .env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### **MySQL**
```env
# في .env  
DATABASE_URL=mysql://user:pass@host:3306/dbname
```

---

## 💳 نظام الدفع - مضمون 100%

### **1. Binance USDT TRC20**
```env
USDT_TRC20_ADDRESS=TFHirK1z8VTss4oDLeyQJ4JwQceMembFrQ
```
- ✅ **التحقق التلقائي** عبر Tronscan API
- ✅ **مطابقة المبلغ والعنوان**
- ✅ **حفظ TXID للمراجعة**

### **2. نظام الكوبونات**
```python
# توليد كوبونات من لوحة الأدمن
/admin → إدارة الكوبونات → توليد كوبونات
```
- ✅ **أكواد فريدة**
- ✅ **تحديد قيمة CID**
- ✅ **استخدام واحد لكل كود**

---

## 🔒 الأمان والاستقرار

### **حماية قاعدة البيانات:**
```python
# نسخ احتياطي تلقائي كل 24 ساعة
# معالجة أخطاء SQLAlchemy
# التحقق من صحة البيانات
```

### **حماية المدفوعات:**
```python
# التحقق المضاعف من TXID
# مطابقة المبلغ الدقيق
# منع المدفوعات المكررة
# سجل كامل للمعاملات
```

### **مراقبة الأخطاء:**
```python
# نظام logging شامل
# معالجة استثناءات شاملة
# إعادة تشغيل تلقائي عند الأخطاء
```

---

## 📊 مراقبة الأداء

### **Logs مهمة للمراقبة:**
```bash
# فحص السجلات
tail -f logs/bot_*.log

# البحث عن أخطاء
grep "ERROR" logs/bot_*.log

# مراقبة المدفوعات
grep "Transaction created" logs/bot_*.log
```

### **إحصائيات مهمة:**
- عدد المستخدمين الجدد يومياً
- عدد المعاملات المكتملة
- معدل نجاح OCR
- رصيد الكوبونات المتاح

---

## 🛠️ الصيانة الدورية

### **يومياً:**
- فحص السجلات للأخطاء
- مراقبة رصيد محفظة USDT
- التأكد من عمل APIs

### **أسبوعياً:**
- نسخ احتياطي لقاعدة البيانات
- مراجعة إحصائيات الاستخدام
- تحديث أسعار الباقات إذا لزم

### **شهرياً:**
- تحديث dependencies
- مراجعة أمان الخادم
- تحليل أداء البوت

---

## 🚨 استكشاف الأخطاء

### **البوت لا يستجيب:**
```bash
# فحص العملية
ps aux | grep python
# فحص السجلات
tail -f logs/bot_*.log
# إعادة تشغيل
python3 bot.py
```

### **أخطاء قاعدة البيانات:**
```bash
# فحص ملف قاعدة البيانات
ls -la advanced_cid_bot.db
# فحص الاتصال
python3 -c "from database.database import db; print('DB OK')"
```

### **أخطاء المدفوعات:**
```bash
# فحص API Keys
echo $PIDKEY_API_KEY
# فحص اتصال Tronscan
curl "https://apilist.tronscan.org/api/transaction-info?hash=test"
```

---

## 📞 الدعم الفني

### **معلومات مهمة للدعم:**
- نسخة Python: `3.11+`
- نسخة Bot: `v2.0`
- آخر تحديث: `2025-09-13`

### **ملفات مهمة للنسخ الاحتياطي:**
```
advanced_cid_bot.db          # قاعدة البيانات
seismic-octane-*.json        # مفاتيح Google Vision
.env                         # متغيرات البيئة
logs/                        # السجلات
```

---

## ✅ **ضمان العمل 100%**

🎯 **جميع الأنظمة مختبرة ومضمونة:**
- ✅ Telegram Bot API
- ✅ Google Vision OCR  
- ✅ PIDKEY/CIDMS API
- ✅ Tronscan Payment Verification
- ✅ SQLite Database
- ✅ Admin Panel
- ✅ Voucher System

**البوت جاهز للإنتاج التجاري! 🚀**
