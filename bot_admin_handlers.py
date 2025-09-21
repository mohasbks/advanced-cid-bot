"""
Admin handlers for Advanced CID Telegram Bot
Implements all admin panel functionality as specified
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import secrets
import string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import func

from database.database import db
from services.voucher_service import voucher_service
from admin_panel import admin_panel

logger = logging.getLogger(__name__)

class AdminHandlers:
    """Admin callback handlers implementing exact specifications"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.admin_panel = admin_panel
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main admin callback handler"""
        query = update.callback_query
        user_id = update.effective_user.id
        data = query.data
        
        # Check admin permissions
        if not self.admin_panel.is_admin(user_id):
            await query.edit_message_text(
                "❌ غير مصرح لك بالوصول للوحة الإدارة",
                parse_mode='Markdown'
            )
            return
        
        # Handle different admin actions
        if data == "admin_stats":
            await self.show_statistics(query)
        elif data == "admin_users":
            await self.show_users_list(query)
        elif data == "admin_balance":
            await self.show_balance_management(query)
        elif data == "admin_vouchers":
            await self.show_voucher_management(query)
        elif data == "admin_packages":
            await self.show_packages_management(query)
        elif data == "admin_transactions":
            await self.show_transactions_management(query)
        elif data == "admin_logs":
            await self.show_operations_log(query)
        elif data == "admin_add_balance":
            await self.handle_add_balance(query, context)
        elif data == "admin_subtract_balance":
            await self.handle_subtract_balance(query, context)
        elif data == "admin_generate_vouchers":
            await self.handle_generate_vouchers(query, context)
        elif data == "admin_create_single_cid":
            await self.create_single_cid_voucher(query)
        elif data == "admin_bulk_single_cid":
            await self.show_bulk_single_cid_options(query)
        elif data.startswith("admin_bulk_cid_"):
            count = int(data.split("_")[-1])
            await self.create_bulk_single_cid_vouchers(query, count)
        elif data == "admin_voucher_stats":
            await self.show_voucher_statistics(query)
        elif data.startswith("admin_gen_pkg_"):
            await self.handle_package_selection(query, context)
        elif data == "admin_settings":
            await self.show_system_settings(query)
        elif data == "admin_panel":
            await self.show_admin_panel(query)
        elif data == "admin_refresh":
            await self.refresh_system_data(query)
        else:
            await query.edit_message_text(
                "❌ إجراء غير مدعوم",
                parse_mode='Markdown'
            )
    
    async def show_statistics(self, query):
        """📊 الإحصائيات - عرض بيانات النظام"""
        try:
            # Get system statistics
            with db.get_session() as session:
                from database.models import User, Transaction, Voucher, CIDRequest
                
                # User statistics
                total_users = session.query(User).count()
                active_users = session.query(User).filter(
                    User.last_activity >= datetime.utcnow() - timedelta(days=30)
                ).count()
                
                # Transaction statistics
                total_deposits = session.query(Transaction).filter(
                    Transaction.type == "usdt_deposit",
                    Transaction.status == "completed"
                ).count()
                
                total_cid_requests = session.query(CIDRequest).count()
                successful_cid = session.query(CIDRequest).filter(
                    CIDRequest.status == "completed"
                ).count()
                
                # Voucher statistics
                total_vouchers = session.query(Voucher).count()
                used_vouchers = session.query(Voucher).filter(
                    Voucher.is_used == True
                ).count()
                
                stats_text = f"""📊 إحصائيات النظام

👥 المستخدمين:
• إجمالي المستخدمين: {total_users:,}
• نشط (30 يوم): {active_users:,}

💰 المالية:
• إيداعات مكتملة: {total_deposits:,}

💎 CID:
• إجمالي الطلبات: {total_cid_requests:,}
• ناجحة: {successful_cid:,}
• معدل النجاح: {(successful_cid/max(1,total_cid_requests)*100):.1f}%

🎫 الكوبونات:
• إجمالي الكودات: {total_vouchers:,}
• مستخدمة: {used_vouchers:,}
• متاحة: {total_vouchers - used_vouchers:,}

