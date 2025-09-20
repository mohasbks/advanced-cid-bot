"""
Payment verification service for USDT TRC20 transactions
Uses Tronscan API to verify payments
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import aiohttp
from decimal import Decimal

from config import config
from database.database import db
from services.package_service import PackageService

logger = logging.getLogger(__name__)

class PaymentService:
    """Service for handling USDT TRC20 payment verification"""
    
    def __init__(self):
        self.tronscan_api = config.binance.tronscan_api_url
        self.wallet_address = config.binance.usdt_trc20_address
        self.confirmation_blocks = config.binance.confirmation_blocks
        
        # USDT TRC20 contract address on TRON network
        self.usdt_contract = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    
    async def verify_payment(self, txid: str) -> Tuple[bool, Dict]:
        """
        Verify USDT TRC20 payment using transaction ID
        Returns (is_valid, transaction_data)
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Get transaction details
                tx_url = f"{self.tronscan_api}/transaction-info?hash={txid}"
                
                async with session.get(tx_url) as response:
                    if response.status != 200:
                        logger.error(f"Tronscan API error: {response.status}")
                        return False, {"error": "API request failed"}
                    
                    tx_data = await response.json()
                    
                    # Check if transaction exists
                    if not tx_data or "hash" not in tx_data:
                        return False, {"error": "Transaction not found"}
                    
                    # Verify transaction details
                    verification_result = self._verify_transaction_details(tx_data)
                    
                    if verification_result["is_valid"]:
                        # Check if already processed
                        if db.is_txid_used(txid):
                            return False, {"error": "Transaction already processed"}
                    
                    return verification_result["is_valid"], verification_result
        
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            return False, {"error": str(e)}
    
    def _verify_transaction_details(self, tx_data: Dict) -> Dict:
        """Verify transaction details"""
        try:
            result = {
                "is_valid": False,
                "amount": 0.0,
                "from_address": "",
                "to_address": "",
                "timestamp": 0,
                "confirmations": 0,
                "contract_address": "",
                "error": ""
            }
            
            # Check if transaction is confirmed
            if not tx_data.get("confirmed", False):
                result["error"] = "Transaction not confirmed"
                return result
            
            # Get confirmations
            current_block = self._get_latest_block_number()
            tx_block = tx_data.get("blockNumber", 0)
            confirmations = current_block - tx_block if current_block > 0 else 0
            
            result["confirmations"] = confirmations
            
            if confirmations < self.confirmation_blocks:
                result["error"] = f"Insufficient confirmations: {confirmations}/{self.confirmation_blocks}"
                return result
            
            # Check if it's a TRC20 token transfer
            trc20_transfers = tx_data.get("trc20TransferInfo", [])
            
            if not trc20_transfers:
                result["error"] = "No TRC20 transfers found"
                return result
            
            # Find USDT transfer to our wallet
            usdt_transfer = None
            for transfer in trc20_transfers:
                if (transfer.get("contract_address") == self.usdt_contract and 
                    transfer.get("to_address") == self.wallet_address):
                    usdt_transfer = transfer
                    break
            
            if not usdt_transfer:
                result["error"] = "No USDT transfer to specified wallet found"
                return result
            
            # Extract transfer details
            amount_raw = usdt_transfer.get("quant", "0")
            # USDT has 6 decimal places on TRON
            amount = float(Decimal(amount_raw) / Decimal(10**6))
            
            result.update({
                "is_valid": True,
                "amount": amount,
                "from_address": usdt_transfer.get("from_address", ""),
                "to_address": usdt_transfer.get("to_address", ""),
                "timestamp": tx_data.get("timestamp", 0),
                "contract_address": usdt_transfer.get("contract_address", ""),
                "tx_fee": tx_data.get("cost", {}).get("net_fee", 0)
            })
            
            # Minimum amount validation
            min_amount = float(db.get_system_setting("min_usdt_deposit", "5.0"))
            if amount < min_amount:
                result["is_valid"] = False
                result["error"] = f"Amount too small: {amount} < {min_amount}"
            
            return result
            
        except Exception as e:
            logger.error(f"Transaction verification error: {e}")
            return {
                "is_valid": False,
                "error": f"Verification failed: {str(e)}",
                "amount": 0.0,
                "from_address": "",
                "to_address": "",
                "timestamp": 0,
                "confirmations": 0,
                "contract_address": ""
            }
    
    def _get_latest_block_number(self) -> int:
        """Get latest block number from Tronscan"""
        try:
            response = requests.get(f"{self.tronscan_api}/system/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("database", {}).get("block", 0)
        except Exception as e:
            logger.error(f"Failed to get latest block: {e}")
        return 0
    
    async def process_payment(self, user_id: int, txid: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Process and verify a payment - handles both general deposits and reserved packages
        Returns (success, message, transaction_data)
        """
        try:
            # Verify payment
            is_valid, tx_data = await self.verify_payment(txid)
            
            if not is_valid:
                error_msg = tx_data.get("error", "Payment verification failed")
                logger.warning(f"Payment verification failed for {txid}: {error_msg}")
                return False, f"فشل في التحقق من الدفع: {error_msg}", None
            
            paid_amount = tx_data["amount"]
            
            # Check if user has an active package reservation
            package_service = PackageService()
            reservation = package_service.get_active_reservation(user_id)
            
            if reservation and abs(paid_amount - reservation["required_amount"]) <= 0.01:
                # This is a targeted payment for a reserved package
                result = package_service.complete_reservation(user_id, txid, paid_amount)
                
                if result["success"]:
                    success_msg = f"""✅ تم شراء الباقة بنجاح!

                    الباقة: {result['package'].name}
                    💎 CID المضافة: {result['package'].cid_amount:,}
                    💰 المبلغ المدفوع: ${paid_amount:.2f}

                    💳 رصيدك الجديد:
                    • CID: {result['new_cid_balance']:,}
                    • USD: {result['new_usd_balance']:.2f}"""

                    logger.info(f"Reserved package payment completed: {txid} - {paid_amount} USDT for user {user_id}")
                    return True, success_msg, tx_data
                else:
                    return False, f"فشل في إكمال شراء الباقة: {result['message']}", None
            
            else:
                # Regular deposit to user balance
                transaction = db.create_transaction(
                    user_id=user_id,
                    transaction_type="usdt_deposit",
                    amount_usd=paid_amount,
                    status="pending",
                    txid=txid,
                    from_address=tx_data["from_address"],
                    to_address=tx_data["to_address"],
                    description=f"USDT TRC20 deposit: {paid_amount} USDT"
                )
                
                if not transaction:
                    return False, "فشل في إنشاء المعاملة", None
                
                # Update user balance
                success = db.update_user_balance(user_id, usd_amount=paid_amount)
                
                if success:
                    # Mark transaction as completed
                    db.update_transaction_status(
                        transaction.id, 
                        "completed",
                        completed_at=datetime.utcnow()
                    )
                    
                    logger.info(f"Payment processed successfully: {txid} - {paid_amount} USDT for user {user_id}")
                    
                    success_msg = f"""✅ تم إيداع الرصيد بنجاح!

💰 المبلغ المودع: ${paid_amount:.2f}
💳 رصيدك الجديد: {db.get_user_balance(user_id)[1]:.2f} USD

🛒 يمكنك الآن شراء باقات CID من /packages"""
                    
                    return True, success_msg, tx_data
                else:
                    # Mark transaction as failed
                    db.update_transaction_status(transaction.id, "failed")
                    return False, "فشل في تحديث الرصيد", None
                
        except Exception as e:
            logger.error(f"Payment processing error: {e}")
            return False, f"خطأ في معالجة الدفع: {str(e)}", None
    
    async def get_recent_transactions(self, hours: int = 24) -> List[Dict]:
        """Get recent transactions to our wallet"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get TRC20 transfers to our wallet
                url = f"{self.tronscan_api}/token_trc20/transfers"
                params = {
                    "limit": 50,
                    "start": 0,
                    "sort": "-timestamp",
                    "count": True,
                    "filterTokenValue": 1,
                    "relatedAddress": self.wallet_address,
                    "contractAddress": self.usdt_contract
                }
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    transfers = data.get("token_transfers", [])
                    
                    # Filter recent transactions
                    cutoff_time = (datetime.now() - timedelta(hours=hours)).timestamp() * 1000
                    recent_transfers = []
                    
                    for transfer in transfers:
                        if transfer.get("block_ts", 0) > cutoff_time:
                            recent_transfers.append({
                                "txid": transfer.get("transaction_id", ""),
                                "amount": float(Decimal(transfer.get("quant", "0")) / Decimal(10**6)),
                                "from_address": transfer.get("from_address", ""),
                                "timestamp": transfer.get("block_ts", 0),
                                "confirmed": transfer.get("confirmed", False)
                            })
                    
                    return recent_transfers
                    
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {e}")
            return []
    
    def get_deposit_address(self) -> str:
        """Get the USDT TRC20 deposit address"""
        return self.wallet_address
    
    def format_payment_info(self, amount_usd: float) -> str:
        """Format payment information for user"""
        message = f"""🥇 الدفع عبر بايننس - الطريقة المفضلة
━━━━━━━━━━━━━━━━━━━━━

💰 المبلغ المطلوب: `${amount_usd:.2f} USD`

📍 عنوان محفظة بايننس:
`{config.binance.usdt_trc20_address}`

🌐 الشبكة: `TRC20 (Tron)`
💎 العملة: `USDT`

✅ مميزات الدفع عبر بايننس:
• تأكيد فوري للمعاملات
• رسوم منخفضة جداً
• أمان عالي ومضمون
• دعم فني 24/7

⚠️ تعليمات مهمة:
• استخدم شبكة TRC20 فقط
• أرسل المبلغ المطلوب بالضبط
• احفظ رقم المعاملة (TXID)
• التأكيد خلال 1-10 دقائق

💡 نصيحة: اضغط على النصوص الزرقاء أعلاه لنسخها فوراً"""
        return message

# Global payment service instance
payment_service = PaymentService()
