"""
Package management service for Advanced CID Telegram Bot
Handles CID packages, pricing, and purchase operations
"""

import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from config import config
from database.database import db
from database.models import Package, Transaction, PackageReservation, User

logger = logging.getLogger(__name__)

class PackageService:
    """Service for managing CID packages and purchases"""
    
    def __init__(self):
        self.db = db  # Add missing db reference
        self.packages = [
            {'id': 1, 'name': 'باقة صغيرة', 'cid_amount': 30, 'price_sar': 11.25, 'price_usd': 3.00, 'is_active': True},
            {'id': 2, 'name': 'باقة متوسطة', 'cid_amount': 50, 'price_sar': 15.00, 'price_usd': 4.00, 'is_active': True},
            {'id': 3, 'name': 'باقة كبيرة', 'cid_amount': 100, 'price_sar': 26.25, 'price_usd': 7.00, 'is_active': True},
            {'id': 4, 'name': 'باقة مميزة', 'cid_amount': 500, 'price_sar': 112.50, 'price_usd': 30.00, 'is_active': True},
            {'id': 5, 'name': 'باقة متقدمة', 'cid_amount': 1000, 'price_sar': 206.25, 'price_usd': 55.00, 'is_active': True},
            {'id': 6, 'name': 'باقة احترافية', 'cid_amount': 5000, 'price_sar': 937.50, 'price_usd': 250.00, 'is_active': True},
            {'id': 7, 'name': 'باقة ضخمة', 'cid_amount': 10000, 'price_sar': 1687.50, 'price_usd': 450.00, 'is_active': True}
        ]
    
    def get_all_packages(self) -> List[dict]:
        """Get all available packages"""
        return self.packages
    
    def get_package_by_id(self, package_id: int) -> Optional[dict]:
        """Get package by ID"""
        for package in self.packages:
            if package['id'] == package_id and package['is_active']:
                return package
        return None
    
    def format_packages_list(self, currency: str = "sar") -> str:
        """Format packages list for display"""
        packages = self.get_all_packages()
        if not packages:
            return "❌ لا توجد باقات متاحة حالياً"
        
        text = "🧾 الباقات المتاحة\n\n"
        
        for i, package in enumerate(packages, 1):
            # Always show both currencies
            price_usd = f"${package['price_usd']:.2f}"
            price_sar = f"{package['price_sar']} ريال"
            
            text += f"{i}. {package['name']}\n"
            text += f"💎 CID: {package['cid_amount']:,}\n"
            text += f"💰 السعر: {price_usd} ({price_sar})\n"
            if package['cid_amount'] >= 100:
                savings = round((package['price_sar'] / package['cid_amount']) * 25 - 20, 2)
                if savings < 0:
                    text += f"💸 توفير: {abs(savings)} ريال\n"
            text += "\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━\n"
        text += "💡 لشراء باقة: استخدم الأزرار أدناه\n"
        text += "🎯 أو تواصل معنا للدفع اليدوي"
        
        return text
    
    def format_package_purchase_options(self, user_id: int, currency="sar") -> str:
        """Format package purchase options with smart pricing based on user balance"""
        packages = self.get_all_packages()
        
        # Get user balance
        try:
            cid_balance, usd_balance = db.get_user_balance(user_id)
        except:
            cid_balance, usd_balance = 0, 0.0
        
        # Check for active reservation
        reservation = self.get_active_reservation(user_id)
        
        text = f"""📦 باقات CID المتاحة━━━━━━━━━━━━━━━━━━━━━

💳 رصيدك الحالي: {usd_balance:.2f} USD
"""
        
        if reservation:
            text += f"""⏰ لديك حجز نشط:📦 {reservation['package'].name}
💰 المطلوب دفع: ${reservation['required_amount']:.2f}
⏳ ينتهي في: {(reservation['expires_at'] - datetime.utcnow()).total_seconds() / 60:.0f} دقيقة

"""
        
        text += "\n"
        
        for i, package in enumerate(packages, 1):
            if currency.lower() == "usd":
                price = f"${package['price_usd']:.2f}"
            else:
                price = f"{package['price_sar']} ريال"
            
            # Calculate what user needs to pay
            needed_amount = max(0, package['price_usd'] - usd_balance)
            
            text += f"{i}. {package['name']}\n"
            text += f"💎 CID: {package['cid_amount']:,}\n"
            text += f"💰 السعر الكامل: {price}\n"
            
            if needed_amount > 0:
                text += f"💸 المطلوب دفع: ${needed_amount:.2f}\n"
            else:
                text += f"✅ يمكن الشراء من الرصيد\n"
            
            if package['cid_amount'] >= 100:
                savings = round((package['price_sar'] / package['cid_amount']) * 25 - 20, 2)
                if savings < 0:
                    text += f"💸 توفير: {abs(savings)} ريال\n"
            text += "\n"
        
        if not reservation:
            text += """━━━━━━━━━━━━━━━━━━━━━
💡 لحجز باقة: /buy1, /buy2, /buy3...
💳 عرض الرصيد: /balance
📈 سجل المشتريات: /history

🎯 كيف يعمل النظام الجديد:1️⃣ تختار الباقة المطلوبة
2️⃣ ندفع المبلغ المطلوب بالضبط
3️⃣ تحصل على الباقة فوراً!"""
        else:
            text += """━━━━━━━━━━━━━━━━━━━━━
⚠️ لديك حجز نشط - ادفع المبلغ المطلوب أو اختر باقة جديدة"""
        
        return text
    
    def calculate_package_details(self, package_id: int) -> Optional[Dict]:
        """Calculate package details and costs"""
        package = self.get_package_by_id(package_id)
        
        if not package:
            return None
        
        base_cost_usd = config.pidkey.cost_per_cid
        base_cost_sar = base_cost_usd * config.usd_to_sar
        
        per_cid_cost_usd = package['price_usd'] / package['cid_amount']
        per_cid_cost_sar = package['price_sar'] / package['cid_amount']
        
        discount_usd = max(0, (1 - (per_cid_cost_usd / base_cost_usd)) * 100) if base_cost_usd > 0 else 0
        discount_sar = max(0, (1 - (per_cid_cost_sar / base_cost_sar)) * 100) if base_cost_sar > 0 else 0
        
        savings_usd = max(0, (base_cost_usd * package['cid_amount']) - package['price_usd'])
        savings_sar = max(0, (base_cost_sar * package['cid_amount']) - package['price_sar'])
        
        return {
            "package": package,
            "per_cid_cost_usd": per_cid_cost_usd,
            "per_cid_cost_sar": per_cid_cost_sar,
            "discount_usd": discount_usd,
            "discount_sar": discount_sar,
            "savings_usd": savings_usd,
            "savings_sar": savings_sar,
            "base_cost_usd": base_cost_usd,
            "base_cost_sar": base_cost_sar
        }
    
    def format_package_details(self, package_id: int) -> str:
        """Format detailed package information"""
        details = self.calculate_package_details(package_id)
        
        if not details:
            return "❌ الباقة غير موجودة"
        
        pkg = details["package"]
        
        message = f"""
💎 تفاصيل {pkg['name']}━━━━━━━━━━━━━━━━━━━━━

🔢 المحتوى: {pkg['cid_amount']:,} CID
💰 السعر: {pkg['price_usd']:.2f} USD ({pkg['price_sar']:.2f} ر.س)

📊 تحليل التكلفة:• تكلفة الـ CID الواحد: {details['per_cid_cost_usd']:.3f} USD
• التكلفة الأساسية: {details['base_cost_usd']:.3f} USD لكل CID
"""
        
        if details["discount_usd"] > 1:
            message += f"""
🎯 الوفورات:• نسبة الخصم: {details['discount_usd']:.1f}%
• توفر: {details['savings_usd']:.2f} USD ({details['savings_sar']:.2f} ر.س)
"""
        
        message += f"""
⭐ المميزات:• تفعيل فوري بعد الشراء
• صالح لجميع إصدارات Microsoft Office
• دعم فني متكامل
• ضمان استرداد المال خلال 24 ساعة

🛒 للشراء: `/buy_{pkg.id}`
"""
        
        return message
    
    def get_user_transactions(self, user_id: int, limit: int = 10) -> List:
        """Get user transactions"""
        try:
            with self.db.get_session() as session:
                transactions = session.query(Transaction).filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(limit).all()
                return [self.db._transaction_to_dict(tx) for tx in transactions]
        except Exception as e:
            logger.error(f"Error getting user transactions: {e}")
            return []

    def purchase_package(self, user_id: int, package_id: int) -> dict:
        """Purchase a package for user"""
        try:
            with db.get_session() as session:
                # Get user
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return False, "المستخدم غير موجود", None
                
                # Get package from self.packages instead of database
                package = self.get_package_by_id(package_id)
                if not package:
                    return False, "الباقة غير موجودة أو غير متاحة", None
                
                # Get current balance
                cid_balance, usd_balance = db.get_user_balance(user_id)
                
                # Check balance
                if usd_balance < package['price_usd']:
                    needed = package['price_usd'] - usd_balance
                    insufficient_balance_msg = f"""❌ رصيد غير كافي لشراء الباقة

━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 تفاصيل الرصيد:
• المطلوب: ${package['price_usd']:.2f}
• الرصيد الحالي: ${usd_balance:.2f}
• النقص: ${needed:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 حلول لإكمال الشراء:

1️⃣ شحن الرصيد عبر Binance
   • استخدم `/recharge {needed:.2f}` أو أكثر
   • الدفع بـ USDT (TRC20)
   • سريع وآمن ✅

2️⃣ الدفع عبر الموقع الإلكتروني
   • مدى • فيزا • ماستر كارد
   • STC Pay
   • رابط: https://tf3eel.com/ar/TelegramCID

3️⃣ التواصل مع الإدارة
   • استخدم `/contact` للتواصل مع الأدمن
   • طرق دفع إضافية متاحة 💳
   • دعم شخصي مباشر 👨‍💻

🎯 اختر الطريقة الأنسب لك!"""
                    return False, insufficient_balance_msg, None
                
                # Create transaction
                transaction_id = db.create_transaction(
                    user_id=user_id,
                    transaction_type="cid_purchase",
                    amount_usd=-package['price_usd'],  # Negative for purchase
                    amount_cid=package['cid_amount'],
                    status="pending",
                    description=f"Purchase {package['name']} - {package['cid_amount']} CID for {package['price_usd']} USD"
                )
            
            if not transaction_id:
                return False, "فشل في إنشاء المعاملة", None
            
            # Update user balance
            success = db.add_user_balance(
                user_id=user_id,
                cid_amount=package['cid_amount'],
                usd_amount=-package['price_usd']
            )
            
            if success:
                # Mark transaction as completed
                db.update_transaction_status(
                    transaction_id,
                    "completed",
                    completed_at=datetime.utcnow()
                )
                
                logger.info(f"Package purchased successfully: User {user_id}, Package {package_id}")
                
                # Get updated balance
                new_cid_balance, new_usd_balance = db.get_user_balance(user_id)
                
                success_msg = f"""
✅ تم شراء الباقة بنجاح!
📦 الباقة: {package['name']}
💎 CID المضاف: {package['cid_amount']:,}
💰 المبلغ المدفوع: {package['price_usd']:.2f} USD

💳 رصيدك الحالي:
• CID: {new_cid_balance:,}
• USD: {new_usd_balance:.2f}

🎯 يمكنك الآن استخدام خدمة CID لتفعيل Microsoft Office
📸 أرسل صورة Installation ID للبدء
"""
                return True, success_msg, transaction_id
            else:
                # Mark transaction as failed
                db.update_transaction_status(
                    transaction_id,
                    "failed",
                    completed_at=datetime.utcnow()
                )
                return False, "فشل في تحديث الرصيد", None
                
        except Exception as e:
            logger.error(f"Package purchase error: {e}")
            return False, f"خطأ في شراء الباقة: {str(e)}", None
    
    def reserve_package(self, user_id: int, package_id: int) -> dict:
        """Reserve a package for targeted payment"""
        try:
            with db.get_session() as session:
                # Get user current balance
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return {"success": False, "message": "المستخدم غير موجود"}
                
                # Get package
                package = config.get_package_by_id(package_id)
                if not package:
                    return {"success": False, "message": "الباقة غير موجودة"}
                
                # Calculate required payment
                current_balance = user.balance_usd
                required_amount = max(0, package.price_usd - current_balance)
                
                # Cancel any existing active reservations for this user
                session.query(PackageReservation).filter_by(
                    user_id=user.id, 
                    status='active'
                ).update({'status': 'cancelled'})
                
                # Create new reservation
                from datetime import timedelta
                reservation = PackageReservation(
                    user_id=user.id,
                    package_id=package_id,
                    required_amount=required_amount,
                    expires_at=datetime.utcnow() + timedelta(minutes=30)
                )
                
                session.add(reservation)
                session.commit()
                
                return {
                    "success": True,
                    "reservation_id": reservation.id,
                    "package": package,
                    "current_balance": current_balance,
                    "required_payment": required_amount,
                    "total_package_price": package.price_usd,
                    "expires_at": reservation.expires_at
                }
                
        except Exception as e:
            logger.error(f"Package reservation error: {e}")
            return {"success": False, "message": f"خطأ في حجز الباقة: {str(e)}"}
    
    def get_active_reservation(self, user_id: int) -> dict:
        """Get user's active package reservation"""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return None
                
                reservation = session.query(PackageReservation).filter_by(
                    user_id=user.id,
                    status='active'
                ).filter(
                    PackageReservation.expires_at > datetime.utcnow()
                ).first()
                
                if not reservation:
                    return None
                
                package = config.get_package_by_id(reservation.package_id)
                
                return {
                    "reservation_id": reservation.id,
                    "package_id": reservation.package_id,
                    "package": package,
                    "required_amount": reservation.required_amount,
                    "expires_at": reservation.expires_at,
                    "created_at": reservation.created_at
                }
                
        except Exception as e:
            logger.error(f"Get reservation error: {e}")
            return None
    
    def complete_reservation(self, user_id: int, txid: str, paid_amount: float) -> dict:
        """Complete a package reservation with payment"""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return {"success": False, "message": "المستخدم غير موجود"}
                
                reservation = session.query(PackageReservation).filter_by(
                    user_id=user.id,
                    status='active'
                ).filter(
                    PackageReservation.expires_at > datetime.utcnow()
                ).first()
                
                if not reservation:
                    return {"success": False, "message": "لا يوجد حجز نشط"}
                
                package = config.get_package_by_id(reservation.package_id)
                if not package:
                    return {"success": False, "message": "الباقة غير موجودة"}
                
                # Verify payment amount
                if abs(paid_amount - reservation.required_amount) > 0.01:  # Allow 1 cent tolerance
                    return {
                        "success": False, 
                        "message": f"المبلغ المدفوع غير صحيح\nالمطلوب: ${reservation.required_amount:.2f}\nالمدفوع: ${paid_amount:.2f}"
                    }
                
                # Update user balance (add paid amount first)
                if reservation.required_amount > 0:
                    user.balance_usd += paid_amount
                
                # Purchase the package
                if user.balance_usd >= package.price_usd:
                    # Deduct package cost and add CID
                    user.balance_usd -= package.price_usd
                    user.balance_cid += package.cid_amount
                    
                    # Mark reservation as completed
                    reservation.status = 'completed'
                    reservation.payment_txid = txid
                    reservation.completed_at = datetime.utcnow()
                    
                    # Create transaction record
                    transaction = Transaction(
                        user_id=user.id,
                        type='package_purchase_reserved',
                        amount_usd=package.price_usd,
                        amount_cid=package.cid_amount,
                        status='completed',
                        txid=txid,
                        description=f"Package purchase via reservation: {package.name}",
                        completed_at=datetime.utcnow()
                    )
                    session.add(transaction)
                    
                    session.commit()
                    
                    return {
                        "success": True,
                        "message": f"تم شراء {package.name} بنجاح!",
                        "package": package,
                        "new_cid_balance": user.balance_cid,
                        "new_usd_balance": user.balance_usd,
                        "transaction_id": transaction.id
                    }
                else:
                    return {"success": False, "message": "رصيد غير كافي حتى بعد الدفع"}
                    
        except Exception as e:
            logger.error(f"Complete reservation error: {e}")
            return {"success": False, "message": f"خطأ في إكمال الشراء: {str(e)}"}
    
    def cleanup_expired_reservations(self):
        """Clean up expired reservations"""
        try:
            with db.get_session() as session:
                expired_count = session.query(PackageReservation).filter(
                    PackageReservation.status == 'active',
                    PackageReservation.expires_at < datetime.utcnow()
                ).update({'status': 'expired'})
                
                session.commit()
                logger.info(f"Cleaned up {expired_count} expired reservations")
                
        except Exception as e:
            logger.error(f"Cleanup expired reservations error: {e}")
    
    def get_user_purchase_history(self, user_id: int, limit: int = 10) -> List[dict]:
        """Get user's package purchase history"""
        try:
            with db.get_session() as session:
                user = session.query(db.User).filter_by(user_id=user_id).first()
                if not user:
                    return []
                
                transactions = session.query(Transaction).filter(
                    Transaction.user_id == user.id,
                    Transaction.type == "cid_purchase",
                    Transaction.status == "completed"
                ).order_by(Transaction.completed_at.desc()).limit(limit).all()
                
                # Convert to dictionaries to avoid session binding issues
                result = []
                for tx in transactions:
                    result.append({
                        'id': tx.id,
                        'amount_cid': tx.amount_cid or 0,
                        'amount_usd': tx.amount_usd or 0.0,
                        'completed_at': tx.completed_at,
                        'type': tx.type,
                        'status': tx.status,
                        'description': tx.description
                    })
                
                return result
        except Exception as e:
            logger.error(f"Failed to get purchase history: {e}")
            return []
    
    def format_purchase_history(self, user_id: int) -> str:
        """Format user's purchase history"""
        try:
            history = self.get_user_purchase_history(user_id)
            
            if not history:
                return "📝 لا يوجد تاريخ شراء"
            
            message = "📋 تاريخ مشترياتك:\n\n"
            
            for i, transaction in enumerate(history, 1):
                try:
                    date_str = transaction['completed_at'].strftime('%Y-%m-%d %H:%M')
                    message += f"""
{i}. 💎 CID: {transaction['amount_cid']:,}
   💰 المبلغ: {abs(transaction['amount_usd']):.2f} USD
   📅 التاريخ: {date_str}
   
"""
                except Exception as e:
                    logger.error(f"Error formatting transaction {transaction}: {e}")
                    continue
            
            # Calculate totals
            total_cid = sum(t['amount_cid'] for t in history if t['amount_cid'])
            total_usd = sum(abs(t['amount_usd']) for t in history if t['amount_usd'])
            
            message += f"""
📊 الإجمالي:
• إجمالي CID: {total_cid:,}
• إجمالي الإنفاق: {total_usd:.2f} USD
"""
            return message
        except Exception as e:
            logger.error(f"Error in format_purchase_history: {e}")
            return "❌ حدث خطأ في استرجاع التاريخ، حاول مرة أخرى أو تواصل مع الدعم الفني /contact"
        
        return message
    
    def get_package_statistics(self) -> Dict:
        """Get package sales statistics"""
        try:
            with db.get_session() as session:
                stats = {}
                
                # Get sales per package
                packages = self.get_all_packages()
                for package in packages:
                    sales_count = session.query(Transaction).filter(
                        Transaction.type == "cid_purchase",
                        Transaction.status == "completed",
                        Transaction.amount_cid == package.cid_amount
                    ).count()
                    
                    total_revenue = session.query(Transaction.amount_usd).filter(
                        Transaction.type == "cid_purchase",
                        Transaction.status == "completed",
                        Transaction.amount_cid == package.cid_amount
                    ).all()
                    
                    revenue = sum(abs(t[0]) for t in total_revenue) if total_revenue else 0
                    
                    stats[package.id] = {
                        "name": package.name,
                        "sales_count": sales_count,
                        "revenue": revenue,
                        "cid_sold": sales_count * package.cid_amount
                    }
                
                return stats
        except Exception as e:
            logger.error(f"Failed to get package statistics: {e}")
            return {}
    
    def format_package_stats(self) -> str:
        """Format package statistics for admin"""
        stats = self.get_package_statistics()
        
        if not stats:
            return "❌ لا توجد إحصائيات متاحة"
        
        message = "📊 إحصائيات الباقات:\n\n"
        
        total_sales = 0
        total_revenue = 0
        total_cid_sold = 0
        
        for package_id, data in stats.items():
            total_sales += data["sales_count"]
            total_revenue += data["revenue"]
            total_cid_sold += data["cid_sold"]
            
            message += f"""
📦 {data['name']}:
   🛒 مبيعات: {data['sales_count']}
   💰 إيراد: {data['revenue']:.2f} USD
   💎 CID مباع: {data['cid_sold']:,}

"""
        
        message += f"""
🏆 الإجمالي العام:
• إجمالي المبيعات: {total_sales}
• إجمالي الإيرادات: {total_revenue:.2f} USD
• إجمالي CID مباع: {total_cid_sold:,}
"""
        
        return message

# Global package service instance
package_service = PackageService()