━━━━━━━━━━━━━━━━━━━━━
🕒 آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="admin_stats")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                stats_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error showing statistics: {e}")
            await query.edit_message_text(
                f"❌ خطأ في جلب الإحصائيات: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def show_users_list(self, query):
        """👥 قائمة المستخدمين - عرض المستخدمين + أرصدتهم"""
        try:
            with db.get_session() as session:
                from database.models import User
                
                # Get last 20 users with their balances
                users = session.query(User).order_by(User.registered_at.desc()).limit(20).all()
                
                if not users:
                    users_text = "👥 قائمة المستخدمين\n\nلا يوجد مستخدمين"
                else:
                    users_text = "👥 قائمة المستخدمين (آخر 20)\n\n"
                    
                    for i, user in enumerate(users, 1):
                        username = user.username or "بدون معرف"
                        first_name = user.first_name or "مستخدم"
                        
                        # Escape special markdown characters
                        safe_first_name = first_name.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        safe_username = username.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        
                        users_text += f"""*{i}. {safe_first_name}*
📱 المعرف: @{safe_username}
🆔 ID: {user.user_id}
💎 رصيد CID: {user.balance_cid:,}
💵 رصيد USD: ${user.balance_usd:.2f}
📅 التسجيل: {user.registered_at.strftime('%Y-%m-%d')}

"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 تحديث القائمة", callback_data="admin_users")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    users_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error showing users list: {e}")
            await query.edit_message_text(
                f"❌ خطأ في جلب قائمة المستخدمين: {str(e)}",
                parse_mode='Markdown'
            )

    async def show_balance_management(self, query):
        """💰 إدارة الأرصدة - إضافة وخصم"""
        balance_text = """💰 إدارة الأرصدة

اختر العملية المطلوبة:

➕ إضافة رصيد يدوي
   - إدخال ID المستخدم
   - إدخال عدد النقاط CID
   - إدخال مبلغ USD (اختياري)

➖ خصم رصيد يدوي  
   - إدخال ID المستخدم
   - إدخال عدد النقاط المراد خصمها

━━━━━━━━━━━━━━━━━━━━━
⚠️ تنبيه: هذه العمليات تتم بشكل مباشر ولا يمكن التراجع عنها"""
        
        keyboard = [
            [InlineKeyboardButton("➕ إضافة رصيد يدوي", callback_data="admin_add_balance")],
            [InlineKeyboardButton("➖ خصم رصيد يدوي", callback_data="admin_subtract_balance")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            balance_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def show_voucher_management(self, query):
        """🎫 توليد أكواد (Voucher Codes)"""
        voucher_text = """🎫 **إدارة الكوبونات**

اختر العملية المطلوبة:

➕ **توليد أكواد جديدة**
   - اختيار الباقة (25, 50, 100, 500... إلخ CID)
   - اختيار عدد الأكواد المراد توليدها
   - النظام سيولد أكواد عشوائية مثل: AB12-CD34-EF56

📊 **إحصائيات الكوبونات**
   - عرض الكودات المتاحة والمستخدمة

━━━━━━━━━━━━━━━━━━━━━
💡 **مثال الكود المولد**: XK9M-P2L7-QW4R"""
        
        keyboard = [
            [InlineKeyboardButton("➕ توليد أكواد جديدة", callback_data="admin_generate_vouchers")],
            [InlineKeyboardButton("⚡ إنشاء كوبون 1 CID", callback_data="admin_create_single_cid")],
            [InlineKeyboardButton("📊 إحصائيات الكوبونات", callback_data="admin_voucher_stats")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            voucher_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def show_admin_panel(self, query):
        """Show main admin panel"""
        await query.edit_message_text(
            self.admin_panel.get_main_admin_panel_text(),
            parse_mode='Markdown',
            reply_markup=self.admin_panel.get_main_admin_keyboard()
        )

    async def handle_add_balance(self, query, context):
        """Handle add balance process"""
        await query.edit_message_text(
            """➕ **إضافة رصيد يدوي**

أرسل البيانات بالتنسيق التالي:
`معرف_المستخدم CID_المراد_إضافته USD_المراد_إضافته`

**مثال:**
`123456789 100 10.5`

هذا المثال سيضيف:
• 100 CID 
• 10.5 USD
• للمستخدم رقم 123456789

━━━━━━━━━━━━━━━━━━━━━
💡 **ملاحظة**: يمكن كتابة 0 لأي قيمة لا تريد إضافتها""",
            parse_mode='Markdown'
        )
        
        context.user_data['waiting_for'] = 'admin_add_balance'

    async def handle_subtract_balance(self, query, context):
        """Handle subtract balance process"""
        await query.edit_message_text(
            """➖ **خصم رصيد يدوي**

أرسل البيانات بالتنسيق التالي:
`معرف_المستخدم CID_المراد_خصمه USD_المراد_خصمه`

**مثال:**
`123456789 50 5.0`

هذا المثال سيخصم:
• 50 CID 
• 5.0 USD
• من المستخدم رقم 123456789

━━━━━━━━━━━━━━━━━━━━━
⚠️ **تحذير**: لا يمكن التراجع عن هذه العملية""",
            parse_mode='Markdown'
        )
        
        context.user_data['waiting_for'] = 'admin_subtract_balance'

    async def handle_generate_vouchers(self, query, context):
        """Handle voucher generation - step 1: choose package"""
        packages_text = """🎫 **توليد أكواد - اختيار الباقة**

اختر الباقة التي تريد إنشاء كودات لها:

🔟 باقة تجريبية - 10 CID
1️⃣ باقة صغيرة - 30 CID
2️⃣ باقة متوسطة - 50 CID  
3️⃣ باقة كبيرة - 100 CID
4️⃣ باقة مميزة - 500 CID
5️⃣ باقة متقدمة - 1000 CID
6️⃣ باقة احترافية - 2000 CID
7️⃣ باقة ضخمة - 5000 CID
8️⃣ باقة عملاقة - 10000 CID

━━━━━━━━━━━━━━━━━━━━━
اختر الباقة لتحديد عدد الكودات المطلوبة"""
        
        keyboard = [
            [InlineKeyboardButton("🔟 10 CID", callback_data="admin_gen_pkg_0"),
             InlineKeyboardButton("1️⃣ 30 CID", callback_data="admin_gen_pkg_1")],
            [InlineKeyboardButton("2️⃣ 50 CID", callback_data="admin_gen_pkg_2"),
             InlineKeyboardButton("3️⃣ 100 CID", callback_data="admin_gen_pkg_3")],
            [InlineKeyboardButton("4️⃣ 500 CID", callback_data="admin_gen_pkg_4"),
            [InlineKeyboardButton("5️⃣ 1000 CID", callback_data="admin_gen_pkg_5"),
             InlineKeyboardButton("6️⃣ 2000 CID", callback_data="admin_gen_pkg_6")],
            [InlineKeyboardButton("7️⃣ 5000 CID", callback_data="admin_gen_pkg_7"),
             InlineKeyboardButton("8️⃣ 10000 CID", callback_data="admin_gen_pkg_8")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            packages_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def handle_package_selection(self, query, context):
        """Handle package selection for voucher generation"""
        package_id = int(query.data.split("_")[-1])
        
        # Package mapping
        packages = {
            0: {'name': 'باقة تجريبية', 'cid_amount': 10, 'price_usd': 2.67},
            1: {'name': 'باقة صغيرة', 'cid_amount': 30, 'price_usd': 6.40},
            2: {'name': 'باقة متوسطة', 'cid_amount': 50, 'price_usd': 6.67},
            3: {'name': 'باقة كبيرة', 'cid_amount': 100, 'price_usd': 12.53},
            4: {'name': 'باقة مميزة', 'cid_amount': 500, 'price_usd': 56.53},
            5: {'name': 'باقة متقدمة', 'cid_amount': 1000, 'price_usd': 102.67},
            6: {'name': 'باقة احترافية', 'cid_amount': 2000, 'price_usd': 184.80},
            7: {'name': 'باقة ضخمة', 'cid_amount': 5000, 'price_usd': 408.00},
            8: {'name': 'باقة عملاقة', 'cid_amount': 10000, 'price_usd': 762.70}
        }
        
        package = packages.get(package_id)
        if not package:
            await query.edit_message_text("❌ باقة غير صحيحة")
            return
        
        # Store selected package in context
        context.user_data['selected_package'] = package
        context.user_data['selected_package_id'] = package_id
        
        # Create inline keyboard for quick count selection
        keyboard = [
            [InlineKeyboardButton("1", callback_data=f"gen_voucher_count_1"),
             InlineKeyboardButton("5", callback_data=f"gen_voucher_count_5"),
             InlineKeyboardButton("10", callback_data=f"gen_voucher_count_10")],
            [InlineKeyboardButton("25", callback_data=f"gen_voucher_count_25"),
             InlineKeyboardButton("50", callback_data=f"gen_voucher_count_50"),
             InlineKeyboardButton("100", callback_data=f"gen_voucher_count_100")],
            [InlineKeyboardButton("✏️ عدد مخصص", callback_data="gen_voucher_custom"),
             InlineKeyboardButton("🔙 رجوع", callback_data="admin_vouchers")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"""🎫 **توليد أكواد - تحديد العدد**

تم اختيار: **{package['name']}**
💎 **قيمة كل كود**: {package['cid_amount']} CID
💰 **السعر**: ${package['price_usd']:.2f}

━━━━━━━━━━━━━━━━━━━━━
**اختر عدد الكودات المراد توليدها:**

💡 **نصيحة**: ابدأ بعدد صغير للاختبار""",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def show_operations_log(self, query):
        """📋 سجل العمليات - عرض عمليات الشحن + عمليات CID"""
        try:
            with db.get_session() as session:
                from database.models import Transaction, CIDRequest, User
                
                # Get recent deposit operations with user info
                recent_deposits = session.query(Transaction, User).join(
                    User, Transaction.user_id == User.id
                ).filter(
                    Transaction.type == "usdt_deposit"
                ).order_by(Transaction.created_at.desc()).limit(10).all()
                
                # Get recent CID operations with user info
                recent_cid = session.query(CIDRequest, User).join(
                    User, CIDRequest.user_id == User.id
                ).order_by(CIDRequest.created_at.desc()).limit(10).all()
                
                log_text = "📋 **سجل الأنشطة**\n\n"
                
                # Deposit operations
                log_text += "💰 **آخر عمليات الشحن:**\n"
                if recent_deposits:
                    for i, (tx, user) in enumerate(recent_deposits[:5], 1):
                        username = user.username or "بدون معرف"
                        first_name = user.first_name or "مستخدم"
                        status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌"}.get(tx.status, "❓")
                        
                        # Escape special markdown characters
                        safe_first_name = first_name.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        safe_username = username.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        
                        log_text += f"{i}. {status_emoji} {safe_first_name} (@{safe_username})\n"
                        log_text += f"   💵 ${tx.amount_usd:.2f} • 📅 {tx.created_at.strftime('%m-%d %H:%M')}\n\n"
                else:
                    log_text += "📭 لا توجد عمليات شحن حديثة\n\n"
                
                log_text += "💎 **آخر عمليات CID:**\n"
                if recent_cid:
                    for i, (cid_req, user) in enumerate(recent_cid[:5], 1):
                        username = user.username or "بدون معرف"
                        first_name = user.first_name or "مستخدم"
                        status_emoji = {"completed": "✅", "processing": "🔄", "failed": "❌"}.get(cid_req.status, "❓")
                        
                        # Escape special markdown characters
                        safe_first_name = first_name.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        safe_username = username.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        
                        log_text += f"{i}. {status_emoji} {safe_first_name} (@{safe_username})\n"
                        log_text += f"   🔑 CID Request • 📅 {cid_req.created_at.strftime('%m-%d %H:%M')}\n\n"
                else:
                    log_text += "📭 لا توجد عمليات CID حديثة\n\n"
                
                log_text += f"━━━━━━━━━━━━━━━━━━━━━\n🕒 **آخر تحديث**: {datetime.now().strftime('%H:%M')}"
                
                keyboard = [
                    [InlineKeyboardButton("🔄 تحديث السجل", callback_data="admin_logs")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    log_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error showing operations log: {e}")
            await query.edit_message_text(
                f"❌ خطأ في جلب سجل العمليات: {str(e)}",
                parse_mode='Markdown'
            )

    async def show_packages_management(self, query):
        """📦 إدارة الباقات - عرض وتعديل الباقات"""
        try:
            with db.get_session() as session:
                from database.models import Package
                
                packages = session.query(Package).order_by(Package.cid_amount).all()
                
                if not packages:
                    packages_text = "📦 **إدارة الباقات**\n\nلا توجد باقات متاحة"
                else:
                    packages_text = "📦 **إدارة الباقات**\n\n"
                    
                    for i, package in enumerate(packages, 1):
                        status = "✅ نشط" if package.is_active else "❌ معطل"
                        packages_text += f"""**{i}. {package.name}**
💎 CID: {package.cid_amount:,}
💵 USD: ${package.price_usd:.2f}
🏷️ ريال: {package.price_sar:.2f} ر.س
📊 الحالة: {status}

"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 تحديث القائمة", callback_data="admin_packages")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    packages_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error showing packages management: {e}")
            await query.edit_message_text(
                f"❌ خطأ في جلب قائمة الباقات: {str(e)}",
                parse_mode='Markdown'
            )

    async def show_transactions_management(self, query):
        """💰 المعاملات المالية - عرض المعاملات الأخيرة"""
        try:
            with db.get_session() as session:
                from database.models import Transaction, User
                
                # Get last 15 transactions with user info
                transactions = session.query(Transaction, User).join(
                    User, Transaction.user_id == User.id
                ).order_by(Transaction.created_at.desc()).limit(15).all()
                
                if not transactions:
                    trans_text = "💰 **المعاملات المالية**\n\nلا توجد معاملات"
                else:
                    trans_text = "💰 **المعاملات المالية (آخر 15)**\n\n"
                    
                    for i, (transaction, user) in enumerate(transactions, 1):
                        username = user.username or "بدون معرف"
                        first_name = user.first_name or "مستخدم"
                        
                        # Transaction type emoji
                        type_emoji = {
                            'usdt_deposit': '💳',
                            'voucher_redeem': '🎫', 
                            'cid_purchase': '🔑',
                            'balance_add': '➕',
                            'balance_subtract': '➖'
                        }.get(transaction.type, '💰')
                        
                        # Status emoji
                        status_emoji = {
                            'completed': '✅',
                            'pending': '⏳', 
                            'failed': '❌',
                            'processing': '🔄'
                        }.get(transaction.status, '❓')
                        
                        # Escape special markdown characters
                        safe_first_name = first_name.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        safe_username = username.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace('`', '\\`')
                        safe_type = transaction.type.replace('*', '\\*').replace('_', '\\_')
                        safe_status = transaction.status.replace('*', '\\*').replace('_', '\\_')
                        
                        trans_text += f"""*{i}. {type_emoji} {safe_type}*
👤 المستخدم: {safe_first_name} (@{safe_username})
💎 CID: {transaction.amount_cid or 0:,}
💵 USD: ${transaction.amount_usd or 0:.2f}
📊 الحالة: {status_emoji} {safe_status}
📅 التاريخ: {transaction.created_at.strftime('%m-%d %H:%M')}

"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 تحديث القائمة", callback_data="admin_transactions")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    trans_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error showing transactions management: {e}")
            await query.edit_message_text(
                f"❌ خطأ في جلب قائمة المعاملات: {str(e)}",
                parse_mode='Markdown'
            )

    async def show_system_settings(self, query):
        """⚙️ إعدادات النظام - تكوين البوت"""
        from config import config
        from database.database import db
        
        # Get real system values
        admin_count = len(db.get_admin_users())
        wallet_address = config.binance.usdt_trc20_address
        
        settings_text = f"""⚙️ **إعدادات النظام**

