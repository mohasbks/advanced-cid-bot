"""
Database connection and operations for Advanced CID Telegram Bot
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from database.models import Base, User, Package, Transaction, Voucher, VoucherUse, CIDRequest, AdminLog, SystemSettings
from config import config

logger = logging.getLogger(__name__)

class Database:
    """Database connection and operations manager"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.User = User  # Add User class reference
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database connection"""
        try:
            # Check if DATABASE_URL is provided (Railway style)
            if config.database.url:
                database_url = config.database.url
            elif config.database.type == "postgresql":
                database_url = f"postgresql+psycopg2://{config.database.user}:{config.database.password}@{config.database.host}:{config.database.port}/{config.database.name}"
            elif config.database.type == "sqlite":
                database_url = f"sqlite:///{config.database.name}"
            elif config.database.type == "mysql":
                database_url = f"mysql+pymysql://{config.database.user}:{config.database.password}@{config.database.host}:{config.database.port}/{config.database.name}"
            else:
                raise ValueError(f"Unsupported database type: {config.database.type}")
            
            # PostgreSQL specific connection arguments
            connect_args = {}
            if config.database.type == "sqlite":
                connect_args = {"check_same_thread": False}
            
            self.engine = create_engine(
                database_url,
                echo=False,  # SQL logging disabled - BIGINT issue resolved
                pool_pre_ping=True,
                connect_args=connect_args
            )
            
            # Drop and recreate tables with updated schema (BIGINT support for Telegram user IDs)
            # Force Railway redeploy - Updated 2025-09-21 11:22 - Fixed users.id to BigInteger to match foreign keys
            Base.metadata.drop_all(bind=self.engine)
            Base.metadata.create_all(bind=self.engine)
            
            # Create session factory
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # Initialize default data
            self._initialize_default_data()
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def _initialize_default_data(self):
        """Initialize default packages and settings"""
        try:
            with self.get_session() as session:
                # Check if packages already exist
                if session.query(Package).count() == 0:
                    # Add default packages
                    for pkg in config.packages:
                        db_package = Package(
                            id=pkg.id,
                            name=pkg.name,
                            cid_amount=pkg.cid_amount,
                            price_sar=pkg.price_sar,
                            price_usd=pkg.price_usd
                        )
                        session.add(db_package)
                    
                    logger.info("Default packages added to database")
                
                # Add default system settings
                default_settings = [
                    ("maintenance_mode", "false", "Enable/disable maintenance mode"),
                    ("min_usdt_deposit", "5.0", "Minimum USDT deposit amount"),
                    ("cid_cost_usd", "0.2", "Cost per CID in USD"),
                    ("exchange_rate_usd_sar", "3.75", "USD to SAR exchange rate"),
                ]
                
                for key, value, description in default_settings:
                    if not session.query(SystemSettings).filter_by(key=key).first():
                        setting = SystemSettings(key=key, value=value, description=description)
                        session.add(setting)
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to initialize default data: {e}")
    
    # User operations
    def create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> Dict:
        """Create user - alias to get_or_create_user"""
        return self.get_or_create_user(user_id, username, first_name, last_name)
    
    def add_user_balance(self, user_id: int, cid_amount: int = 0, usd_amount: float = 0.0) -> bool:
        """Add balance to user"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if user:
                    user.balance_cid += cid_amount
                    user.balance_usd += usd_amount
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error adding user balance: {e}")
            return False
    
    def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
        """Get existing user or create new one"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                
                if not user:
                    user = User(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        is_admin=config.is_admin(user_id)
                    )
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                    logger.info(f"New user created: {user_id}")
                else:
                    # Update user info
                    user.username = username
                    user.first_name = first_name
                    session.commit()
                    
                return user
        except Exception as e:
            logger.error(f"Error creating/updating user {user_id}: {e}")
            return None

    def add_user_balance(self, user_id: int, cid_amount: int, usd_amount: float) -> bool:
        """Add balance to user account (admin operation)"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if not user:
                    return False
                
                user.balance_cid += cid_amount
                user.balance_usd += usd_amount
                user.last_activity = datetime.utcnow()
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding balance for user {user_id}: {e}")
            return False

    def subtract_user_balance(self, user_id: int, cid_amount: int, usd_amount: float) -> bool:
        """Subtract balance from user account (admin operation)"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if not user:
                    return False
                
                # Check if user has sufficient balance
                if user.balance_cid < cid_amount or user.balance_usd < usd_amount:
                    return False
                
                user.balance_cid -= cid_amount
                user.balance_usd -= usd_amount
                user.last_activity = datetime.utcnow()
                
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error subtracting balance for user {user_id}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by user_id"""
        with self.get_session() as session:
            return session.query(User).filter_by(user_id=user_id).first()
    
    def get_user_balance(self, user_id: int) -> tuple:
        """Get user balance (CID, USD)"""
        with self.get_session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                return user.balance_cid, user.balance_usd
            return 0, 0.0
    
    # Transaction operations
    def create_transaction(self, user_id: int, transaction_type: str, amount_usd: float = 0.0, 
                          amount_cid: int = 0, **kwargs) -> Optional[Transaction]:
        """Create new transaction"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return None
                
                transaction = Transaction(
                    user_id=user.id,
                    type=transaction_type,
                    amount_usd=amount_usd,
                    amount_cid=amount_cid,
                    **kwargs
                )
                session.add(transaction)
                session.commit()
                session.refresh(transaction)
                transaction_id = transaction.id
                
                logger.info(f"Transaction created: {transaction_id} for user {user_id}")
                return transaction_id
        except Exception as e:
            logger.error(f"Failed to create transaction: {e}")
            return None
    
    def update_transaction_status(self, transaction_id: int, status: str, **kwargs) -> bool:
        """Update transaction status"""
        try:
            with self.get_session() as session:
                transaction = session.query(Transaction).filter_by(id=transaction_id).first()
                if transaction:
                    transaction.status = status
                    if status == 'completed':
                        transaction.completed_at = datetime.utcnow()
                    
                    # Update additional fields
                    for key, value in kwargs.items():
                        if hasattr(transaction, key):
                            setattr(transaction, key, value)
                    
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to update transaction status: {e}")
            return False
    
    def is_txid_used(self, txid: str) -> bool:
        """Check if TXID is already used"""
        with self.get_session() as session:
            return session.query(Transaction).filter_by(txid=txid, status='completed').first() is not None
    
    def get_user_transactions(self, user_id: int, limit: int = 10):
        """Get user transactions"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return []
                
                transactions = session.query(Transaction).filter_by(
                    user_id=user.id
                ).order_by(
                    Transaction.created_at.desc()
                ).limit(limit).all()
                
                # Convert to dictionary objects to avoid session binding issues
                result = []
                for tx in transactions:
                    result.append({
                        'id': tx.id,
                        'amount_cid': tx.amount_cid or 0,
                        'amount_usd': tx.amount_usd or 0.0,
                        'created_at': tx.created_at,
                        'completed_at': tx.completed_at,
                        'type': tx.type,
                        'status': tx.status,
                        'description': tx.description
                    })
                
                return result
        except Exception as e:
            logger.error(f"Failed to get user transactions: {e}")
            return []
    
    # Voucher operations
    def create_voucher(self, code: str, cid_amount: int, usd_amount: float, admin_id: int, expires_days: int = None) -> Optional[Voucher]:
        """Create new voucher"""
        try:
            with self.get_session() as session:
                expires_at = None
                if expires_days:
                    expires_at = datetime.utcnow() + timedelta(days=expires_days)
                
                voucher = Voucher(
                    code=code,
                    cid_amount=cid_amount,
                    usd_amount=usd_amount,
                    created_by_admin=admin_id,
                    expires_at=expires_at
                )
                session.add(voucher)
                session.commit()
                session.refresh(voucher)
                
                # Create a detached copy with all the data we need
                voucher_copy = Voucher(
                    code=voucher.code,
                    cid_amount=voucher.cid_amount,
                    usd_amount=voucher.usd_amount,
                    created_by_admin=voucher.created_by_admin,
                    expires_at=voucher.expires_at,
                    created_at=voucher.created_at,
                    is_used=voucher.is_used
                )
                voucher_copy.id = voucher.id
                
                logger.info(f"Voucher created: {code}")
                return voucher_copy
        except Exception as e:
            logger.error(f"Failed to create voucher: {e}")
            return None
    
    def redeem_voucher(self, code: str, user_id: int) -> tuple:
        """Redeem voucher code. Returns (success: bool, message: str, voucher: Voucher)"""
        try:
            with self.get_session() as session:
                voucher = session.query(Voucher).filter_by(code=code).first()
                
                if not voucher:
                    return False, "كود الشحن غير صالح", None
                
                if voucher.is_used:
                    return False, "تم استخدام هذا الكود من قبل", None
                
                if voucher.expires_at and voucher.expires_at < datetime.utcnow():
                    return False, "انتهت صلاحية هذا الكود", None
                
                # Mark voucher as used
                voucher.is_used = True
                
                # Create voucher use record
                voucher_use = VoucherUse(voucher_id=voucher.id, user_id=user_id)
                session.add(voucher_use)
                
                # Update user balance
                user = session.query(User).filter_by(user_id=user_id).first()
                if user:
                    user.balance_cid += voucher.cid_amount
                    user.balance_usd += voucher.usd_amount
                
                session.commit()
                session.refresh(voucher)  # Refresh to ensure object is up-to-date
                
                # Create a detached copy of voucher data to avoid session binding issues
                voucher_data = {
                    'id': voucher.id,
                    'code': voucher.code,
                    'cid_amount': voucher.cid_amount,
                    'usd_amount': voucher.usd_amount,
                    'created_by_admin': voucher.created_by_admin,
                    'is_used': voucher.is_used,
                    'created_at': voucher.created_at,
                    'expires_at': voucher.expires_at
                }
                
                logger.info(f"Voucher {code} redeemed by user {user_id}")
                
                return True, "تم شحن الرصيد بنجاح", voucher_data
                
        except Exception as e:
            logger.error(f"Failed to redeem voucher: {e}")
            return False, "حدث خطأ أثناء استخدام الكود", None
    
    # CID Request operations
    def create_cid_request(self, user_id: int, installation_id: str) -> Optional[int]:
        """Create new CID request and return the request ID"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return None
                
                cid_request = CIDRequest(
                    user_id=user.id,
                    installation_id=installation_id
                )
                session.add(cid_request)
                session.commit()
                session.refresh(cid_request)
                
                # Get the ID before session closes
                request_id = cid_request.id
                
                logger.info(f"CID request created: {request_id} for user {user_id}")
                return request_id
        except Exception as e:
            logger.error(f"Failed to create CID request: {e}")
            return None
    
    def update_cid_request(self, request_id: int, status: str, confirmation_id: str = None, error_message: str = None) -> bool:
        """Update CID request"""
        try:
            with self.get_session() as session:
                cid_request = session.query(CIDRequest).filter_by(id=request_id).first()
                if cid_request:
                    cid_request.status = status
                    if confirmation_id:
                        cid_request.confirmation_id = confirmation_id
                    if error_message:
                        cid_request.error_message = error_message
                    if status in ['completed', 'failed', 'invalid_iid']:
                        cid_request.completed_at = datetime.utcnow()
                    
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to update CID request: {e}")
            return False
    
    # Admin operations
    def log_admin_action(self, admin_id: int, action: str, target_user_id: int = None, details: str = None):
        """Log admin action"""
        try:
            with self.get_session() as session:
                log = AdminLog(
                    admin_user_id=admin_id,
                    action=action,
                    target_user_id=target_user_id,
                    details=details
                )
                session.add(log)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")
    
    def get_system_setting(self, key: str, default: str = None) -> str:
        """Get system setting value"""
        with self.get_session() as session:
            setting = session.query(SystemSettings).filter_by(key=key).first()
            return setting.value if setting else default
    
    def set_system_setting(self, key: str, value: str, description: str = None):
        """Set system setting value"""
        with self.get_session() as session:
            setting = session.query(SystemSettings).filter_by(key=key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
                if description:
                    setting.description = description
            else:
                setting = SystemSettings(key=key, value=value, description=description)
                session.add(setting)
            session.commit()
    
    def set_user_admin(self, user_id: int, is_admin: bool = True) -> bool:
        """Set user admin status"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                if user:
                    user.is_admin = is_admin
                    session.commit()
                    logger.info(f"User {user_id} admin status set to {is_admin}")
                    return True
                else:
                    logger.error(f"User {user_id} not found")
                    return False
        except Exception as e:
            logger.error(f"Failed to set admin status for user {user_id}: {e}")
            return False

    def get_admin_users(self) -> List[Dict]:
        """Get all admin users"""
        try:
            with self.get_session() as session:
                admin_users = session.query(User).filter_by(is_admin=True).all()
                return [
                    {
                        'telegram_id': user.user_id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'is_admin': user.is_admin
                    }
                    for user in admin_users
                ]
        except Exception as e:
            logger.error(f"Failed to get admin users: {e}")
            return []

# Global database instance
db = Database()
