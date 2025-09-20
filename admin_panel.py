"""
Admin panel for Advanced CID Telegram Bot
Provides comprehensive admin controls and statistics
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from database.database import db
from database.models import User, Transaction, Voucher, CIDRequest, AdminLog
from services.voucher_service import voucher_service
from services.package_service import package_service
from services.payment_service import payment_service
from config import config

logger = logging.getLogger(__name__)

class AdminPanel:
    """Admin panel for bot management"""
    
    def __init__(self, database=None):
        self.admin_ids = config.telegram.admin_ids
        self.db = database or db
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_ids
    
    def get_main_admin_panel_text(self) -> str:
        """Get main admin panel text"""
        stats = self.get_system_statistics()
        
        if "error" in stats:
            return f"🔧 **لوحة الإدارة**\n\n❌ خطأ في جلب الإحصائيات: {stats['error']}"
        
        return f"""🔧 **لوحة الإدارة المتقدمة**
━━━━━━━━━━━━━━━━━━━━━

📊 **نظرة سريعة:**
• إجمالي المستخدمين: {stats['users']['total']:,}
• نشط (24 ساعة): {stats['users']['recent_24h']:,}
• معاملات اليوم: {stats['activity']['recent_transactions']:,}
• صافي الإيرادات: {stats['financial']['net_revenue']:.2f} USD

💎 **خدمة CID:**
• طلبات مكتملة: {stats['cid']['completed']:,}
• معدل النجاح: {stats['cid']['success_rate']}

🎫 **الكوبونات:**
• نشطة: {stats['vouchers']['active']:,}
• مستخدمة: {stats['vouchers']['used']:,}

🕒 **آخر تحديث**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