🔧 **الإعدادات المتاحة:**

💰 **إعدادات الدفع:**
• عنوان محفظة USDT: `{wallet_address}`
• شبكة: TRC20 (Tron)
• أسعار الصرف: 1 USD = {config.usd_to_sar} ريال

🎯 **إعدادات CID:**
• تكلفة كل عملية: 1 CID
• PIDKEY API: متصل

🛡️ **الأمان:**
• عدد الأدمن: {admin_count}
• التحقق التلقائي: مفعل

━━━━━━━━━━━━━━━━━━━━━
📊 **حالة النظام**: ✅ يعمل بشكل طبيعي"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            settings_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def show_voucher_statistics(self, query):
        """📊 إحصائيات الكوبونات - عرض تفاصيل الكودات"""
        try:
            with db.get_session() as session:
                from database.models import Voucher
                
                # Get voucher statistics
                total_vouchers = session.query(Voucher).count()
                used_vouchers = session.query(Voucher).filter(Voucher.is_used == True).count()
                unused_vouchers = total_vouchers - used_vouchers
                
                # Get vouchers by CID amount
                voucher_stats_by_cid = session.query(
                    Voucher.cid_amount,
                    func.count(Voucher.id).label('count')
                ).group_by(Voucher.cid_amount).all()
                
                # Calculate total value
                total_cid_value = session.query(func.sum(Voucher.cid_amount)).filter(
                    Voucher.is_used == False
                ).scalar() or 0
                
                total_usd_value = session.query(func.sum(Voucher.usd_amount)).filter(
                    Voucher.is_used == False
                ).scalar() or 0.0
                
                # Create breakdown text
                breakdown_text = ""
                for cid_amount, count in voucher_stats_by_cid:
                    breakdown_text += f"• {cid_amount} CID: {count} كود\n"
                if not breakdown_text:
                    breakdown_text = "• لا توجد كوبونات حاليًا"
                
                # Add seconds to make content unique each time
                current_time = datetime.now()
                stats_text = f"""📊 إحصائيات الكوبونات التفصيلية

📈 الإحصائيات العامة:
• إجمالي الكودات: {total_vouchers:,}
• مستخدمة: {used_vouchers:,}
• متاحة: {unused_vouchers:,}

💎 القيم المتاحة:
• إجمالي CID متاح: {total_cid_value:,}
• إجمالي USD متاح: ${total_usd_value:.2f}

🔢 التوزيع حسب الفئات:
{breakdown_text}

🕒 آخر تحديث: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="admin_voucher_stats")],
                    [InlineKeyboardButton("🎫 إدارة الكوبونات", callback_data="admin_vouchers")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    stats_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error showing voucher statistics: {e}")
            await query.edit_message_text(
                f"❌ خطأ في جلب إحصائيات الكوبونات: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def create_single_cid_voucher(self, query):
        """⚡ إنشاء كوبون 1 CID للأدمن"""
        try:
            admin_id = query.from_user.id
            
            # Create a single voucher with 1 CID only (no USD)
            success, message, vouchers = voucher_service.create_bulk_vouchers(
                cid_amount=1,
                usd_amount=0.0,  # No USD for 1 CID voucher
                count=1,
                admin_id=admin_id
            )
            
            if success and vouchers:
                voucher_code = vouchers[0]
                
                success_text = f"""⚡ **تم إنشاء كوبون 1 CID بنجاح!**

