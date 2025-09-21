"""
Database models for Advanced CID Telegram Bot
SQLite/MySQL compatible models using SQLAlchemy
"""

from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """User model"""
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)  # Telegram user ID
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    balance_cid = Column(Integer, default=0)  # CID balance
    balance_usd = Column(Float, default=0.0)  # USD balance for purchases
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user")
    voucher_uses = relationship("VoucherUse", back_populates="user")
    cid_requests = relationship("CIDRequest", back_populates="user")
    package_reservations = relationship("PackageReservation", back_populates="user")

class Package(Base):
    """Package model"""
    __tablename__ = 'packages'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    cid_amount = Column(Integer, nullable=False)
    price_sar = Column(Float, nullable=False)
    price_usd = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    """Transaction model for payments and balance changes"""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    type = Column(String(50), nullable=False)  # 'usdt_deposit', 'voucher_redeem', 'cid_purchase', 'admin_adjust'
    amount_usd = Column(Float, default=0.0)
    amount_cid = Column(Integer, default=0)
    status = Column(String(50), default='pending')  # 'pending', 'completed', 'failed', 'cancelled'
    
    # For USDT transactions
    txid = Column(String(255), nullable=True, unique=True)  # Transaction ID
    from_address = Column(String(255), nullable=True)
    to_address = Column(String(255), nullable=True)
    
    # For voucher transactions
    voucher_code = Column(String(255), nullable=True)
    
    # For CID purchases
    installation_id = Column(Text, nullable=True)
    confirmation_id = Column(Text, nullable=True)
    
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="transactions")

class Voucher(Base):
    """Voucher codes model"""
    __tablename__ = 'vouchers'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(255), unique=True, nullable=False)
    cid_amount = Column(Integer, nullable=False)
    usd_amount = Column(Float, nullable=False)
    is_used = Column(Boolean, default=False)
    created_by_admin = Column(BigInteger, nullable=True)  # Admin user ID who created it
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    uses = relationship("VoucherUse", back_populates="voucher")

class VoucherUse(Base):
    """Voucher usage tracking"""
    __tablename__ = 'voucher_uses'
    
    id = Column(Integer, primary_key=True)
    voucher_id = Column(Integer, ForeignKey('vouchers.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    voucher = relationship("Voucher", back_populates="uses")
    user = relationship("User", back_populates="voucher_uses")

class CIDRequest(Base):
    """CID service requests"""
    __tablename__ = 'cid_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    installation_id = Column(Text, nullable=False)
    confirmation_id = Column(Text, nullable=True)
    status = Column(String(50), default='processing')  # 'processing', 'completed', 'failed', 'invalid_iid'
    cost_cid = Column(Integer, default=1)  # Cost in CID (usually 1)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="cid_requests")

class AdminLog(Base):
    """Admin actions log"""
    __tablename__ = 'admin_logs'
    
    id = Column(Integer, primary_key=True)
    admin_user_id = Column(BigInteger, nullable=False)
    action = Column(String(255), nullable=False)
    target_user_id = Column(BigInteger, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class PackageReservation(Base):
    """Package reservations for targeted payments"""
    __tablename__ = 'package_reservations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    package_id = Column(Integer, nullable=False)
    required_amount = Column(Float, nullable=False)  # Amount needed to pay
    status = Column(String(50), default='active')  # 'active', 'completed', 'expired', 'cancelled'
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # 30 minutes from creation
    payment_txid = Column(String(255), nullable=True)  # TXID when paid
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="package_reservations")

class SystemSettings(Base):
    """System settings and configuration"""
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