اختر العملية التي تريد القيام بها:"""
    
    def get_main_admin_keyboard(self) -> InlineKeyboardMarkup:
        """Get main admin panel keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
                InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("🎫 إدارة الكوبونات", callback_data="admin_vouchers"),
                InlineKeyboardButton("📦 إدارة الباقات", callback_data="admin_packages")
            ],
            [
                InlineKeyboardButton("💰 المعاملات المالية", callback_data="admin_transactions"),
                InlineKeyboardButton("🔧 إعدادات النظام", callback_data="admin_settings")
            ],
            [
                InlineKeyboardButton("📝 سجل الأنشطة", callback_data="admin_logs"),
                InlineKeyboardButton("🔄 تحديث البيانات", callback_data="admin_refresh")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_system_statistics(self) -> Dict:
        """Get comprehensive system statistics"""
        try:
            with db.get_session() as session:
                # User statistics
                total_users = session.query(User).count()
                active_users = session.query(User).filter(
                    User.last_activity >= datetime.utcnow() - timedelta(days=30)
                ).count()
                banned_users = session.query(User).filter(User.is_banned == True).count()
                
                # Financial statistics
                total_deposits = session.query(Transaction).filter(
                    Transaction.type == "usdt_deposit",
                    Transaction.status == "completed"
                ).all()
                
                total_deposit_amount = sum(t.amount_usd for t in total_deposits)
                
                # CID statistics
                total_cid_requests = session.query(CIDRequest).count()
                completed_cid_requests = session.query(CIDRequest).filter(
                    CIDRequest.status == "completed"
                ).count()
                failed_cid_requests = session.query(CIDRequest).filter(
                    CIDRequest.status == "failed"
                ).count()
                
                # Package sales
                package_sales = session.query(Transaction).filter(
                    Transaction.type == "cid_purchase",
                    Transaction.status == "completed",
                    Transaction.amount_cid > 0
                ).all()
                
                total_cid_sold = sum(t.amount_cid for t in package_sales)
                total_package_revenue = sum(abs(t.amount_usd) for t in package_sales)
                
                # Voucher statistics
                voucher_stats = voucher_service.get_voucher_stats()
                
                # Recent activity (last 24 hours)
                recent_cutoff = datetime.utcnow() - timedelta(hours=24)
                recent_users = session.query(User).filter(
                    User.last_activity >= recent_cutoff
                ).count()
                
                recent_transactions = session.query(Transaction).filter(
                    Transaction.created_at >= recent_cutoff
                ).count()
                
                return {
                    "users": {
                        "total": total_users,
                        "active": active_users,
                        "banned": banned_users,
                        "recent_24h": recent_users
                    },
                    "financial": {
                        "total_deposits": len(total_deposits),
                        "total_deposit_amount": total_deposit_amount,
                        "total_package_revenue": total_package_revenue,
                        "net_revenue": total_deposit_amount + total_package_revenue
                    },
                    "cid": {
                        "total_requests": total_cid_requests,
                        "completed": completed_cid_requests,
                        "failed": failed_cid_requests,
                        "success_rate": f"{(completed_cid_requests / max(1, total_cid_requests)) * 100:.1f}%",
                        "total_sold": total_cid_sold
                    },
                    "vouchers": voucher_stats,
                    "activity": {
                        "recent_users": recent_users,
                        "recent_transactions": recent_transactions
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get system statistics: {e}")
            return {"error": str(e)}
    
    def get_user_management_stats(self) -> str:
        """Get user management statistics"""
        try:
            with db.get_session() as session:
                total_users = session.query(User).count()
                active_users = session.query(User).filter(
                    User.last_activity >= datetime.utcnow() - timedelta(days=30)
                ).count()
                banned_users = session.query(User).filter(User.is_banned == True).count()
                
                recent_users = session.query(User).filter(
                    User.registered_at >= datetime.utcnow() - timedelta(days=7)
                ).count()
                
                return f"""📊 **إحصائيات المستخدمين:**
• إجمالي المستخدمين: {total_users:,}
• نشط (30 يوم): {active_users:,}
• محظور: {banned_users:,}
• جديد (7 أيام): {recent_users:,}

⚙️ **الإجراءات المتاحة:**
• حظر/إلغاء حظر مستخدم
• تعديل رصيد المستخدم
• عرض تفاصيل المستخدم
• إرسال رسالة لجميع المستخدمين"""
                
        except Exception as e:
            return f"❌ خطأ في جلب بيانات المستخدمين: {str(e)}"
    
    def get_transaction_stats(self) -> str:
        """Get transaction statistics"""
        try:
            with db.get_session() as session:
                # Recent transactions (last 24 hours)
                recent_cutoff = datetime.utcnow() - timedelta(hours=24)
                recent_txs = session.query(Transaction).filter(
                    Transaction.created_at >= recent_cutoff
                ).count()
                
                # Pending transactions
                pending_txs = session.query(Transaction).filter(
                    Transaction.status == "pending"
                ).count()
                
                # Failed transactions
                failed_txs = session.query(Transaction).filter(
                    Transaction.status == "failed"
                ).count()
                
                # Total revenue (last 30 days)
                month_cutoff = datetime.utcnow() - timedelta(days=30)
                recent_deposits = session.query(Transaction).filter(
                    Transaction.type == "usdt_deposit",
                    Transaction.status == "completed",
                    Transaction.created_at >= month_cutoff
                ).all()
                
                monthly_revenue = sum(abs(t.amount_usd) for t in recent_deposits)
                
                return f"""💰 **إحصائيات المعاملات:**
• معاملات آخر 24 ساعة: {recent_txs:,}
• معاملات معلقة: {pending_txs:,}
• معاملات فاشلة: {failed_txs:,}
• إيرادات الشهر: ${monthly_revenue:.2f}

🔧 **الإجراءات المتاحة:**
• مراجعة المعاملات المعلقة
• إعادة معالجة المعاملات الفاشلة
• تصدير تقرير المعاملات
• تحديث حالة المعاملة يدوياً"""
                
        except Exception as e:
            return f"❌ خطأ في جلب بيانات المعاملات: {str(e)}"
    
    def get_voucher_management_stats(self) -> str:
        """Get voucher management statistics"""
        try:
            voucher_stats = voucher_service.get_voucher_stats()
            
            return f"""🎫 **إحصائيات الكوبونات:**
• إجمالي الكوبونات: {voucher_stats.get('total_vouchers', 0):,}
• مستخدمة: {voucher_stats.get('used_vouchers', 0):,}
• متاحة: {voucher_stats.get('active_vouchers', 0):,}
• منتهية الصلاحية: {voucher_stats.get('expired_vouchers', 0):,}

💵 **القيم المالية:**
• إجمالي قيمة الكوبونات: ${voucher_stats.get('total_value', 0):.2f}
• قيمة مستخدمة: ${voucher_stats.get('used_value', 0):.2f}

⚙️ **الإجراءات المتاحة:**
• إنشاء كوبونات جديدة
• إلغاء كوبون
• عرض تفاصيل الكوبون
• تصدير قائمة الكوبونات"""
                
        except Exception as e:
            return f"❌ خطأ في جلب بيانات الكوبونات: {str(e)}"
    
    def get_recent_logs(self) -> str:
        """Get recent system logs"""
        try:
            with db.get_session() as session:
                recent_logs = session.query(AdminLog).order_by(
                    AdminLog.created_at.desc()
                ).limit(10).all()
                
                if not recent_logs:
                    return "📋 **سجلات النظام:**\n\nلا توجد سجلات حديثة"
                
                logs_text = "📋 **آخر 10 سجلات:**\n\n"
                
                for log in recent_logs:
                    time_str = log.created_at.strftime("%m-%d %H:%M")
                    logs_text += f"🔸 `{time_str}` - {log.action}\n"
                    if log.details:
                        logs_text += f"   └ {log.details[:50]}...\n"
                    logs_text += "\n"
                
                logs_text += "\n⚙️ **الإجراءات المتاحة:**\n"
                logs_text += "• عرض السجلات الكاملة\n"
                logs_text += "• تصدير السجلات\n"
                logs_text += "• مسح السجلات القديمة"
                
                return logs_text
                
        except Exception as e:
            return f"❌ خطأ في جلب السجلات: {str(e)}"
    
    def format_statistics_message(self) -> str:
        """Format system statistics for display"""
        stats = self.get_system_statistics()
        
        if "error" in stats:
            return f"❌ خطأ في جلب الإحصائيات: {stats['error']}"
        
        message = f"""
📊 **إحصائيات النظام**
━━━━━━━━━━━━━━━━━━━━━

👥 **المستخدمين**:
• إجمالي المستخدمين: {stats['users']['total']:,}
• نشط (30 يوم): {stats['users']['active']:,}
• محظور: {stats['users']['banned']:,}
• نشاط (24 ساعة): {stats['users']['recent_24h']:,}

💰 **الإحصائيات المالية**:
• إجمالي الإيداعات: {stats['financial']['total_deposits']:,}
• مبلغ الإيداعات: {stats['financial']['total_deposit_amount']:.2f} USD
• إيرادات الباقات: {stats['financial']['total_package_revenue']:.2f} USD
• صافي الإيرادات: {stats['financial']['net_revenue']:.2f} USD

💎 **خدمة CID**:
• إجمالي الطلبات: {stats['cid']['total_requests']:,}
• مكتملة: {stats['cid']['completed']:,}
• فاشلة: {stats['cid']['failed']:,}
• معدل النجاح: {stats['cid']['success_rate']}
• CID مباع: {stats['cid']['total_sold']:,}

🎫 **الكوبونات**:
• إجمالي الكودات: {stats['vouchers']['total']:,}
• مستخدمة: {stats['vouchers']['used']:,}
• نشطة: {stats['vouchers']['active']:,}
• منتهية الصلاحية: {stats['vouchers']['expired']:,}

📈 **النشاط الحديث (24 ساعة)**:
• مستخدمين نشطين: {stats['activity']['recent_users']:,}
• معاملات جديدة: {stats['activity']['recent_transactions']:,}

🕒 **آخر تحديث**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return message
    
    def get_user_management_keyboard(self) -> InlineKeyboardMarkup:
        """Get user management keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("🔍 البحث عن مستخدم", callback_data="admin_search_user"),
                InlineKeyboardButton("👑 قائمة الأدمن", callback_data="admin_list_admins")
            ],
            [
                InlineKeyboardButton("📊 أفضل المستخدمين", callback_data="admin_top_users"),
                InlineKeyboardButton("⛔ المستخدمين المحظورين", callback_data="admin_banned_users")
            ],
            [
                InlineKeyboardButton("💰 تعديل الرصيد", callback_data="admin_adjust_balance"),
                InlineKeyboardButton("🔐 حظر/إلغاء حظر", callback_data="admin_ban_user")
            ],
            [
                InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_voucher_management_keyboard(self) -> InlineKeyboardMarkup:
        """Get voucher management keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("➕ إنشاء كود واحد", callback_data="admin_create_voucher"),
                InlineKeyboardButton("📦 إنشاء كودات متعددة", callback_data="admin_bulk_vouchers")
            ],
            [
                InlineKeyboardButton("🔍 البحث عن كود", callback_data="admin_search_voucher"),
                InlineKeyboardButton("📊 إحصائيات الكودات", callback_data="admin_voucher_stats")
            ],
            [
                InlineKeyboardButton("📋 آخر الكودات المنشأة", callback_data="admin_recent_vouchers"),
                InlineKeyboardButton("⏰ الكودات منتهية الصلاحية", callback_data="admin_expired_vouchers")
            ],
            [
                InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_transaction_management_keyboard(self) -> InlineKeyboardMarkup:
        """Get transaction management keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("💰 آخر الإيداعات", callback_data="admin_recent_deposits"),
                InlineKeyboardButton("🛒 آخر المشتريات", callback_data="admin_recent_purchases")
            ],
            [
                InlineKeyboardButton("❌ المعاملات الفاشلة", callback_data="admin_failed_transactions"),
                InlineKeyboardButton("⏳ المعاملات المعلقة", callback_data="admin_pending_transactions")
            ],
            [
                InlineKeyboardButton("📊 تقرير مالي", callback_data="admin_financial_report"),
                InlineKeyboardButton("🔍 البحث في المعاملات", callback_data="admin_search_transaction")
            ],
            [
                InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_recent_transactions(self, transaction_type: str = None, limit: int = 10) -> List[Transaction]:
        """Get recent transactions"""
        try:
            with db.get_session() as session:
                query = session.query(Transaction)
                
                if transaction_type:
                    query = query.filter(Transaction.type == transaction_type)
                
                transactions = query.order_by(Transaction.created_at.desc()).limit(limit).all()
                return transactions
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {e}")
            return []
    
    def format_transaction_list(self, transactions: List[Transaction], title: str) -> str:
        """Format transaction list for display"""
        if not transactions:
            return f"📝 **{title}**\n\nلا توجد معاملات"
        
        message = f"📝 **{title}**\n\n"
        
        for i, tx in enumerate(transactions, 1):
            user_name = "غير معروف"
            try:
                with db.get_session() as session:
                    user = session.query(User).filter_by(id=tx.user_id).first()
                    if user:
                        user_name = user.username or f"User {user.user_id}"
            except:
                pass
            
            status_emoji = {"completed": "✅", "pending": "⏳", "failed": "❌"}.get(tx.status, "❓")
            type_emoji = {
                "usdt_deposit": "💰",
                "cid_purchase": "💎",
                "voucher_redeem": "🎫"
            }.get(tx.type, "📄")
            
            message += f"""
{i}. {type_emoji} {status_emoji} **{user_name}**
   💵 مبلغ: {tx.amount_usd:.2f} USD
   💎 CID: {tx.amount_cid}
   📅 {tx.created_at.strftime('%Y-%m-%d %H:%M')}
   
"""
        
        return message
    
    def get_admin_logs(self, limit: int = 20) -> List[AdminLog]:
        """Get recent admin logs"""
        try:
            with db.get_session() as session:
                logs = session.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit).all()
                return logs
        except Exception as e:
            logger.error(f"Failed to get admin logs: {e}")
            return []
    
    def format_admin_logs(self) -> str:
        """Format admin logs for display"""
        logs = self.get_admin_logs()
        
        if not logs:
            return "📝 **سجل أنشطة الأدمن**\n\nلا توجد أنشطة مسجلة"
        
        message = "📝 **سجل أنشطة الأدمن**\n\n"
        
        for i, log in enumerate(logs, 1):
            admin_name = f"Admin {log.admin_user_id}"
            target_info = f" -> User {log.target_user_id}" if log.target_user_id else ""
            
            message += f"""
{i}. 👤 **{admin_name}**
   🔧 العملية: {log.action}
   🎯 الهدف: {target_info}
   📝 التفاصيل: {log.details or 'لا توجد تفاصيل'}
   📅 {log.created_at.strftime('%Y-%m-%d %H:%M')}
   
"""
        
        return message
    
    def log_admin_action(self, admin_id: int, action: str, target_user_id: int = None, details: str = None):
        """Log admin action"""
        db.log_admin_action(admin_id, action, target_user_id, details)
    
    def adjust_user_balance(self, admin_id: int, target_user_id: int, cid_amount: int = 0, usd_amount: float = 0.0, reason: str = "") -> Tuple[bool, str]:
        """Adjust user balance (admin function)"""
        try:
            # Get user info for logging
            with db.get_session() as session:
                user = session.query(User).filter_by(user_id=target_user_id).first()
                if not user:
                    return False, "المستخدم غير موجود"
                
                old_cid = user.balance_cid
                old_usd = user.balance_usd
            
            # Update balance
            success = db.update_user_balance(target_user_id, cid_amount, usd_amount)
            
            if success:
                # Create transaction record
                db.create_transaction(
                    user_id=target_user_id,
                    transaction_type="admin_adjust",
                    amount_usd=usd_amount,
                    amount_cid=cid_amount,
                    status="completed",
                    description=f"Admin balance adjustment: {reason}"
                )
                
                # Log admin action
                self.log_admin_action(
                    admin_id=admin_id,
                    action="balance_adjustment",
                    target_user_id=target_user_id,
                    details=f"CID: {old_cid} -> {old_cid + cid_amount}, USD: {old_usd:.2f} -> {old_usd + usd_amount:.2f}. Reason: {reason}"
                )
                
                return True, f"تم تعديل رصيد المستخدم {target_user_id} بنجاح"
            else:
                return False, "فشل في تعديل الرصيد"
                
        except Exception as e:
            logger.error(f"Failed to adjust user balance: {e}")
            return False, f"خطأ في تعديل الرصيد: {str(e)}"
    
    def ban_user(self, admin_id: int, target_user_id: int, ban: bool = True, reason: str = "") -> Tuple[bool, str]:
        """Ban or unban user"""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(user_id=target_user_id).first()
                if not user:
                    return False, "المستخدم غير موجود"
                
                old_status = user.is_banned
                user.is_banned = ban
                session.commit()
                
                action = "ban_user" if ban else "unban_user"
                status_text = "محظور" if ban else "غير محظور"
                
                self.log_admin_action(
                    admin_id=admin_id,
                    action=action,
                    target_user_id=target_user_id,
                    details=f"Status changed from {old_status} to {ban}. Reason: {reason}"
                )
                
                return True, f"تم {'حظر' if ban else 'إلغاء حظر'} المستخدم {target_user_id}"
                
        except Exception as e:
            logger.error(f"Failed to ban/unban user: {e}")
            return False, f"خطأ في {'حظر' if ban else 'إلغاء حظر'} المستخدم: {str(e)}"

# Global admin panel instance
admin_panel = AdminPanel()