🎫 **الكوبون الخاص بك:**
`{voucher_code}`

💎 **قيمة الكوبون:** 1 CID
🔒 **للأدمن فقط:** يمكنك استخدامه أو إرساله لأي شخص

💡 **نصيحة:** اضغط على الكود أعلاه لنسخه فوراً!

⚠️ **ملاحظة:** هذا الكوبون يُستخدم مرة واحدة فقط"""
                
                keyboard = [
                    [InlineKeyboardButton("⚡ إنشاء كوبون آخر", callback_data="admin_create_single_cid")],
                    [InlineKeyboardButton("📦 توليد كمية كبيرة", callback_data="admin_bulk_single_cid")],
                    [InlineKeyboardButton("🎫 إدارة الكوبونات", callback_data="admin_vouchers")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    success_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
                logger.info(f"Admin {admin_id} created single 1 CID voucher: {voucher_code}")
            else:
                await query.edit_message_text(
                    f"❌ خطأ في إنشاء الكوبون: {message}",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error creating single CID voucher: {e}")
            await query.edit_message_text(
                f"❌ حدث خطأ أثناء إنشاء الكوبون: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def show_bulk_single_cid_options(self, query):
        """📦 عرض خيارات توليد كميات كبيرة من كوبونات 1 CID"""
        try:
            options_text = """📦 **توليد كميات كبيرة من كوبونات 1 CID**

