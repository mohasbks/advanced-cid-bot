"""
Voucher management service for Advanced CID Telegram Bot
Handles voucher creation, validation, and redemption
"""

import random
import string
import logging
from typing import Optional, Tuple, List
from datetime import datetime, timedelta

from database.database import db
from database.models import Voucher, VoucherUse

logger = logging.getLogger(__name__)

class VoucherService:
    """Service for managing voucher codes"""
    
    def __init__(self):
        self.code_length = 12
        self.code_prefix = "CID"
    
    def generate_voucher_code(self) -> str:
        """Generate a unique voucher code"""
        while True:
            # Generate random alphanumeric code
            random_part = ''.join(random.choices(
                string.ascii_uppercase + string.digits, 
                k=self.code_length - len(self.code_prefix)
            ))
            code = f"{self.code_prefix}{random_part}"
            
            # Check if code already exists
            with db.get_session() as session:
                existing = session.query(Voucher).filter_by(code=code).first()
                if not existing:
                    return code
    
    def create_voucher(self, cid_amount: int, usd_amount: float, admin_id: int, 
                      expires_days: int = None, custom_code: str = None) -> Tuple[bool, str, Optional[Voucher]]:
        """
        Create a new voucher
        Returns (success, message, voucher)
        """
        try:
            # Use custom code or generate new one
            code = custom_code if custom_code else self.generate_voucher_code()
            
            # Validate custom code if provided
            if custom_code:
                if len(custom_code) < 6 or len(custom_code) > 20:
                    return False, "كود الشحن يجب أن يكون بين 6-20 حرف", None
                
                # Check if custom code already exists
                with db.get_session() as session:
                    existing = session.query(Voucher).filter_by(code=custom_code).first()
                    if existing:
                        return False, "هذا الكود مستخدم بالفعل", None
            
            # Validate amounts
            if cid_amount < 0 or usd_amount < 0:
                return False, "القيم يجب أن تكون موجبة", None
            
            if cid_amount == 0 and usd_amount == 0:
                return False, "يجب أن يحتوي الكود على قيمة CID أو USD على الأقل", None
            
            # Create voucher
            voucher = db.create_voucher(
                code=code,
                cid_amount=cid_amount,
                usd_amount=usd_amount,
                admin_id=admin_id,
                expires_days=expires_days
            )
            
            if voucher:
                logger.info(f"Voucher created by admin {admin_id}: {code}")
                return True, f"تم إنشاء كود الشحن بنجاح: {code}", voucher
            else:
                return False, "فشل في إنشاء كود الشحن", None
                
        except Exception as e:
            logger.error(f"Failed to create voucher: {e}")
            return False, f"خطأ في إنشاء كود الشحن: {str(e)}", None
    
    def redeem_voucher(self, code: str, user_id: int) -> Tuple[bool, str, Optional[Voucher]]:
        """
        Redeem a voucher code
        Returns (success, message, voucher)
        """
        try:
            # Ensure code is string and clean it
            clean_code = str(code).strip().upper()
            
            if len(clean_code) < 6:
                return False, "كود الشحن غير صالح", None
            
            with db.get_session() as session:
                # Check if user already used this voucher
                existing_use = session.query(VoucherUse).join(Voucher).filter(
                    Voucher.code == clean_code,
                    VoucherUse.user_id == user_id
                ).first()
                
                if existing_use:
                    return False, "لقد استخدمت هذا الكود من قبل", None
            
            # Redeem voucher - ensure we handle the return values properly
            result = db.redeem_voucher(clean_code, user_id)
            if len(result) == 3:
                success, message, voucher = result
            else:
                # Fallback for unexpected return format
                success, message = result[0], result[1]
                voucher = result[2] if len(result) > 2 else None
            
            if success and voucher:
                # Log admin action if it's an admin-created voucher
                if voucher.get('created_by_admin'):
                    db.log_admin_action(
                        admin_id=voucher['created_by_admin'],
                        action="voucher_redeemed",
                        target_user_id=user_id,
                        details=f"Voucher {clean_code} redeemed for {voucher['cid_amount']} CID"
                    )
                
                logger.info(f"Voucher redeemed by user {user_id}: {clean_code}")
                return True, f"✅ تم شحن رصيدك بـ {voucher['cid_amount']:,} CID", voucher
            
        except Exception as e:
            logger.error(f"Voucher redemption error: {e}")
            return False, "حدث خطأ أثناء استخدام كود الشحن", None
    
    def validate_voucher(self, code: str) -> Tuple[bool, str, Optional[Voucher]]:
        """
        Validate voucher without redeeming it
        Returns (is_valid, message, voucher)
        """
        try:
            clean_code = code.strip().upper()
            
            with db.get_session() as session:
                voucher = session.query(Voucher).filter_by(code=clean_code).first()
                
                if not voucher:
                    return False, "كود الشحن غير موجود", None
                
                if voucher.is_used:
                    return False, "تم استخدام هذا الكود من قبل", voucher
                
                if voucher.expires_at and voucher.expires_at < datetime.utcnow():
                    return False, "انتهت صلاحية هذا الكود", voucher
                
                return True, "كود الشحن صالح للاستخدام", voucher
                
        except Exception as e:
            logger.error(f"Voucher validation error: {e}")
            return False, "خطأ في التحقق من كود الشحن", None
    
    def get_voucher_info(self, code: str) -> Optional[str]:
        """Get voucher information for display"""
        try:
            is_valid, message, voucher = self.validate_voucher(code)
            
            if not voucher:
                return f"❌ {message}"
            
            status_emoji = "✅" if is_valid else "❌"
            status_text = "صالح" if is_valid else "غير صالح"
            
            info = f"""
{status_emoji} معلومات كود الشحن

🎫 الكود: `{voucher.code}`
💎 CID: {voucher.cid_amount}
💰 USD: {voucher.usd_amount:.2f}
📊 الحالة: {status_text}
📅 تاريخ الإنشاء: {voucher.created_at.strftime('%Y-%m-%d %H:%M')}
"""
            
            if voucher.expires_at:
                info += f"⏰ تاريخ الانتهاء: {voucher.expires_at.strftime('%Y-%m-%d %H:%M')}\n"
            else:
                info += "⏰ تاريخ الانتهاء: لا ينتهي\n"
            
            if not is_valid:
                info += f"\n❗ السبب: {message}"
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting voucher info: {e}")
            return f"❌ خطأ في جلب معلومات الكود: {str(e)}"
    
    def create_bulk_vouchers(self, count: int, cid_amount: int, usd_amount: float, 
                           admin_id: int, expires_days: int = None, prefix: str = None) -> Tuple[bool, str, List[str]]:
        """
        Create multiple vouchers at once
        Returns (success, message, voucher_codes)
        """
        try:
            if count < 1 or count > 100:
                return False, "يمكن إنشاء من 1 إلى 100 كود في المرة الواحدة", []
            
            if cid_amount < 0 or usd_amount < 0:
                return False, "القيم يجب أن تكون موجبة", []
            
            if cid_amount == 0 and usd_amount == 0:
                return False, "يجب أن يحتوي الكود على قيمة CID أو USD على الأقل", []
            
            created_codes = []
            
            # Use custom prefix if provided
            original_prefix = self.code_prefix
            if prefix:
                self.code_prefix = prefix.upper()
            
            try:
                for i in range(count):
                    success, message, voucher = self.create_voucher(
                        cid_amount=cid_amount,
                        usd_amount=usd_amount,
                        admin_id=admin_id,
                        expires_days=expires_days
                    )
                    
                    if success and voucher:
                        created_codes.append(voucher.code)
                    else:
                        logger.warning(f"Failed to create voucher {i+1}/{count}: {message}")
                
            finally:
                # Restore original prefix
                self.code_prefix = original_prefix
            
            if created_codes:
                db.log_admin_action(
                    admin_id=admin_id,
                    action="bulk_vouchers_created",
                    details=f"Created {len(created_codes)} vouchers - CID: {cid_amount}, USD: {usd_amount}"
                )
                
                logger.info(f"Admin {admin_id} created {len(created_codes)} vouchers")
                return True, f"تم إنشاء {len(created_codes)} كود شحن بنجاح", created_codes
            else:
                return False, "فشل في إنشاء أي كود شحن", []
                
        except Exception as e:
            logger.error(f"Bulk voucher creation error: {e}")
            return False, f"خطأ في إنشاء الكودات: {str(e)}", []
    
    def get_voucher_stats(self) -> dict:
        """Get voucher statistics"""
        try:
            with db.get_session() as session:
                total_vouchers = session.query(Voucher).count()
                used_vouchers = session.query(Voucher).filter_by(is_used=True).count()
                active_vouchers = session.query(Voucher).filter(
                    Voucher.is_used == False,
                    (Voucher.expires_at.is_(None) | (Voucher.expires_at > datetime.utcnow()))
                ).count()
                
                expired_vouchers = session.query(Voucher).filter(
                    Voucher.is_used == False,
                    Voucher.expires_at < datetime.utcnow()
                ).count()
                
                # Calculate total value
                from sqlalchemy import func
                total_cid_value = session.query(func.sum(Voucher.cid_amount)).filter_by(is_used=False).scalar() or 0
                total_usd_value = session.query(func.sum(Voucher.usd_amount)).filter_by(is_used=False).scalar() or 0
                
                return {
                    "total": total_vouchers,
                    "used": used_vouchers,
                    "active": active_vouchers,
                    "expired": expired_vouchers,
                    "total_cid_value": total_cid_value,
                    "total_usd_value": total_usd_value
                }
                
        except Exception as e:
            logger.error(f"Error getting voucher stats: {e}")
            return {
                "total": 0,
                "used": 0,
                "active": 0,
                "expired": 0,
                "total_cid_value": 0,
                "total_usd_value": 0.0
            }
    
    def format_voucher_list(self, codes: List[str]) -> str:
        """Format voucher codes for display"""
        if not codes:
            return "لا توجد كودات"
        
        formatted = "📋 كودات الشحن المنشأة:\n\n"
        
        for i, code in enumerate(codes, 1):
            formatted += f"`{code}`\n"
            
            # Add line break every 10 codes for readability
            if i % 10 == 0 and i < len(codes):
                formatted += "\n"
        
        formatted += f"\n📊 العدد الإجمالي: {len(codes)} كود"
        
        return formatted

# Global voucher service instance
voucher_service = VoucherService()
