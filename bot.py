"""
Advanced CID Telegram Bot - Main Bot File
Integrates all services: OCR, Payments, Vouchers, Packages, Admin Panel
"""

import logging
import asyncio
import os
import tempfile
import re
from typing import Optional, Dict
import sys
import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
from telegram.error import TelegramError

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our services
from config import config
from database.database import db
from database.models import User, Transaction, CIDRequest, Voucher
from services.payment_service import payment_service
from services.package_service import package_service
from services.voucher_service import voucher_service
from services.pidkey_service import pidkey_service
from admin_panel import AdminPanel
from bot_admin_handlers import AdminHandlers
from setup_logging import setup_logging, get_logger

# Configure logging
logger = setup_logging()

# Conversation states
WAITING_FOR_TXID = 1
WAITING_FOR_VOUCHER = 2
WAITING_FOR_IID_IMAGE = 3
WAITING_FOR_IID_TEXT = 4

class AdvancedCIDBot:
    """Main bot class"""
    
    def __init__(self):
        # Initialize Google Vision API first
        self.vision_service = None
        credentials_path = os.getenv('GOOGLE_CLOUD_CREDENTIALS_PATH', './seismic-octane-471921-n4-1dca51f146a8.json')
        
        if os.path.exists(credentials_path):
            try:
                from services.google_vision_service import GoogleVisionService
                self.vision_service = GoogleVisionService(credentials_path)
                logger.info("🚀 Google Vision API initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Vision: {e}")
        
        # Check Vision API availability (optional)
        if not self.vision_service:
            logger.warning("⚠️ Google Vision API not available - Using pytesseract fallback")
            logger.info("📝 Using pytesseract for OCR processing")
        else:
            logger.info("✨ Using Google Vision API for OCR")
            
        self.application = None
        # Initialize database and admin panel
        self.db = db
        self.admin_panel = AdminPanel(db)
        self.admin_handlers = AdminHandlers(self)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        welcome_text = f"""🎉 أهلاً وسهلاً {first_name} في بوت Advanced CID!

⚡ أسرع طريقة للبدء:
🔹 تحقق من رصيدك الحالي
🔹 اشحن رصيدك أو اشتري باقة
🔹 احصل على Confirmation ID فوراً

💎 ميزات ذكية حصرية:
📱 أرسل صورة Installation ID → استخراج تلقائي فوري
🎫 أرسل كود الشحن → تفعيل تلقائي في ثواني

🚀 جاهز للبدء؟ اختر من القائمة أدناه:"""
        
        # Create main navigation keyboard
        keyboard = [
            [InlineKeyboardButton("🔑 إنشاء CID فوري", callback_data="get_cid")],
            [InlineKeyboardButton("💳 شحن رصيد", callback_data="deposit"),
             InlineKeyboardButton("📦 باقات CID", callback_data="packages")],
            [InlineKeyboardButton("📊 رصيدي ومعلوماتي", callback_data="info"),
             InlineKeyboardButton("📋 تاريخ العمليات", callback_data="history")],
            [InlineKeyboardButton("🎫 كود شحن", callback_data="voucher"),
             InlineKeyboardButton("📞 دعم فني", callback_data="contact")]
        ]
        
        # Add admin button if user is admin
        if user_id in config.telegram.admin_ids:
            keyboard.append([InlineKeyboardButton("🔧 لوحة الإدارة", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command - show user info and balance"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        # Get user balance
        cid_balance, usd_balance = db.get_user_balance(user_id)
        
        # Get purchase history count
        history_count = len(db.get_user_transactions(user_id))
        
        info_text = f"""👤 معلومات حسابك
🆔 الاسم: {first_name}
📱 المعرف: @{username if username != 'غير محدد' else 'غير محدد'}
🔢 ID: `{user_id}`

💰 الرصيد الحالي:💎 CID: {cid_balance:,}
💵 USD: ${usd_balance:.2f}

📊 الإحصائيات:🛍️ المعاملات: {history_count}
⭐ الحالة: {'VIP' if cid_balance > 100 else 'عادي'}

━━━━━━━━━━━━━━━━━━━━━
✨ استخدم الأزرار للتنقل السريع:"""
        
        # Create info navigation keyboard
        keyboard = [
            [InlineKeyboardButton("🔑 إنشاء CID", callback_data="get_cid"),
             InlineKeyboardButton("💳 شحن رصيد", callback_data="deposit")],
            [InlineKeyboardButton("📦 شراء باقة", callback_data="packages"),
             InlineKeyboardButton("📋 تاريخ المعاملات", callback_data="history")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        
        # Add admin button if user is admin
        if user_id in config.telegram.admin_ids:
            keyboard.insert(-1, [InlineKeyboardButton("🔧 لوحة الإدارة", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(info_text, reply_markup=reply_markup)
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        user_id = update.effective_user.id
        cid_balance, usd_balance = db.get_user_balance(user_id)
        
        await update.message.reply_text(
            f"📊 رصيدك الحالي\n\n💎 CID: {cid_balance:,}\n💰 USD: ${usd_balance:.2f}\n\n━━━━━━━━━━━━━━━━━━━━━\n\n💡 لشحن الرصيد:\n🥇 /deposit - بايننس USDT TRC20\n🎫 /contact - طلب كوبون من الإدارة\n\n📦 لشراء CID: /packages"
        )
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        # Get purchase history
        history = package_service.format_purchase_history(user_id)
        
        await update.message.reply_text(history)
    
    async def get_cid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /get_cid command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        # Check if user has CID balance
        cid_balance, usd_balance = db.get_user_balance(user_id)
        
        if cid_balance <= 0:
            await update.message.reply_text(
                """❌ رصيد CID غير كافي                
🔋 رصيدك الحالي: 0 CID

💡 لشحن رصيدك:🥇 `/deposit` - شحن عبر بايننس USDT TRC20  
🎫 `/contact` - طلب كوبون من الإدارة
📦 `/packages` - شراء باقة CID

⚡ تحتاج إلى رصيد CID لاستخراج Confirmation ID""",
            )
            return
        
        instructions_text = f"""🔑 احصل على Confirmation ID

📋 رصيدك الحالي: {cid_balance:,} CID
💰 تكلفة العملية: 1 CID

📸 طريقة 1 - أرسل صورة:
• صور شاشة Microsoft Office
• تأكد من وضوح Installation ID
• سيتم استخراج الرقم تلقائياً
• ✨ يعمل في أي مكان بالبوت!

📝 طريقة 2 - أرسل النص:
• أرسل Installation ID مباشرة (63 رقم)
• يجب أن يكون الرقم مكتمل وصحيح

⚡ المعالجة فورية وآمنة في أي مكان!

🎯 الآن أرسل الصورة أو النص...

━━━━━━━━━━━━━━━━━━━━━
✨ استخدم الأزرار للتنقل:"""
        
        # Create get_cid navigation keyboard
        keyboard = [
            [InlineKeyboardButton("📊 معلوماتي", callback_data="info"),
             InlineKeyboardButton("📦 شراء باقة", callback_data="packages")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(instructions_text, reply_markup=reply_markup)
    
    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads for OCR processing"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        # Check if user has CID balance
        cid_balance, usd_balance = db.get_user_balance(user_id)
        
        if cid_balance <= 0:
            await update.message.reply_text(
                """❌ رصيد CID غير كافي                
🔋 رصيدك الحالي: 0 CID

💡 لشحن رصيدك:🥇 `/deposit` - شحن عبر بايننس USDT TRC20  
🎫 `/contact` - طلب كوبون من الإدارة
📦 `/packages` - شراء باقة CID

⚡ تحتاج إلى رصيد CID لاستخراج Confirmation ID""",
            )
            return
        
        try:
            # Show processing message
            processing_msg = await update.message.reply_text("🔄 جار معالجة الصورة واستخراج Installation ID...")
            
            # Download photo
            photo_file = await update.message.photo[-1].get_file()
            photo_path = f"temp_photo_{user_id}_{update.message.message_id}.jpg"
            await photo_file.download_to_drive(photo_path)
            
            # Extract Installation ID using Google Vision API with Tesseract fallback
            installation_id = ""
            vision_result = None
            tesseract_result = None
            
            # Try Google Vision API first
            if self.vision_service:
                vision_result = self.vision_service.extract_installation_id(photo_path)
                if vision_result['success']:
                    # Validate the Google Vision result
                    validation = self.vision_service.validate_installation_id(vision_result['installation_id'])
                    if validation['is_valid']:
                        installation_id = validation['cleaned_id']
                        logger.info(f"✅ Google Vision success: {vision_result['confidence']:.1%} confidence")
                    else:
                        logger.warning(f"❌ Google Vision result invalid: {', '.join(validation['issues'])}")
                        vision_result['success'] = False
                else:
                    logger.warning(f"❌ Google Vision failed: {vision_result['error']}")
            
            # Fallback to pytesseract if Google Vision failed or unavailable
            if not installation_id:
                logger.info("🔄 Trying pytesseract fallback...")
                try:
                    import pytesseract
                    from PIL import Image
                    import cv2
                    import numpy as np
                    
                    # Process image with OpenCV for better OCR
                    img = cv2.imread(photo_path)
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    
                    # Apply image processing for better OCR
                    gray = cv2.medianBlur(gray, 3)
                    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
                    
                    # Extract text using pytesseract
                    ocr_text = pytesseract.image_to_string(thresh, config='--psm 6 -c tessedit_char_whitelist=0123456789')
                    
                    # Extract 63-digit number
                    import re
                    numbers = re.findall(r'\d{50,}', ocr_text.replace(' ', '').replace('\n', ''))
                    
                    for num in numbers:
                        if len(num) >= 50:
                            installation_id = num[:63] if len(num) > 63 else num
                            logger.info(f"✅ Pytesseract success: extracted {len(installation_id)} digits")
                            break
                    
                    if not installation_id:
                        logger.warning("❌ Pytesseract: No valid installation ID found")
                        
                except Exception as e:
                    logger.error(f"❌ Pytesseract fallback failed: {e}")
            
            # Clean up temp file
            import os
            if os.path.exists(photo_path):
                os.remove(photo_path)
            
            if not installation_id or len(installation_id) < 50:
                await processing_msg.edit_text(
                    """❌ فشل في استخراج Installation ID
🔍 المشكلة المحتملة:• الصورة غير واضحة
• Installation ID غير مرئي بالكامل  
• إضاءة سيئة أو انعكاسات

💡 نصائح لصورة أفضل:• التقط صورة واضحة لشاشة Office
• تأكد من ظهور Installation ID كاملاً
• استخدم إضاءة جيدة
• تجنب الانعكاسات والظلال

🔧 للمساعدة: `/contact`""",
                    )
                return
            
            # Ensure exactly 63 digits
            installation_id = re.sub(r'[^0-9]', '', installation_id)
            if len(installation_id) > 63:
                installation_id = installation_id[:63]
            elif len(installation_id) < 63:
                # Pad with zeros if too short (rare case)
                installation_id = installation_id.ljust(63, '0')
            
            # Format Installation ID for display (groups of 7)
            formatted_id = '-'.join([installation_id[i:i+7] for i in range(0, len(installation_id), 7)])
            
            # Show extracted Installation ID to user first
            await processing_msg.edit_text(
                f"""✅ تم استخراج Installation ID بنجاح!
🆔 Installation ID:`{formatted_id}`

🔄 جار طلب Confirmation ID من خدمة Microsoft...
⏳ هذا قد يستغرق بضع ثوانٍ...""",
            )
            
            # Request CID from PIDKEY service
            success, message, confirmation_id = await pidkey_service.process_cid_request(user_id, installation_id)
            
            if success:
                # Balance already deducted in process_cid_request
                # confirmation_id is already returned directly
                
                # Get updated balance after CID deduction
                updated_cid_balance, updated_usd_balance = db.get_user_balance(user_id)
                
                await processing_msg.edit_text(
                    f"""✅ تم إنشاء Confirmation ID بنجاح!

🔑 Installation ID:
`{installation_id}`

🎯 Confirmation ID:
`{confirmation_id}`

⚡ تم خصم: 1 CID من رصيدك
💎 رصيدك الحالي: {updated_cid_balance:,} CID

⭐ نصيحة للتنشيط السريع في برامج أوفيس فقط:
🔄 اضغط رجوع ثم اختر الاتصال بالإنترنت لتنشيط فوري!

📞 للدعم: `/contact`""",
                    parse_mode='Markdown'
                    )
                
            else:
                await processing_msg.edit_text(
                    f"""❌ فشل في إنشاء Confirmation ID
🔍 Installation ID المستخرج:
```
{installation_id}
```

❌ السبب: {message}

🔧 الحلول المقترحة:• تحقق من صحة Installation ID
• جرب مرة أخرى بعد قليل
• تواصل مع الدعم الفني

📞 للمساعدة: `/contact`""",
                    )
                
        except Exception as e:
            logger.error(f"Error processing photo for user {user_id}: {e}")
            await update.message.reply_text(
                """❌ حدث خطأ في معالجة الصورة
🔧 حاول مرة أخرى أو تواصل مع الدعم الفني
📞 `/contact` للحصول على المساعدة""",
            )
    
    async def process_installation_id_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, installation_id: str):
        """Process Installation ID submitted as text"""
        user_id = update.effective_user.id
        
        # Check if user has CID balance
        cid_balance, usd_balance = db.get_user_balance(user_id)
        
        if cid_balance <= 0:
            await update.message.reply_text(
                """❌ رصيد CID غير كافي                
🔋 رصيدك الحالي: 0 CID

💡 لشحن رصيدك:
🥇 `/deposit` - شحن عبر بايننس USDT TRC20  
🎫 `/contact` - طلب كوبون من الإدارة
📦 `/packages` - شراء باقة CID

⚡ تحتاج إلى رصيد CID لاستخراج Confirmation ID""",
            )
            return
        
        try:
            # Show processing message
            processing_msg = await update.message.reply_text("🔄 جار معالجة Installation ID...")
            
            # Ensure exactly 63 digits
            installation_id = re.sub(r'[^0-9]', '', installation_id)
            if len(installation_id) > 63:
                installation_id = installation_id[:63]
            elif len(installation_id) < 63:
                # Pad with zeros if too short (rare case)
                installation_id = installation_id.ljust(63, '0')
            
            # Format Installation ID for display (groups of 7)
            formatted_id = '-'.join([installation_id[i:i+7] for i in range(0, len(installation_id), 7)])
            
            # Show extracted Installation ID to user first
            await processing_msg.edit_text(
                f"""✅ تم استقبال Installation ID بنجاح!
🆔 Installation ID:
`{formatted_id}`

🔄 جار طلب Confirmation ID من خدمة Microsoft...
⏳ هذا قد يستغرق بضع ثوانٍ...""",
            )
            
            # Request CID from PIDKEY service
            success, message, confirmation_id = await pidkey_service.process_cid_request(user_id, installation_id)
            
            if success:
                # Get updated balance after CID deduction
                updated_cid_balance, updated_usd_balance = db.get_user_balance(user_id)
                
                await processing_msg.edit_text(
                    f"""✅ تم إنشاء Confirmation ID بنجاح!

🔑 Installation ID:
`{installation_id}`

🎯 Confirmation ID:
`{confirmation_id}`

⚡ تم خصم: 1 CID من رصيدك
💎 رصيدك الحالي: {updated_cid_balance:,} CID

⭐ نصيحة للتنشيط السريع في برامج أوفيس فقط:
🔄 اضغط رجوع ثم اختر الاتصال بالإنترنت لتنشيط فوري!
📋 يعمل مع: Word • Excel • PowerPoint • Outlook

📞 للدعم: `/contact`""",
                    parse_mode='Markdown'
                )
                
            else:
                await processing_msg.edit_text(
                    f"""❌ فشل في إنشاء Confirmation ID
🔍 Installation ID المدخل:
```
{installation_id}
```

❌ السبب: {message}

🔧 الحلول المقترحة:
• تحقق من صحة Installation ID
• جرب مرة أخرى بعد قليل
• تواصل مع الدعم الفني

📞 للمساعدة: `/contact`""",
                )
                
        except Exception as e:
            logger.error(f"Error processing text Installation ID for user {user_id}: {e}")
            await update.message.reply_text(
                """❌ حدث خطأ في معالجة Installation ID
🔧 حاول مرة أخرى أو تواصل مع الدعم الفني
📞 `/contact` للحصول على المساعدة""",
            )

    async def packages_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /packages command - show payment method selection first"""
        
        keyboard = [
            [InlineKeyboardButton("💰 الدفع عبر Binance", callback_data="packages_binance")],
            [InlineKeyboardButton("🌐 الدفع عبر الموقع الإلكتروني", callback_data="packages_salla")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            """📦 شراء باقات CID

━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 اختر طريقة الدفع المفضلة لديك:

💰 الدفع عبر Binance
• USDT TRC20 - سريع وآمن
• تأكيد فوري للمعاملات

🌐 الدفع عبر الموقع الإلكتروني
• مدى • فيزا • ماستر كارد
• STC Pay""", 
            reply_markup=reply_markup
        )
    
    async def deposit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /deposit and /recharge commands"""
        user_id = update.effective_user.id
        
        # Check if amount specified in command
        args = context.args
        amount = None
        
        if args:
            try:
                amount = float(args[0])
                if amount <= 0:
                    await update.message.reply_text(
                        "❌ مبلغ غير صحيح\n\nاستخدم: `/recharge 15.50` أو `/deposit 20`",
                            )
                    return
            except ValueError:
                await update.message.reply_text(
                    "❌ مبلغ غير صحيح\n\nاستخدم: `/recharge 15.50` أو `/deposit 20`",
                    )
                return
        
        # If no amount specified, suggest common amounts or show user's balance deficit
        if not amount:
            # Get user's current balance
            cid_balance, usd_balance = db.get_user_balance(user_id)
            
            # Show options for common recharge amounts
            keyboard = [
                [InlineKeyboardButton("💵 $5", callback_data="recharge_5"),
                 InlineKeyboardButton("💵 $10", callback_data="recharge_10")],
                [InlineKeyboardButton("💵 $20", callback_data="recharge_20"),
                 InlineKeyboardButton("💵 $50", callback_data="recharge_50")],
                [InlineKeyboardButton("✏️ مبلغ مخصص", callback_data="recharge_custom")],
                [InlineKeyboardButton("🌐 الدفع عبر الموقع", url="https://tf3eel.com/ar/TelegramCID")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"""💳 شحن الرصيد

💰 رصيدك الحالي: ${usd_balance:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 اختر مبلغ الشحن:
• للمبالغ المخصصة: `/recharge 15.75`
• أو اختر من الأزرار أدناه""",
                reply_markup=reply_markup
            )
            return
        
        # Check minimum amount
        if amount < 1.0:
            await update.message.reply_text(
                f"❌ المبلغ أقل من الحد الأدنى\n\n💡 الحد الأدنى للشحن: $1.00\nالمبلغ المطلوب: ${amount:.2f}"
            )
            return
        
        # Show payment info for specified amount
        deposit_info = payment_service.format_payment_info(amount)
        
        keyboard = [
            [InlineKeyboardButton("💰 تأكيد الدفع", callback_data=f"confirm_payment_{amount}")],
            [InlineKeyboardButton("🌐 الدفع عبر الموقع", url="https://tf3eel.com/ar/TelegramCID")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            deposit_info,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def voucher_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /voucher command"""
        await update.message.reply_text(
            """🎫 استخدام كود الشحن

📋 أرسل كود الشحن الآن:

✨ **نصيحة ذكية:** يمكنك إرسال كود الشحن في أي مكان بالبوت وسأتعرف عليه تلقائياً!

💡 إذا لم يكن لديك كود شحن:
• تواصل مع الإدارة لشراء كود: /contact
• أو اشحن مباشرة عبر بايننس: /deposit"""
        )
        return WAITING_FOR_VOUCHER
    
    async def handle_voucher_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voucher code input"""
        voucher_code = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Show processing message
        processing_msg = await update.message.reply_text("🔄 جار التحقق من كود الشحن...")
        
        # Redeem voucher
        success, message, voucher = voucher_service.redeem_voucher(voucher_code, user_id)
        
        await processing_msg.delete()
        
        if success:
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
        
        return ConversationHandler.END
    
    async def buy_package_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, package_id: int):
        """Handle /buy1, /buy2, etc. commands"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        # Get package info
        package = package_service.get_package_by_id(package_id)
        if not package:
            await update.message.reply_text("❌ الباقة غير موجودة")
            return
        
        # Check user balance
        cid_balance, usd_balance = db.get_user_balance(user_id)
        
        if usd_balance < package['price_usd']:
            needed = package['price_usd'] - usd_balance
            await update.message.reply_text(
                f"""❌ رصيد غير كافي                
💰 رصيدك الحالي: ${usd_balance:.2f}
💵 المطلوب: ${package['price_usd']:.2f}
📊 تحتاج إضافة: ${needed:.2f}

💡 لشحن الرصيد:💳 `/deposit` - بايننس USDT TRC20
🎫 `/contact` - كوبون من الإدارة"""
            )
            return
        
        # Process purchase
        success, message, transaction_id = package_service.purchase_package(user_id, package_id)
        
        if success:
            new_cid, new_usd = db.get_user_balance(user_id)
            await update.message.reply_text(
                f"""✅ تم شراء الباقة بنجاح!

📦 الباقة: {package['name']}
💎 CID المضافة: {package['cid_amount']:,}
💰 المبلغ المدفوع: ${package['price_usd']:.2f}

📊 رصيدك الجديد:
💎 CID: {new_cid:,}
💵 USD: ${new_usd:.2f}

🎯 جاهز للحصول على Confirmation ID؟ استخدم /get_cid"""
            )
        else:
            await update.message.reply_text(f"❌ {message}")
    
    async def text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (Installation ID or voucher codes)"""
        text = update.message.text.strip()
        user_id = update.effective_user.id
        user_data = context.user_data
        
        # Check for admin input first
        waiting_for = user_data.get('waiting_for')
        if waiting_for in ['admin_voucher_count', 'admin_add_balance', 'admin_subtract_balance', 
                          'voucher', 'txid', 'admin_message', 'contact_message_manual']:
            await self.handle_text_input(update, context)
            return
        
        # Smart text recognition - check voucher codes first (higher priority)
        if self.is_voucher_code_format(text):
            await self.process_voucher_code(update, context, text)
            return
        
        # Check if it's a potential Installation ID (63 digits)
        digits_only = ''.join(c for c in text if c.isdigit())
        
        if len(digits_only) >= 50:
            # Treat as Installation ID
            await self.process_installation_id_text(update, context, digits_only)
        elif re.match(r'^\d+\.?\d*$', text):
            # Looks like a number (custom amount) - process as recharge directly
            try:
                amount = float(text)
                if amount < 1.0:
                    await update.message.reply_text(
                        f"❌ المبلغ أقل من الحد الأدنى\n\n💡 الحد الأدنى للشحن: $1.00\nالمبلغ المطلوب: ${amount:.2f}"
                    )
                    return
                
                # Show payment info for specified amount
                deposit_info = payment_service.format_payment_info(amount)
                
                keyboard = [
                    [InlineKeyboardButton("💰 تأكيد الدفع", callback_data=f"confirm_payment_{amount}")],
                    [InlineKeyboardButton("🌐 الدفع عبر الموقع", url="https://tf3eel.com/ar/TelegramCID")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    deposit_info,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
            except ValueError:
                await update.message.reply_text(
                    f"💰 مبلغ مخصص: ${text}\n"
                    f"📝 لشحن هذا المبلغ، استخدم: `/recharge {text}`\n\n"
                    "💡 أو اختر من الباقات الجاهزة: /packages"
                )
        else:
            await update.message.reply_text(
                """❓ غير مفهوم
🔤 إذا كان كود شحن: استخدم `/voucher`
🔢 إذا كان Installation ID: تأكد أنه 63 رقم
📸 أو أرسل صورة شاشة Office: للحصول على CID""",
            )

    async def handle_admin_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin input for balance operations and voucher generation"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        waiting_for = context.user_data.get('waiting_for')
        
        if not self.admin_panel.is_admin(user_id):
            return
        
        try:
            if waiting_for == 'admin_add_balance':
                await self.process_add_balance(update, context, text)
            elif waiting_for == 'admin_subtract_balance':
                await self.process_subtract_balance(update, context, text)
            elif waiting_for == 'admin_voucher_count':
                await self.process_voucher_generation(update, context, text)
        except Exception as e:
            logger.error(f"Error processing admin input: {e}")
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
        
        # Clear waiting state
        if 'waiting_for' in context.user_data:
            del context.user_data['waiting_for']

    async def process_add_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Process admin add balance request"""
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ خطأ في التنسيق\n\nالصيغة المطلوبة:\n`معرف_المستخدم CID_المراد_إضافته USD_المراد_إضافته`\n\nمثال: `123456789 100 10.5`",
            )
            return
        
        try:
            target_user_id = int(parts[0])
            cid_amount = int(parts[1])
            usd_amount = float(parts[2])
            
            # Add balance to user
            success = db.add_user_balance(target_user_id, cid_amount, usd_amount)
            
            if success:
                await update.message.reply_text(
                    f"""✅ تمت إضافة الرصيد بنجاح                    
👤 المستخدم: {target_user_id}
➕ مضاف: {cid_amount} CID + ${usd_amount}
📊 الرصيد الجديد: {db.get_user_balance(target_user_id)[0]:,} CID + ${db.get_user_balance(target_user_id)[1]:.2f}""",
                    )
                
                # Log the action
                logger.info(f"Admin {update.effective_user.id} added balance: {cid_amount} CID, ${usd_amount} to user {target_user_id}")
            else:
                await update.message.reply_text("❌ فشل في إضافة الرصيد - تأكد من صحة معرف المستخدم")
                
        except ValueError:
            await update.message.reply_text("❌ تأكد من صحة الأرقام المدخلة")

    async def process_subtract_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Process admin subtract balance request"""
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ خطأ في التنسيق\n\nالصيغة المطلوبة:\n`معرف_المستخدم CID_المراد_خصمه USD_المراد_خصمه`\n\nمثال: `123456789 50 5.0`",
            )
            return
        
        try:
            target_user_id = int(parts[0])
            cid_amount = int(parts[1])
            usd_amount = float(parts[2])
            
            # Subtract balance from user
            success = db.subtract_user_balance(target_user_id, cid_amount, usd_amount)
            
            if success:
                await update.message.reply_text(
                    f"""✅ تم خصم الرصيد بنجاح                    
👤 المستخدم: {target_user_id}
➖ مخصوم: {cid_amount} CID + ${usd_amount}
📊 الرصيد الجديد: {db.get_user_balance(target_user_id)[0]:,} CID + ${db.get_user_balance(target_user_id)[1]:.2f}""",
                    )
                
                # Log the action
                logger.info(f"Admin {update.effective_user.id} subtracted balance: {cid_amount} CID, ${usd_amount} from user {target_user_id}")
            else:
                await update.message.reply_text("❌ فشل في خصم الرصيد - تأكد من وجود رصيد كافي ومن صحة معرف المستخدم")
                
        except ValueError:
            await update.message.reply_text("❌ تأكد من صحة الأرقام المدخلة")

    async def process_voucher_generation_with_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE, count: int):
        """Process voucher generation with direct count from button"""
        try:
            query = update.callback_query
            await query.answer()
            
            if count <= 0 or count > 100:
                await query.edit_message_text("❌ عدد الكودات يجب أن يكون بين 1 و 100")
                return
            
            selected_package = context.user_data.get('selected_package')
            if not selected_package:
                await query.edit_message_text("❌ خطأ: لم يتم اختيار باقة")
                return
            
            # Generate voucher codes
            generated_codes = []
            admin_id = update.effective_user.id
            
            for _ in range(count):
                code = self.admin_handlers.generate_voucher_code()
                # Create voucher in database
                success, message, voucher = voucher_service.create_voucher(
                    cid_amount=selected_package['cid_amount'],
                    usd_amount=selected_package['price_usd'],
                    admin_id=admin_id,
                    custom_code=code
                )
                if success:
                    generated_codes.append(code)
                else:
                    logger.error(f"Failed to create voucher: {message}")
                    # Try with auto-generated code
                    success2, message2, voucher2 = voucher_service.create_voucher(
                        cid_amount=selected_package['cid_amount'],
                        usd_amount=selected_package['price_usd'],
                        admin_id=admin_id
                    )
                    if success2 and voucher2:
                        generated_codes.append(voucher2.code)
            
            # Send codes in chunks to avoid message limits
            if generated_codes:
                codes_text = f"""🎫 تم توليد {len(generated_codes)} كود بنجاح
📦 الباقة: {selected_package['name']}
💎 قيمة كل كود: {selected_package['cid_amount']:,} CID

الأكواد المولدة:"""
                
                # Split codes into groups of 5 for better display
                for i in range(0, len(generated_codes), 5):
                    chunk = generated_codes[i:i+5]
                    chunk_text = codes_text + "\n"
                    
                    # Add codes with numbers
                    for j, code in enumerate(chunk):
                        chunk_text += f"\n🎯 **كود {i+j+1}:** `{code}`"
                    
                    # Add copy instruction
                    chunk_text += f"\n\n💡 **نصيحة:** اضغط على الأكواد أعلاه لنسخها فوراً!"
                    
                    if i + 5 < len(generated_codes):
                        chunk_text += f"\n\n📄 الجزء {i//5 + 1} من {(len(generated_codes)-1)//5 + 1}"
                    
                    if i == 0:
                        await query.edit_message_text(chunk_text, parse_mode='Markdown')
                    else:
                        await query.message.reply_text(chunk_text, parse_mode='Markdown')
                
                # Log the action
                logger.info(f"Admin {admin_id} generated {len(generated_codes)} vouchers for package {selected_package['name']}")
            else:
                await query.edit_message_text("❌ فشل في توليد الكوبونات")
            
        except Exception as e:
            logger.error(f"Error in voucher generation: {e}")
            await query.edit_message_text(f"❌ خطأ: {str(e)}")
    
    async def process_voucher_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Process voucher generation request"""
        try:
            count = int(text)
            if count <= 0 or count > 100:
                await update.message.reply_text("❌ عدد الكودات يجب أن يكون بين 1 و 100")
                return
            
            selected_package = context.user_data.get('selected_package')
            if not selected_package:
                await update.message.reply_text("❌ خطأ: لم يتم اختيار باقة")
                return
            
            # Generate voucher codes
            generated_codes = []
            admin_id = update.effective_user.id
            
            for _ in range(count):
                code = self.admin_handlers.generate_voucher_code()
                # Create voucher in database
                success, message, voucher = voucher_service.create_voucher(
                    cid_amount=selected_package['cid_amount'],
                    usd_amount=selected_package['price_usd'],
                    admin_id=admin_id,
                    custom_code=code
                )
                if success:
                    generated_codes.append(code)
                else:
                    logger.error(f"Failed to create voucher: {message}")
                    # Try with auto-generated code
                    success2, message2, voucher2 = voucher_service.create_voucher(
                        cid_amount=selected_package['cid_amount'],
                        usd_amount=selected_package['price_usd'],
                        admin_id=admin_id
                    )
                    if success2 and voucher2:
                        generated_codes.append(voucher2.code)
            
            # Send codes in chunks to avoid message limits
            codes_text = f"""🎫 تم توليد {count} كود بنجاح
📦 الباقة: {selected_package['name']}
💎 قيمة كل كود: {selected_package['cid_amount']:,} CID

الأكواد المولدة:"""
            
            # Split codes into groups of 5 for better display
            for i in range(0, len(generated_codes), 5):
                chunk = generated_codes[i:i+5]
                chunk_text = codes_text + "\n"
                
                # Add codes with numbers
                for j, code in enumerate(chunk):
                    chunk_text += f"\n🎯 **كود {i+j+1}:** `{code}`"
                
                # Add copy instruction
                chunk_text += f"\n\n💡 **نصيحة:** اضغط على الأكواد أعلاه لنسخها فوراً!"
                
                if i + 5 < len(generated_codes):
                    chunk_text += f"\n\n📄 الجزء {i//5 + 1} من {(len(generated_codes)-1)//5 + 1}"
                
                await update.message.reply_text(chunk_text, parse_mode='Markdown')
            
            # Log the action
            logger.info(f"Admin {update.effective_user.id} generated {count} vouchers for package {selected_package['name']}")
            
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح")
    
    def is_voucher_code_format(self, text: str) -> bool:
        """Check if text looks like a voucher code"""
        # Clean the text
        clean_text = text.strip().upper()
        
        # Basic voucher code patterns:
        # 1. Between 6-20 chars
        # 2. Contains letters and/or numbers
        # 3. No spaces in middle
        # 4. Not purely numeric (to avoid confusion with Installation IDs)
        if len(clean_text) < 6 or len(clean_text) > 20:
            return False
            
        # Must contain at least some letters (not purely numeric)
        if clean_text.isdigit():
            return False
            
        # Should be alphanumeric with possibly some special chars like - or _
        if not re.match(r'^[A-Z0-9_-]+$', clean_text):
            return False
            
        # If it looks like an Installation ID pattern, reject
        digits_only = ''.join(c for c in clean_text if c.isdigit())
        if len(digits_only) >= 50:  # Too many digits, likely Installation ID
            return False
            
        return True
    
    async def process_voucher_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
        """Process voucher code redemption - works anywhere in the bot"""
        user_id = update.effective_user.id
        
        # Show processing message
        processing_msg = await update.message.reply_text("🔄 جار التحقق من كود الشحن...")
        
        # Try to redeem voucher
        success, message, voucher = voucher_service.redeem_voucher(code, user_id)
        
        await processing_msg.delete()
        
        if success:
            cid_balance, usd_balance = db.get_user_balance(user_id)
            await update.message.reply_text(
                f"""✅ تم استخدام كود الشحن بنجاح!
🎫 الكود: `{code}`
💰 رصيدك الجديد:
💎 CID: {cid_balance:,}
💵 USD: ${usd_balance:.2f}

🎯 جاهز للحصول على CID؟ استخدم `/get_cid`""",
            )
        else:
            await update.message.reply_text(f"❌ {message}")
    
    async def admin_add_balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to add balance to users"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in config.admin_ids:
            await update.message.reply_text("❌ غير مسموح")
            return
        
        try:
            args = context.args
            if len(args) < 3:
                await update.message.reply_text(
                    """📝 استخدام الأمر:

`/add_balance [user_id] [cid_amount] [usd_amount]`

مثال:
`/add_balance 123456789 50 10.00`""",
                    )
                return
            
            target_user_id = int(args[0])
            cid_amount = int(args[1])
            usd_amount = float(args[2])
            
            # Add balance
            db.update_user_balance(target_user_id, cid_amount=cid_amount, usd_amount=usd_amount)
            
            # Get new balance
            new_cid, new_usd = db.get_user_balance(target_user_id)
            
            await update.message.reply_text(
                f"""✅ تم إضافة الرصيد
👤 المستخدم: {target_user_id}
➕ مضاف: {cid_amount} CID + ${usd_amount}
📊 الرصيد الجديد: {new_cid:,} CID + ${new_usd:.2f}""",
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /contact command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        # Get available admins directly from database (exclude specific admin from support)
        all_admins = db.get_admin_users()
        admin_users = [admin for admin in all_admins if admin['telegram_id'] != 5255786759]  # Hide Almotasembellah from support
        
        if not admin_users:
            await update.message.reply_text(
                "❌ لا يوجد مديرون متاحون حالياً\n\nحاول مرة أخرى لاحقاً",
            )
            return
        
        # Show admins directly
        admin_list = "👥 **مديرو الموقع المتاحون:**\n\n"
        for i, admin in enumerate(admin_users, 1):
            admin_name = (
                admin.get('first_name') or 
                admin.get('username') or 
                f"مدير {admin['telegram_id']}"
            )
            admin_username = admin.get('username', 'غير متاح')
            admin_list += f"{i}. 👤 **{admin_name}**\n"
            if admin_username != 'غير متاح':
                admin_list += f"   📱 @{admin_username}\n"
            admin_list += f"   🆔 `{admin['telegram_id']}`\n\n"
        
        admin_list += """━━━━━━━━━━━━━━━━━━━━━
💡 **للتواصل المباشر:**
• انسخ اسم المستخدم وتواصل عبر تلجرام
• أو استخدم الرقم المعرف للتواصل

🎫 **للحصول على كوبون شحن:**
أرسل إثبات الدفع لأي من المديرين أعلاه"""
        
        await update.message.reply_text(admin_list, parse_mode='Markdown')
    
    async def handle_text_iid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text Installation ID input"""
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Check if it's a potential Installation ID (contains mostly digits)
        digits_only = ''.join(c for c in text if c.isdigit())
        
        if len(digits_only) >= 50:  # Potential Installation ID
            # Check if user has CID balance
            cid_balance, _ = db.get_user_balance(user_id)
            if cid_balance < 1:
                await update.message.reply_text(
                    "❌ رصيد CID غير كافي\n\nتحتاج إلى شراء باقة CID أولاً\n\nاستخدم `/packages` لعرض الباقات المتاحة",
                    )
                return
            
            # Show processing message
            processing_msg = await update.message.reply_text("🔄 جار معالجة Installation ID...")
            
            # Process CID request
            success, message, confirmation_id = await pidkey_service.process_cid_request(
                user_id, text
            )
            
            await processing_msg.delete()
            
            if success:
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ {message}")
    
    async def callback_query_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        # Handle admin callbacks  
        if data.startswith("admin_"):
            await self.admin_handlers.handle_admin_callback(update, context)
            return
        
        # Regular user callbacks
        if data == "main_menu":
            # Show main menu again
            welcome_text = f"""🚀 مرحباً مرة أخرى!
🎯 أسرع طريقة للبدء:1️⃣ شاهد رصيدك ومعلوماتك
2️⃣ اشحن رصيدك أو اشتري باقة
3️⃣ احصل على Confirmation ID

✨ استخدم الأزرار أدناه للتنقل السريع:"""
            
            keyboard = [
                [InlineKeyboardButton("🔑 إنشاء CID فوري", callback_data="get_cid")],
                [InlineKeyboardButton("💳 شحن رصيد", callback_data="deposit"),
                 InlineKeyboardButton("📦 باقات CID", callback_data="packages")],
                [InlineKeyboardButton("📊 رصيدي ومعلوماتي", callback_data="info"),
                 InlineKeyboardButton("📋 تاريخ العمليات", callback_data="history")],
                [InlineKeyboardButton("🎫 كود شحن", callback_data="voucher"),
                 InlineKeyboardButton("📞 دعم فني", callback_data="contact")]
            ]
            
            # Add admin button if user is admin
            if user_id in config.telegram.admin_ids:
                keyboard.append([InlineKeyboardButton("🔧 لوحة الإدارة", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(welcome_text, reply_markup=reply_markup)
        
        elif data == "info":
            # Show user info
            username = update.effective_user.username or "غير محدد"
            first_name = update.effective_user.first_name or "مستخدم"
            
            # Create user if not exists
            db.create_user(user_id, username, first_name)
            
            # Get user balance and history
            cid_balance, usd_balance = db.get_user_balance(user_id)
            history_count = len(db.get_user_transactions(user_id))
            
            info_text = f"""👤 معلومات حسابك
🆔 الاسم: {first_name}
📱 المعرف: @{username if username != 'غير محدد' else 'غير محدد'}
🔢 ID: `{user_id}`

💰 الرصيد الحالي:💎 CID: {cid_balance:,}
💵 USD: ${usd_balance:.2f}

📊 الإحصائيات:🛍️ المعاملات: {history_count}
⭐ الحالة: {'VIP' if cid_balance > 100 else 'عادي'}

━━━━━━━━━━━━━━━━━━━━━
✨ استخدم الأزرار للتنقل السريع:"""
            
            keyboard = [
                [InlineKeyboardButton("🔑 إنشاء CID", callback_data="get_cid"),
                 InlineKeyboardButton("💳 شحن رصيد", callback_data="deposit")],
                [InlineKeyboardButton("📦 شراء باقة", callback_data="packages"),
                 InlineKeyboardButton("📋 تاريخ المعاملات", callback_data="history")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]
            
            # Add admin button if user is admin
            if user_id in config.telegram.admin_ids:
                keyboard.insert(-1, [InlineKeyboardButton("🔧 لوحة الإدارة", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(info_text, reply_markup=reply_markup)
        
        elif data == "get_cid":
            # Show get_cid instructions
            cid_balance, _ = db.get_user_balance(user_id)
            
            if cid_balance <= 0:
                keyboard = [
                    [InlineKeyboardButton("💳 شحن الرصيد", callback_data="deposit"),
                     InlineKeyboardButton("📦 شراء باقة", callback_data="packages")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    """❌ رصيد CID غير كافي                    
🔋 رصيدك الحالي: 0 CID

💡 لشحن رصيدك:💳 شحن عبر بايننس USDT TRC20  
🎫 طلب كوبون من الإدارة
📦 شراء باقة CID

⚡ تحتاج إلى رصيد CID لاستخراج Confirmation ID

━━━━━━━━━━━━━━━━━━━━━
✨ استخدم الأزرار أدناه:""",
                                        reply_markup=reply_markup
                )
                return
            
            instructions_text = f"""🔑 احصل على Confirmation ID
📋 رصيدك الحالي: {cid_balance:,} CID
💰 تكلفة العملية: 1 CID

📸 طريقة 1 - أرسل صورة:• صور شاشة Microsoft Office
• تأكد من وضوح Installation ID
• سيتم استخراج الرقم تلقائياً

📝 طريقة 2 - أرسل النص:• انسخ Installation ID (63 رقم)
• أرسله كرسالة نصية
• مثال: `12345678901234567890123456789012345678901234567890123456789012`

🎯 الآن أرسل الصورة أو النص...
━━━━━━━━━━━━━━━━━━━━━
✨ استخدم الأزرار للتنقل:"""
            
            keyboard = [
                [InlineKeyboardButton("📊 معلوماتي", callback_data="info"),
                 InlineKeyboardButton("📦 شراء باقة", callback_data="packages")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(instructions_text, reply_markup=reply_markup)
        
        elif data == "contact":
            # Show contact info directly in callback
            user_id = update.effective_user.id
            username = update.effective_user.username or "غير محدد"
            first_name = update.effective_user.first_name or "مستخدم"
            
            # Create user if not exists
            db.create_user(user_id, username, first_name)
            
            # Get available admins directly from database (exclude specific admin from support)
            all_admins = db.get_admin_users()
            admin_users = [admin for admin in all_admins if admin['telegram_id'] != 5255786759]  # Hide Almotasembellah from support
            
            if not admin_users:
                await query.edit_message_text(
                    "❌ لا يوجد مديرون متاحون حالياً\n\nحاول مرة أخرى لاحقاً"
                )
                return
            
            # Show admins directly
            admin_list = "👥 **مديرو الموقع المتاحون:**\n\n"
            for i, admin in enumerate(admin_users, 1):
                admin_name = (
                    admin.get('first_name') or 
                    admin.get('username') or 
                    f"مدير {admin['telegram_id']}"
                )
                admin_username = admin.get('username', 'غير متاح')
                admin_list += f"{i}. 👤 **{admin_name}**\n"
                if admin_username != 'غير متاح':
                    admin_list += f"   📱 @{admin_username}\n"
                admin_list += f"   🆔 `{admin['telegram_id']}`\n\n"
            
            admin_list += """━━━━━━━━━━━━━━━━━━━━━
💡 **للتواصل المباشر:**
• انسخ اسم المستخدم وتواصل عبر تلجرام
• أو استخدم الرقم المعرف للتواصل

🎫 **للحصول على كوبون شحن:**
أرسل إثبات الدفع لأي من المديرين أعلاه

🏠 للعودة: /start"""
            
            await query.edit_message_text(admin_list, parse_mode='Markdown')
        
        elif data == "admin_panel":
            # Check if user is admin
            if user_id not in config.telegram.admin_ids:
                await query.edit_message_text(
                    "❌ غير مصرح لك بالوصول للوحة الإدارة",
                    )
                return
            
            # Show admin panel
            admin_text = """🔧 لوحة الإدارة
👑 مرحباً أيها الأدمن!
اختر العملية المطلوبة:

📊 إحصائيات - عرض بيانات النظام
👥 إدارة المستخدمين - البحث والتعديل
🎫 إدارة الكوبونات - إنشاء وحذف
💰 إدارة الأرصدة - إضافة وخصم
📋 سجل العمليات - مراجعة النشاطات
⚙️ إعدادات النظام - تكوين البوت

━━━━━━━━━━━━━━━━━━━━━
✨ استخدم الأزرار أدناه:"""
            
            keyboard = [
                [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
                 InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
                [InlineKeyboardButton("🎫 إدارة الكوبونات", callback_data="admin_vouchers"),
                 InlineKeyboardButton("💰 إدارة الأرصدة", callback_data="admin_balance")],
                [InlineKeyboardButton("📋 سجل العمليات", callback_data="admin_logs"),
                 InlineKeyboardButton("⚙️ إعدادات النظام", callback_data="admin_settings")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(admin_text, reply_markup=reply_markup)
        
        elif data == "deposit":
            # Get user's current balance
            cid_balance, usd_balance = db.get_user_balance(user_id)
            
            # Show options for common recharge amounts
            keyboard = [
                [InlineKeyboardButton("💵 $5", callback_data="recharge_5"),
                 InlineKeyboardButton("💵 $10", callback_data="recharge_10")],
                [InlineKeyboardButton("💵 $20", callback_data="recharge_20"),
                 InlineKeyboardButton("💵 $50", callback_data="recharge_50")],
                [InlineKeyboardButton("⚙️ مبلغ مخصص", callback_data="recharge_custom")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"""💳 شحن الرصيد
💰 رصيدك الحالي: ${usd_balance:.2f}

🎯 اختر مبلغ الشحن:• للمبالغ المخصصة: `/recharge 15.75`
• أو اختر من الأزرار أدناه""",
                                reply_markup=reply_markup
            )
        
        elif data == "voucher":
            await query.edit_message_text(
                "🎫 استخدام كود الشحن\n\nأرسل كود الشحن:",
            )
            context.user_data['waiting_for'] = 'voucher'
        
        elif data == "packages":
            keyboard = [
                [InlineKeyboardButton("💰 الدفع عبر Binance", callback_data="packages_binance")],
                [InlineKeyboardButton("🌐 الدفع عبر الموقع الإلكتروني", callback_data="packages_salla")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                """📦 شراء باقات CID

━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 اختر طريقة الدفع المفضلة لديك:

💰 الدفع عبر Binance
• USDT TRC20 - سريع وآمن
• تأكيد فوري للمعاملات

🌐 الدفع عبر الموقع الإلكتروني
• مدى • فيزا • ماستر كارد
• STC Pay""", 
                reply_markup=reply_markup
            )
        
        elif data == "packages_binance":
            try:
                packages_text = package_service.format_packages_list("usd")
                
                # Add purchase buttons
                keyboard = [
                    [InlineKeyboardButton(f"📦 باقة {i} - {pkg['cid_amount']} CID", callback_data=f"buy_{pkg['id']}")]
                    for i, pkg in enumerate(package_service.get_all_packages(), 1)
                ]
                keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    packages_text, 
                    reply_markup=reply_markup
                )
            except Exception as e:
                await query.edit_message_text(
                    "❌ حدث خطأ في جلب الباقات\nحاول مرة أخرى"
                )
        
        elif data == "packages_salla":
            keyboard = [
                [InlineKeyboardButton("🌐 فتح الموقع الإلكتروني", url="https://tf3eel.com/ar/TelegramCID")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                """🌐 الدفع عبر الموقع الإلكتروني

━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 طرق الدفع المتاحة:
• مدى
• فيزا 
• ماستر كارد
• STC Pay

🌐 اضغط على الزر أدناه لفتح الموقع""",
                reply_markup=reply_markup
            )
        
        elif data == "history":
            try:
                # Get transactions directly from database
                cid_balance, usd_balance = db.get_user_balance(user_id)
                transactions = db.get_user_transactions(user_id, limit=10)
                
                if not transactions:
                    history_text = "📝 لا يوجد تاريخ شراء"
                else:
                    history_text = "📋 تاريخ مشترياتك:\n\n"
                    for i, tx in enumerate(transactions, 1):
                        date_str = tx['created_at'].strftime('%Y-%m-%d %H:%M') if tx['created_at'] else 'غير محدد'
                        history_text += f"{i}. 💎 CID: {tx['amount_cid']:,}\n"
                        history_text += f"   💰 المبلغ: {abs(tx['amount_usd']):.2f} USD\n"
                        history_text += f"   📅 التاريخ: {date_str}\n\n"
                
                # Add back button
                keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="info")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    history_text, 
                                        reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"History error: {e}")
                await query.edit_message_text(
                    "📝 لا يوجد تاريخ مشتريات حتى الآن\n\n🔙 استخدم الأزرار للعودة",
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="info")]])
                )
        
        elif data.startswith("buy_"):
            try:
                package_id = int(data.split("_")[1])
                success, message, transaction = package_service.purchase_package(user_id, package_id)
                
                if success:
                    await query.edit_message_text(f"✅ {message}")
                else:
                    await query.edit_message_text(f"❌ {message}")
            except Exception as e:
                await query.edit_message_text(
                    "❌ حدث خطأ في شراء الباقة\nحاول مرة أخرى",
                    )
        
        elif data.startswith("gen_voucher_count_"):
            try:
                count = int(data.split("_")[-1])
                await self.process_voucher_generation_with_count(update, context, count)
            except Exception as e:
                logger.error(f"Error generating vouchers: {e}")
                await query.edit_message_text(
                    f"❌ خطأ في توليد الكوبونات: {str(e)}",
                    )
        
        elif data == "gen_voucher_custom":
            await query.edit_message_text(
                """🎫 توليد كوبونات - عدد مخصص
أرسل العدد المطلوب (1-100):

مثال: `25` لتوليد 25 كوبون

💡 نصيحة: تأكد من العدد قبل الإرسال""",
            )
            context.user_data['waiting_for'] = 'admin_voucher_count'
        
        elif data.startswith("recharge_"):
            try:
                if data == "recharge_custom":
                    await query.edit_message_text(
                        """✏️ مبلغ مخصص
💬 ارسل المبلغ المطلوب:
• مثال: `15.50`
• أو: `/recharge 25.75`

🚨 ملاحظة: أقل مبلغ $1.00""",
                        parse_mode='Markdown'
                    )
                    context.user_data['waiting_for'] = 'recharge_amount'
                    return
                
                # Extract amount from callback data
                amount = float(data.split("_")[1])
                
                # Store amount in user data for later use
                context.user_data['selected_amount'] = amount
                
                # Show payment method selection
                keyboard = [
                    [InlineKeyboardButton("💰 الدفع عبر Binance", callback_data=f"binance_pay_{amount}")],
                    [InlineKeyboardButton("🌐 الدفع عبر الموقع", url="https://tf3eel.com/ar/TelegramCID")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"""💳 شحن الرصيد

💰 المبلغ المختار: ${amount:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 اختر طريقة الدفع:""",
                    reply_markup=reply_markup
                )
                
            except Exception as e:
                logger.error(f"Error handling recharge callback: {e}")
                await query.edit_message_text(
                    "❌ خطأ في معالجة الطلب\n\nحاول مرة أخرى",
                    )
        
        elif query.data.startswith("binance_pay_"):
            try:
                # Extract amount from callback data
                amount = float(query.data.split("_")[2])
                
                # Show payment info for Binance
                deposit_info = payment_service.format_payment_info(amount)
                
                keyboard = [
                    [InlineKeyboardButton("💰 تأكيد الدفع", callback_data="confirm_payment")],
                    [InlineKeyboardButton("🌐 الدفع عبر الموقع", url="https://tf3eel.com/ar/TelegramCID")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    deposit_info,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
            except Exception as e:
                logger.error(f"Error handling binance_pay callback: {e}")
                await query.edit_message_text(
                    "❌ خطأ في معالجة الطلب\n\nحاول مرة أخرى"
                )
        
        elif query.data == "contact":
            admin_users = db.get_admin_users()
            # Filter out specific admin from support page
            admin_users = [admin for admin in admin_users if admin['telegram_id'] != 5255786759]
            
            if admin_users:
                contact_text = "📞 **تواصل مع الإدارة**\n\n"
                contact_text += "يمكنك التواصل مع أي من أعضاء الإدارة التاليين:\n\n"
                
                for admin in admin_users:
                    username = admin['username']
                    if username and username != 'غير محدد':
                        contact_text += f"👤 @{username}\n"
                    else:
                        contact_text += f"👤 {admin['first_name']}\n"
                
                contact_text += "\n💬 اختر أي منهم للحصول على المساعدة"
            else:
                contact_text = "📞 **تواصل مع الإدارة**\n\n❌ لا يوجد أدمن متاح حالياً"
            
            await query.edit_message_text(contact_text, parse_mode='Markdown')
        
        # Copy voucher code callback - REMOVED as per user request
        # elif query.data.startswith("copy_voucher_"):
        
        elif data.startswith("contact_admin_"):
            try:
                admin_id = int(data.split("_")[-1])
                
                # Get admin info
                admin_users = db.get_admin_users()
                admin_info = next((admin for admin in admin_users if admin['telegram_id'] == admin_id), None)
                
                if not admin_info:
                    await query.edit_message_text(
                        "❌ المدير غير متاح\n\nحاول مع مدير آخر",
                            )
                    return
                
                # Use multiple fallbacks for admin name
                admin_name = (
                    admin_info.get('first_name') or 
                    admin_info.get('username') or 
                    f"مدير {admin_id}"
                )
                
                await query.edit_message_text(
                    f"""💬 التواصل مع {admin_name}
ارسل رسالتك الآن وسيتم توجيهها مباشرة إلى {admin_name}:

📝 نصائح مهمة:
• اذكر تفاصيل طلبك بوضوح
• ضع اسمك ورقم تليفونك إن أمكن
• في حالة الدفع اليدوي، اذكر المبلغ وطريقة الدفع المطلوبة"""
                )
                
                # Store admin ID for direct messaging
                context.user_data['selected_admin_id'] = admin_id
                context.user_data['waiting_for'] = 'admin_message'
                
            except Exception as e:
                logger.error(f"Error in contact_admin handler: {e}")
                await query.edit_message_text(
                    "❌ حدث خطأ\n\nحاول مرة أخرى",
                    )
        
        elif data == "confirm_payment" or data.startswith("confirm_payment_"):
            await query.edit_message_text(
                "💰 تأكيد الدفع\n\nأرسل Transaction ID (TXID) بعد إتمام التحويل:",
            )
            context.user_data['waiting_for'] = 'txid'
        
        # Contact admin callbacks
        elif data == "contact_manual_payment":
            await query.edit_message_text(
                """🛒 تواصل مع الإدارة للشراء
أرسل رسالة تحتوي على:
• الباقة المطلوبة
• طريقة الدفع المفضلة  
• رقمك للتواصل

سيتم الرد عليك خلال 1-24 ساعة لترتيب الدفع والتفعيل.""",
            )
            context.user_data['waiting_for'] = 'contact_message_manual'
        
        elif data == "contact_voucher":
            await query.edit_message_text(
                """💰 طلب كوبون شحن
للحصول على كوبون شحن، يرجى اتباع الخطوات التالية:

1️⃣ قم بالدفع عبر بايننس:
   • استخدم `/deposit` لعرض عنوان المحفظة
   • أرسل المبلغ المطلوب عبر USDT TRC20
   • احفظ رقم المعاملة (TXID)

2️⃣ أرسل إثبات الدفع:
   أرسل رسالة تحتوي على:
   • رقم المعاملة (TXID)
   • المبلغ المرسل
   • سبب طلب الكوبون

3️⃣ انتظار الرد:
   سيقوم الأدمن بمراجعة الطلب وإرسال الكوبون

📝 أرسل رسالتك الآن:""",
            )
            context.user_data['waiting_for'] = 'admin_message'
            context.user_data['message_type'] = 'voucher_request'
        
        elif data == "contact_general":
            await query.edit_message_text(
                """❓ استفسار عام
يمكنك إرسال أي استفسار حول:
• كيفية استخدام البوت
• أنواع الباقات المتاحة
• طرق الدفع
• أي أسئلة أخرى

📝 أرسل استفسارك الآن:""",
            )
            context.user_data['waiting_for'] = 'admin_message'
            context.user_data['message_type'] = 'general_inquiry'
        
        elif data == "contact_technical":
            await query.edit_message_text(
                """🔧 مشكلة تقنية
صف المشكلة التي تواجهها:
• مشاكل في قراءة Installation ID
• أخطاء في البوت
• مشاكل في واجهة المستخدم
• أي مشاكل تقنية أخرى

📝 اشرح المشكلة بالتفصيل:""",
            )
            context.user_data['waiting_for'] = 'admin_message'
            context.user_data['message_type'] = 'technical_issue'
        
        elif data == "contact_payment":
            await query.edit_message_text(
                """💳 مشكلة في الدفع
اشرح مشكلتك في الدفع:
• مشاكل في التحويل عبر بايننس
• عدم تأكيد المعاملة
• مشاكل في رقم المحفظة
• استفسارات حول طرق الدفع

📝 اشرح المشكلة مع تفاصيل المعاملة إن وجدت:""",
            )
            context.user_data['waiting_for'] = 'admin_message'
            context.user_data['message_type'] = 'payment_issue'
    
    async def handle_manual_payment_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle manual payment messages"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        message_text = update.message.text
        
        # Format message for admin
        admin_message = f"""🛒 طلب شراء يدوي جديد
👤 بيانات العميل:
• الاسم: {first_name}
• المعرف: @{username}
• ID: `{user_id}`

💬 تفاصيل الطلب:
{message_text}

⏰ الوقت: {update.message.date.strftime('%Y-%m-%d %H:%M:%S')}

🎯 الإجراءات المتاحة:
• `/reply {user_id} [رسالة]` - للرد على العميل
• `/add_balance {user_id} [CID] [USD]` - لإضافة الرصيد
• `/create_voucher {user_id} [مبلغ]` - لإنشاء كوبون

📞 للمتابعة السريعة: تواصل مع العميل لترتيب الدفع"""
        
        # Send to all admins
        from config import config
        for admin_id in config.telegram.admin_ids:
            try:
                await context.bot.send_message(
                    admin_id, 
                    admin_message,
                    )
            except Exception as e:
                logger.error(f"Failed to send manual payment request to admin {admin_id}: {e}")
        
        # Confirm to user
        await update.message.reply_text(
            """✅ تم إرسال طلبك بنجاح!
🕒 المتوقع: سيتم التواصل معك خلال ساعات قليلة لترتيب الدفع والتفعيل

💡 نصيحة: تأكد من تفعيل الإشعارات لتلقي الرد سريعاً

🔔 في انتظارك: الإدارة ستراجع طلبك وترد عليك قريباً"""
        )

    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages sent to admin"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        message_text = update.message.text
        
        # Check if user selected a specific admin
        selected_admin_id = context.user_data.get('selected_admin_id')
        
        if selected_admin_id:
            # Direct contact - Start private chat with admin
            try:
                # Send user info to admin and start direct conversation
                admin_message = f"""💬 طلب تواصل جديد
👤 المستخدم: {first_name}
🆔 معرف: @{username}
🆔 ID: {user_id}

📝 الرسالة: {message_text}

⚙️ للرد مباشرة: [t.me/{username}](https://t.me/{username})"""
                
                await self.application.bot.send_message(
                    selected_admin_id,
                    admin_message,
                    parse_mode=None
                )
                
                # Confirm to user
                await update.message.reply_text(
                    "✅ تم إرسال طلبك بنجاح!\n\n🔔 سيتم الرد عليك قريباً"
                )
                
            except Exception as e:
                logger.error(f"Failed to send message to admin {selected_admin_id}: {e}")
                await update.message.reply_text(
                    "❌ فشل في إرسال الرسالة\n\nحاول مرة أخرى أو تواصل مع مدير آخر"
                )
            
            # Clear selected admin from user data
            context.user_data.pop('selected_admin_id', None)
            return
            
        # Original logic for broadcasting to all admins
        message_type = context.user_data.get('message_type', 'general')
        
        # Message type icons
        type_icons = {
            'manual_payment': '🛛',
            'voucher_request': '💰',
            'general_inquiry': '❓',
            'technical_issue': '🔧',
            'payment_issue': '💳'
        }
        
        # Format message for admin
        admin_message = f"""🔔 رسالة جديدة من مستخدم
{type_icons.get(message_type, '📝')} النوع: {message_type.replace('_', ' ').title()}

👤 بيانات المرسل:
• الاسم: {first_name}
• المعرف: @{username}
• ID: `{user_id}`

💬 الرسالة:
{message_text}

⏰ الوقت: {update.message.date.strftime('%Y-%m-%d %H:%M:%S')}

🎯 الإجراءات المتاحة:
• `/reply {user_id} [رسالة]` - للرد على المستخدم
• `/create_voucher {user_id} [مبلغ]` - لإنشاء كوبون
• `/ban {user_id}` - لحظر المستخدم"""
        
        # Send to all admins
        for admin_id in config.telegram.admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    )
            except Exception as e:
                logger.error(f"Failed to send message to admin {admin_id}: {e}")
        
        # Log admin message
        db.log_admin_action(
            admin_id=0,  # System generated
            action=f"User message received: {message_type}",
            details=f"From user {user_id}: {message_text[:100]}..."
        )
        
        # Confirm to user
        await update.message.reply_text(
            """✅ تم إرسال رسالتك بنجاح
📨 تم إرسال رسالتك إلى الإدارة وستحصل على رد في أقرب وقت ممكن.

⏱️ وقت الاستجابة المتوقع: 1-24 ساعة

🔔 ستصلك رسالة هنا عندما يرد الأدمن على استفسارك."""
        )
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callbacks"""
        query = update.callback_query
        user_id = update.effective_user.id
        data = query.data
        
        if not admin_panel.is_admin(user_id):
            await query.edit_message_text("❌ غير مصرح لك بالوصول")
            return
        
        try:
            if data == "admin_stats":
                stats_text = admin_panel.format_statistics_message()
                keyboard = admin_panel.get_main_admin_keyboard()
                
                await query.edit_message_text(
                    stats_text,
                                        reply_markup=keyboard
                )
            
            elif data == "admin_users":
                user_stats = admin_panel.get_user_management_stats()
                await query.edit_message_text(
                    f"👥 إدارة المستخدمين\n\n{user_stats}",
                    )
            
            elif data == "admin_transactions":
                tx_stats = admin_panel.get_transaction_stats()
                await query.edit_message_text(
                    f"💰 إدارة المعاملات\n\n{tx_stats}",
                    )
            
            elif data == "admin_vouchers":
                await self.admin_handlers.show_voucher_management(query)
            
            elif data == "admin_logs":
                recent_logs = admin_panel.get_recent_logs()
                await query.edit_message_text(
                    f"📋 سجلات النظام\n\n{recent_logs}",
                    )
            
            elif data == "admin_settings":
                # Get system settings
                admin_count = len(db.get_admin_users())
                wallet_address = config.binance.usdt_trc20_address
                
                settings_text = f"""⚙️ إعدادات النظام

📊 الإعدادات المتاحة:

💳 إعدادات الدفع:
• عنوان محفظة USDT: `{wallet_address}`
• شبكة: TRC20 (Tron)
• أسعار الصرف: 1 USD = {config.usd_to_sar} ريال

🔑 إعدادات CID:
• تكلفة كل عملية: 1 CID
• PIDKEY API: متصل

🛡️ الأمان:
• عدد الأدمن: {admin_count}
• التحقق التلقائي: مفعل

━━━━━━━━━━━━━━━━━━━━━
✅ حالة النظام: يعمل بشكل طبيعي"""
                
                keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    settings_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e:
            await query.edit_message_text(
                "❌ حدث خطأ في معالجة الطلب",
            )
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel main command"""
        user_id = update.effective_user.id
        
        if not self.admin_panel.is_admin(user_id):
            await update.message.reply_text("❌ غير مصرح لك بالوصول للوحة الإدارة")
            return
        
        keyboard = self.admin_panel.get_main_admin_keyboard()
        await update.message.reply_text(
            "🔧 لوحة تحكم الأدمن\n\nمرحباً بك في لوحة التحكم",
            reply_markup=keyboard
        )
    
    async def handle_txid_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle TXID input for payment verification"""
        txid = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Show processing message
        processing_msg = await update.message.reply_text("🔄 جار التحقق من المعاملة...")
        
        # Process payment
        success, message, tx_data = await payment_service.process_payment(user_id, txid)
        
        await processing_msg.delete()
        
        if success:
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
    
    def setup_bot_commands(self):
        """Setup bot commands menu"""
        commands = [
            BotCommand("start", "🎆 بدء استخدام البوت"),
            BotCommand("info", "📊 معلوماتي ورصيدي"),
            BotCommand("get_cid", "🔑 إنشاء CID جديد"),
            BotCommand("packages", "📦 الباقات والأسعار"),
            BotCommand("recharge", "💳 شحن الرصيد"),
            BotCommand("deposit", "💰 شحن USDT"),
            BotCommand("voucher", "🎫 كود شحن"),
            BotCommand("history", "📋 تاريخ المعاملات"),
            BotCommand("contact", "📞 تواصل مع الإدارة"),
            BotCommand("balance", "💵 عرض الرصيد"),
            BotCommand("admin", "🔧 لوحة الإدارة")
        ]
        
        # Set commands after the bot is initialized
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create a task
                asyncio.create_task(self.application.bot.set_my_commands(commands))
            else:
                # If no loop, run directly
                asyncio.run(self.application.bot.set_my_commands(commands))
        except:
            # Skip command setup if there's an issue
            pass
    
    def setup_handlers(self):
        """Setup bot handlers"""
        app = self.application
        
        # Add command handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("info", self.info_command))
        app.add_handler(CommandHandler("balance", self.balance_command))
        app.add_handler(CommandHandler("packages", self.packages_command))
        app.add_handler(CommandHandler("get_cid", self.get_cid_command))
        app.add_handler(CommandHandler("deposit", self.deposit_command))
        app.add_handler(CommandHandler("recharge", self.deposit_command))  # Alias for deposit
        app.add_handler(CommandHandler("voucher", self.voucher_command))
        app.add_handler(CommandHandler("history", self.history_command))
        app.add_handler(CommandHandler("contact", self.contact_command))
        
        # Add buy commands for packages (buy1, buy2, etc.)
        for i in range(1, 9):
            app.add_handler(CommandHandler(f"buy{i}", lambda update, context, pkg_id=i: self.buy_package_command(update, context, pkg_id)))
        
        # Admin commands
        app.add_handler(CommandHandler("admin", self.admin_command))
        app.add_handler(CommandHandler("reply", self.admin_reply_command))
        app.add_handler(CommandHandler("create_voucher", self.admin_create_voucher_command))
        app.add_handler(CommandHandler("add_balance", self.admin_add_balance_command))
        
        # Add callback query handler
        app.add_handler(CallbackQueryHandler(self.callback_query_handler))
        
        # Add message handlers
        app.add_handler(MessageHandler(filters.PHOTO, self.photo_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_handler))
        
        # Add error handler
        app.add_error_handler(self.error_handler)
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general text input"""
        user_data = context.user_data
        
        if user_data.get('waiting_for') == 'voucher':
            await self.handle_voucher_input(update, context)
            user_data.pop('waiting_for', None)
        
        elif user_data.get('waiting_for') == 'recharge_amount':
            try:
                amount = float(update.message.text.strip())
                if amount < 1.0:
                    await update.message.reply_text(
                        "❌ مبلغ قليل جداً\n\nأقل مبلغ للشحن هو $1.00",
                            )
                    return
                
                # Show payment info for specified amount
                deposit_info = payment_service.format_payment_info(amount)
                
                keyboard = [
                    [InlineKeyboardButton("💰 تأكيد الدفع", callback_data="confirm_payment")],
                    [InlineKeyboardButton("🌐 الدفع عبر الموقع", url="https://tf3eel.com/ar/TelegramCID")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    deposit_info,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
            except ValueError:
                await update.message.reply_text(
                    "❌ مبلغ غير صحيح\n\nمثال صحيح: `15.50`",
                    )
                return
            
            user_data.pop('waiting_for', None)
        
        elif user_data.get('waiting_for') == 'txid':
            await self.handle_txid_input(update, context)
            user_data.pop('waiting_for', None)
        
        elif user_data.get('waiting_for') == 'admin_message':
            await self.handle_admin_message(update, context)
            user_data.pop('waiting_for', None)
            user_data.pop('message_type', None)
        
        elif user_data.get('waiting_for') == 'contact_message_manual':
            await self.handle_manual_payment_message(update, context)
            user_data.pop('waiting_for', None)
        
        elif user_data.get('waiting_for') in ['admin_voucher_count', 'admin_add_balance', 'admin_subtract_balance']:
            # Handle admin input
            await self.handle_admin_input(update, context)
        
        else:
            # Check if it could be an Installation ID
            await self.handle_text_iid(update, context)
    
    async def contact_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /contact command for contacting admin"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "غير محدد"
        first_name = update.effective_user.first_name or "مستخدم"
        
        # Create user if not exists
        db.create_user(user_id, username, first_name)
        
        keyboard = [
            [InlineKeyboardButton("💰 طلب كوبون شحن", callback_data="request_voucher")],
            [InlineKeyboardButton("❓ استفسار عام", callback_data="general_inquiry")],
            [InlineKeyboardButton("🔧 مشكلة تقنية", callback_data="technical_issue")],
            [InlineKeyboardButton("💳 مشكلة في الدفع", callback_data="payment_issue")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            """📞 التواصل مع الإدارة
اختر نوع الاستفسار أو المساعدة المطلوبة:

💰 طلب كوبون شحن: للحصول على كود شحن بعد الدفع
❓ استفسار عام: أسئلة حول الخدمة
🔧 مشكلة تقنية: مشاكل في البوت أو OCR
💳 مشكلة في الدفع: مساعدة في عمليات الدفع

سيتم إرسال رسالتك للإدارة وستحصل على رد قريباً.""",
                        reply_markup=reply_markup
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors that occur during bot operation"""
        error = context.error
        logger.error(f"Update {update} caused error {error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ حدث خطأ غير متوقع، حاول مرة أخرى أو تواصل مع الدعم الفني",
                    )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def admin_reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reply command for admin to respond to users"""
        user_id = update.effective_user.id
        
        if not admin_panel.is_admin(user_id):
            await update.message.reply_text("❌ غير مصرح لك باستخدام هذا الأمر")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ خطأ في الاستخدام\n\nالصيغة الصحيحة:\n`/reply [user_id] [رسالة]`\n\nمثال:\n`/reply 123456789 مرحباً، تم استلام طلبك`",
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            reply_message = " ".join(context.args[1:])
            
            # Send message to target user
            admin_reply = f"""📨 رد من الإدارة
{reply_message}

━━━━━━━━━━━━━━━━━━━━━
💬 للتواصل مع الإدارة مرة أخرى: /contact"""
            
            await context.bot.send_message(
                chat_id=target_user_id,
                text=admin_reply,
            )
            
            # Confirm to admin
            await update.message.reply_text(
                f"✅ تم إرسال الرد بنجاح\n\nإلى المستخدم: `{target_user_id}`\nالرسالة: {reply_message}",
            )
            
            # Log admin action
            db.log_admin_action(
                admin_id=user_id,
                action="Admin reply sent",
                details=f"To user {target_user_id}: {reply_message[:100]}..."
            )
            
        except ValueError:
            await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في إرسال الرسالة: {str(e)}")
    
    async def admin_create_voucher_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /create_voucher command for admin to create vouchers for users"""
        user_id = update.effective_user.id
        
        if not admin_panel.is_admin(user_id):
            await update.message.reply_text("❌ غير مصرح لك باستخدام هذا الأمر")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                """❌ خطأ في الاستخدام
الصيغة الصحيحة:
`/create_voucher [user_id] [مبلغ] [سبب اختياري]`

أمثلة:
• `/create_voucher 123456789 10` - كوبون بقيمة $10
• `/create_voucher 123456789 25 دفع عبر بايننس` - مع سبب""",
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            amount = float(context.args[1])
            reason = " ".join(context.args[2:]) if len(context.args) > 2 else "كوبون من الإدارة"
            
            # Validate amount
            if amount <= 0 or amount > 1000:
                await update.message.reply_text("❌ المبلغ يجب أن يكون بين 0.01 و 1000 دولار")
                return
            
            # Create voucher
            voucher_code = voucher_service.create_voucher(
                value_usd=amount,
                created_by_admin_id=user_id,
                description=f"Admin created for user {target_user_id}: {reason}"
            )
            
            if voucher_code:
                # Send voucher to user
                voucher_message = f"""🎫 كوبون شحن جديد!
تم إنشاء كوبون شحن لك من قبل الإدارة:"

💰 القيمة: ${amount:.2f}
🔖 الكود: `{voucher_code}`
📝 السبب: {reason}

🔄 لاستخدام الكوبون:
1. أرسل الأمر `/voucher`
2. أدخل الكود: `{voucher_code}`

⏰ صالح لمدة: 30 يوماً من الآن
📞 للاستفسار: /contact"""
                
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=voucher_message,
                    )
                
                # Confirm to admin
                await update.message.reply_text(
                    f"""✅ تم إنشاء وإرسال الكوبون بنجاح
👤 للمستخدم: `{target_user_id}`
💰 المبلغ: ${amount:.2f}
🔖 الكود: `{voucher_code}`
📝 السبب: {reason}""",
                    )
                
                # Log admin action
                db.log_admin_action(
                    admin_id=user_id,
                    action="Voucher created and sent",
                    details=f"${amount:.2f} voucher ({voucher_code}) for user {target_user_id}: {reason}"
                )
            else:
                await update.message.reply_text("❌ فشل في إنشاء الكوبون")
                
        except ValueError:
            await update.message.reply_text("❌ تأكد من صحة معرف المستخدم والمبلغ")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في إنشاء الكوبون: {str(e)}")
    
    def run(self):
        """Run the bot"""
        # Initialize bot application
        self.application = Application.builder().token(config.telegram.bot_token).build()
        
        # Setup handlers
        self.setup_handlers()
        
        logger.info("Advanced CID Bot started successfully!")
        
        # Start the bot
        self.application.run_polling(drop_pending_updates=True)

def main():
    """Main function to run the bot"""
    bot = AdvancedCIDBot()
    bot.run()

if __name__ == "__main__":
    main()