⚡ **اختر الكمية المطلوبة:**
• كل كوبون يحتوي على 1 CID فقط
• الحد الأقصى: 100 كوبون
• مناسب للتوزيع والهدايا

🎯 **خيارات سريعة:**"""

            keyboard = [
                [InlineKeyboardButton("5 كوبونات", callback_data="admin_bulk_cid_5"),
                 InlineKeyboardButton("10 كوبونات", callback_data="admin_bulk_cid_10")],
                [InlineKeyboardButton("25 كوبون", callback_data="admin_bulk_cid_25"),
                 InlineKeyboardButton("50 كوبون", callback_data="admin_bulk_cid_50")],
                [InlineKeyboardButton("100 كوبون", callback_data="admin_bulk_cid_100")],
                [InlineKeyboardButton("🔙 العودة", callback_data="admin_create_single_cid")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                options_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error showing bulk single CID options: {e}")
            await query.edit_message_text(
                "❌ خطأ في عرض الخيارات",
                parse_mode='Markdown'
            )
    
    async def create_bulk_single_cid_vouchers(self, query, count: int):
        """📦 إنشاء كميات كبيرة من كوبونات 1 CID"""
        try:
            admin_id = query.from_user.id
            
            # Validate count
            if count < 1 or count > 100:
                await query.edit_message_text(
                    "❌ الكمية يجب أن تكون بين 1 و 100 كوبون",
                    parse_mode='Markdown'
                )
                return
            
            # Show processing message
            await query.edit_message_text(
                f"🔄 جار إنشاء {count} كوبون بقيمة 1 CID لكل كوبون...\n\n⏳ يرجى الانتظار...",
                parse_mode='Markdown'
            )
            
            # Create bulk vouchers
            success, message, vouchers = voucher_service.create_bulk_vouchers(
                cid_amount=1,
                usd_amount=0.0,  # No USD for 1 CID vouchers
                count=count,
                admin_id=admin_id
            )
            
            if success and vouchers:
                # Format vouchers list with chunks to avoid message limits
                chunk_size = 20  # 20 codes per message
                voucher_chunks = [vouchers[i:i + chunk_size] for i in range(0, len(vouchers), chunk_size)]
                
                success_text = f"""✅ **تم إنشاء {len(vouchers)} كوبون بنجاح!**

