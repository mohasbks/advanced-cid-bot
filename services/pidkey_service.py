"""
PIDKEY API service for Advanced CID Telegram Bot
Handles CID generation from Installation IDs
"""

import aiohttp
import logging
from typing import Optional, Tuple, Dict
from datetime import datetime
import asyncio

from config import config
from database.database import db

logger = logging.getLogger(__name__)

class PIDKEYService:
    """Service for interacting with PIDKEY API"""
    
    def __init__(self):
        # CIDMS API configuration
        self.api_url = "https://pidkey.com/ajax/cidms_api"
        self.api_key = "KaT8lsFLRhYKng6uaReScSptI"
        self.cost_per_cid = 1
        
        # Request timeout settings (PIDKEY supports >100 seconds)
        self.timeout = aiohttp.ClientTimeout(total=120)
    
    def validate_installation_id(self, installation_id: str) -> Tuple[bool, str]:
        """
        Validate Installation ID format
        Returns (is_valid, message)
        """
        if not installation_id:
            return False, "Installation ID فارغ"
        
        # Remove any formatting (spaces, dashes)
        clean_id = ''.join(c for c in installation_id if c.isdigit())
        
        # Check length (should be 63 digits for Office)
        if len(clean_id) != 63:
            return False, f"Installation ID يجب أن يحتوي على 63 رقم بالضبط (الحالي: {len(clean_id)})"
        
        # Check if it's all digits
        if not clean_id.isdigit():
            return False, "Installation ID يجب أن يحتوي على أرقام فقط"
        
        # Basic pattern validation (Office IDs usually don't start with 0)
        if clean_id.startswith('000'):
            return False, "Installation ID غير صالح - يبدأ بأصفار متعددة"
        
        return True, clean_id
    
    async def get_confirmation_id(self, installation_id: str) -> Tuple[bool, str, Optional[str]]:
        """
        Get Confirmation ID from CIDMS API
        Returns (success, message, confirmation_id)
        """
        try:
            # Validate Installation ID first
            is_valid, result = self.validate_installation_id(installation_id)
            if not is_valid:
                return False, result, None
            
            clean_installation_id = result
            
            # Build CIDMS API URL
            api_url = f"{self.api_url}?iids={clean_installation_id}&justforcheck=0&apikey={self.api_key}"
            
            headers = {
                'User-Agent': 'Advanced-CID-Bot/1.0'
            }
            
            logger.info(f"Requesting CID for IID: {clean_installation_id[:10]}...")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(api_url, headers=headers) as response:
                    
                    response_text = await response.text()
                    logger.info(f"CIDMS API Response: {response_text}")
                    
                    if response.status == 200:
                        # Try to parse as JSON using manual parsing (server returns wrong mimetype)
                        try:
                            import json
                            response_text = response_text.strip()
                            
                            # Try to parse as JSON manually
                            if response_text.startswith('{') and response_text.endswith('}'):
                                data = json.loads(response_text)
                                logger.info(f"CIDMS API JSON Response: {data}")
                                
                                # Check for successful response
                                if data.get('result') == 'Successfully' and data.get('confirmationid'):
                                    confirmation_id = data['confirmationid']
                                    logger.info(f"CID generated successfully for IID: {clean_installation_id[:10]}...")
                                    return True, "تم إنشاء Confirmation ID بنجاح", confirmation_id
                                
                                # Check for errors in various field formats (API uses inconsistent naming)
                                error_executing = data.get('errorexecuting') or data.get('error_executing')
                                had_occurred = data.get('hadoccurred', 0) or data.get('had_occurred', 0)
                                
                                if error_executing or had_occurred != 0:
                                    error_msg = error_executing or 'Unknown error occurred'
                                    logger.error(f"CIDMS API error: {error_msg}")
                                    return False, f"خطأ من API: {error_msg}", None
                                
                                else:
                                    logger.error(f"CIDMS API unexpected response structure: {data}")
                                    return False, "استجابة غير متوقعة من API", None
                            
                            else:
                                # Not JSON format, treat as plain text
                                # Check if response is empty or too short
                                if len(response_text) < 10:
                                    logger.error(f"CIDMS API returned short response: {response_text}")
                                    return False, "API لم يرجع Confirmation ID صالح", None
                                
                                # Check for obvious error indicators
                                if "invalid" in response_text.lower() or "failed" in response_text.lower():
                                    logger.error(f"CIDMS API error: {response_text}")
                                    return False, f"خطأ من API: {response_text}", None
                                
                                # Assume the response is the Confirmation ID if it's long enough
                                confirmation_id = response_text
                                logger.info(f"CID generated successfully for IID: {clean_installation_id[:10]}...")
                                return True, "تم إنشاء Confirmation ID بنجاح", confirmation_id
                                
                        except json.JSONDecodeError as json_error:
                            # Not valid JSON, treat as plain text
                            logger.info(f"Response is not valid JSON, treating as plain text: {json_error}")
                            response_text = response_text.strip()
                            
                            # Check for obvious error indicators
                            if "invalid" in response_text.lower() or "failed" in response_text.lower():
                                logger.error(f"CIDMS API error: {response_text}")
                                return False, "BLOCKED_CODE", None
                            elif "blocked" in response_text.lower() or "banned" in response_text.lower():
                                return False, "BLOCKED_CODE", None
                                
                            # Check if response is empty or too short
                            if len(response_text) < 10:
                                logger.error(f"CIDMS API returned short response: {response_text}")
                                return False, "BLOCKED_CODE", None
                            
                            # Assume the response is the Confirmation ID
                            confirmation_id = response_text
                            logger.info(f"CID generated successfully for IID: {clean_installation_id[:10]}...")
                            return True, "تم إنشاء Confirmation ID بنجاح", confirmation_id
                    
                    elif response.status == 400:
                        return False, "BLOCKED_CODE", None
                    
                    elif response.status == 403:
                        return False, "BLOCKED_CODE", None
                    
                    elif response.status == 401:
                        return False, "خطأ في المصادقة مع API", None
                    
                    elif response.status == 429:
                        return False, "تم تجاوز حد الطلبات، حاول مرة أخرى لاحقاً", None
                    
                    elif response.status == 503:
                        return False, "خدمة API غير متاحة حالياً، حاول مرة أخرى", None
                    
                    else:
                        logger.error(f"CIDMS API error {response.status}: {response_text}")
                        return False, f"خطأ في API (كود: {response.status})", None
        
        except asyncio.TimeoutError:
            logger.error("PIDKEY API timeout")
            return False, "انتهت مهلة الاتصال مع API، حاول مرة أخرى", None
        
        except aiohttp.ClientError as e:
            logger.error(f"PIDKEY API client error: {e}")
            return False, "خطأ في الاتصال مع خدمة CID", None
        
        except Exception as e:
            logger.error(f"PIDKEY API unexpected error: {e}")
            return False, f"خطأ غير متوقع: {str(e)}", None
    
    async def process_cid_request(self, user_id: int, installation_id: str) -> Tuple[bool, str, Optional[str]]:
        """
        Process complete CID request (balance check + API call + database update)
        Returns (success, message, confirmation_id)
        """
        try:
            # Check user balance
            cid_balance, usd_balance = db.get_user_balance(user_id)
            
            if cid_balance < 1:
                return False, "رصيد CID غير كافي. تحتاج إلى شراء باقة أولاً", None
            
            # Create CID request record
            cid_request_id = db.create_cid_request(user_id, installation_id)
            if not cid_request_id:
                return False, "فشل في إنشاء طلب CID", None
            
            # Get Confirmation ID from API
            success, message, confirmation_id = await self.get_confirmation_id(installation_id)
            
            if success and confirmation_id:
                # Deduct CID from user balance
                balance_updated = db.subtract_user_balance(user_id, cid_amount=1, usd_amount=0.0)
                
                if balance_updated:
                    # Update CID request as completed
                    db.update_cid_request(
                        cid_request_id,
                        status="completed",
                        confirmation_id=confirmation_id
                    )
                    
                    # Create transaction record
                    db.create_transaction(
                        user_id=user_id,
                        transaction_type="cid_purchase",
                        amount_cid=-1,
                        status="completed",
                        installation_id=installation_id,
                        confirmation_id=confirmation_id,
                        description=f"CID service - Generated CID for Installation ID"
                    )
                    
                    logger.info(f"CID request completed successfully for user {user_id}")
                    
                    success_message = f"""
✅ تم إنشاء Confirmation ID بنجاح!

🔑 Confirmation ID:
`{confirmation_id}`

💎 رصيد CID المتبقي: {cid_balance - 1}

📋 تعليمات التفعيل:
1. انسخ الكود أعلاه (اضغط عليه)
2. افتح Microsoft Office
3. اذهب إلى Account أو File > Account
4. اختر "Change Product Key"
5. الصق الكود واضغط Enter
6. اتبع التعليمات لإكمال التفعيل

🎯 ملاحظة: احفظ هذا الكود في مكان آمن
"""
                    
                    return True, success_message, confirmation_id
                else:
                    # Failed to update balance, mark request as failed
                    db.update_cid_request(
                        cid_request_id,
                        status="failed",
                        error_message="فشل في خصم رصيد CID"
                    )
                    return False, "فشل في خصم رصيد CID", None
            else:
                # API call failed, update request
                db.update_cid_request(
                    cid_request_id,
                    status="failed" if "غير صالح" in message else "invalid_iid",
                    error_message=message
                )
                return False, message, None
                
        except Exception as e:
            logger.error(f"CID request processing error: {e}")
            return False, f"خطأ في معالجة طلب CID: {str(e)}", None
    
    def format_installation_id(self, installation_id: str) -> str:
        """Format Installation ID for display"""
        clean_id = ''.join(c for c in installation_id if c.isdigit())
        
        if len(clean_id) != 63:
            return installation_id  # Return as-is if not valid length
        
        # Format as XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXX
        formatted = '-'.join([
            clean_id[i:i+5] for i in range(0, len(clean_id), 5)
        ])
        
        return formatted
    
    async def validate_api_connection(self) -> Tuple[bool, str]:
        """Test API connection and authentication"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'Advanced-CID-Bot/1.0'
            }
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.api_url}/status",
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        return True, f"API متصل بنجاح - الحالة: {data.get('status', 'نشط')}"
                    elif response.status == 401:
                        return False, "خطأ في المصادقة - تحقق من API Key"
                    else:
                        return False, f"خطأ في الاتصال - كود: {response.status}"
                        
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False, f"فشل الاتصال: {str(e)}"
    
    def get_usage_statistics(self, user_id: int) -> Dict:
        """Get user CID usage statistics"""
        try:
            with db.get_session() as session:
                user = session.query(db.User).filter_by(user_id=user_id).first()
                if not user:
                    return {"error": "المستخدم غير موجود"}
                
                # Get completed CID requests
                completed_requests = session.query(db.CIDRequest).filter(
                    db.CIDRequest.user_id == user.id,
                    db.CIDRequest.status == "completed"
                ).count()
                
                # Get failed requests
                failed_requests = session.query(db.CIDRequest).filter(
                    db.CIDRequest.user_id == user.id,
                    db.CIDRequest.status == "failed"
                ).count()
                
                # Get total CID purchased
                cid_purchases = session.query(db.Transaction).filter(
                    db.Transaction.user_id == user.id,
                    db.Transaction.type == "cid_purchase",
                    db.Transaction.status == "completed",
                    db.Transaction.amount_cid > 0
                ).all()
                
                total_purchased = sum(t.amount_cid for t in cid_purchases)
                
                return {
                    "completed_requests": completed_requests,
                    "failed_requests": failed_requests,
                    "total_purchased": total_purchased,
                    "current_balance": user.balance_cid,
                    "usage_rate": f"{(completed_requests / max(1, total_purchased)) * 100:.1f}%"
                }
                
        except Exception as e:
            logger.error(f"Failed to get usage statistics: {e}")
            return {"error": str(e)}

# Global PIDKEY service instance
pidkey_service = PIDKEYService()