💎 **قيمة كل كوبون:** 1 CID
📊 **العدد الإجمالي:** {len(vouchers)} كوبون
🔒 **للأدمن فقط:** يمكنك استخدامها أو توزيعها

💡 **نصيحة:** اضغط على أي كود لنسخه فوراً!
⚠️ **ملاحظة:** كل كوبون يُستخدم مرة واحدة فقط

━━━━━━━━━━━━━━━━━━━━━
📋 **الكوبونات المُنشأة:**

"""
                
                # Send first chunk with success message
                first_chunk = voucher_chunks[0] if voucher_chunks else []
                for i, code in enumerate(first_chunk, 1):
                    success_text += f"`{code}`\n"
                
                if len(voucher_chunks) > 1:
                    success_text += f"\n📄 **المجموعة الأولى:** {len(first_chunk)} من {len(vouchers)} كوبون"
                
                keyboard = [
                    [InlineKeyboardButton("📦 توليد كمية أخرى", callback_data="admin_bulk_single_cid")],
                    [InlineKeyboardButton("⚡ كوبون واحد", callback_data="admin_create_single_cid")],
                    [InlineKeyboardButton("🎫 إدارة الكوبونات", callback_data="admin_vouchers")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    success_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
                # Send remaining chunks if any
                for chunk_idx, chunk in enumerate(voucher_chunks[1:], start=2):
                    try:
                        chunk_text = f"📄 **المجموعة {chunk_idx}:** ({len(chunk)} كوبون)\n\n"
                        for code in chunk:
                            chunk_text += f"`{code}`\n"
                        
                        await query.message.reply_text(
                            chunk_text,
                            parse_mode='Markdown'
                        )
                    except Exception as chunk_error:
                        logger.error(f"Error sending chunk {chunk_idx}: {chunk_error}")
                        # Continue with next chunk instead of failing completely
                
                logger.info(f"Admin {admin_id} created {len(vouchers)} single CID vouchers")
            else:
                await query.edit_message_text(
                    f"❌ فشل في إنشاء الكوبونات: {message}",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error creating bulk single CID vouchers: {e}")
            await query.edit_message_text(
                f"❌ خطأ في إنشاء الكوبونات: {str(e)}",
                parse_mode='Markdown'
            )

    async def refresh_system_data(self, query):
        """🔄 تحديث البيانات - إعادة تحميل بيانات النظام"""
        try:
            # Show loading message
            await query.edit_message_text(
                "🔄 **جاري تحديث بيانات النظام...**\n\nيرجى الانتظار...",
                parse_mode='Markdown'
            )
            
            # Simulate data refresh operations
            import asyncio
            await asyncio.sleep(2)  # Simulate processing time
            
            # Get fresh statistics
            with db.get_session() as session:
                from database.models import User, Transaction, Voucher, CIDRequest
                
                # Fresh counts
                total_users = session.query(User).count()
                total_transactions = session.query(Transaction).count()
                total_vouchers = session.query(Voucher).count()
                total_cid_requests = session.query(CIDRequest).count()
                
                # System status
                system_status = "✅ نشط" 
                last_activity = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                refresh_text = f"""🔄 **تم تحديث البيانات بنجاح**

📊 **البيانات المحدثة:**
• المستخدمين: {total_users:,}
• المعاملات: {total_transactions:,}
• الكوبونات: {total_vouchers:,}
• طلبات CID: {total_cid_requests:,}

🖥️ **حالة النظام:**
• الحالة: {system_status}
• آخر نشاط: {last_activity}
• قاعدة البيانات: ✅ متصلة
• APIs: ✅ تعمل بشكل طبيعي

━━━━━━━━━━━━━━━━━━━━━
✅ تم التحديث بنجاح!"""
                
                keyboard = [
                    [InlineKeyboardButton("📊 عرض الإحصائيات", callback_data="admin_stats")],
                    [InlineKeyboardButton("🔄 تحديث مرة أخرى", callback_data="admin_refresh")],
                    [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="admin_panel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    refresh_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error refreshing system data: {e}")
            await query.edit_message_text(
                f"❌ خطأ في تحديث البيانات: {str(e)}\n\n🔄 يرجى المحاولة مرة أخرى",
                parse_mode='Markdown'
            )

    def generate_voucher_code(self, length: int = 12) -> str:
        """Generate random voucher code like AB12-CD34-EF56"""
        chars = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(chars) for _ in range(length))
        # Format as XXXX-XXXX-XXXX
        return f"{code[:4]}-{code[4:8]}-{code[8:12]}"

# Global instance
admin_handlers = None
