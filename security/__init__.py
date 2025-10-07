"""
Security Module for Find Your Team Platform

This module provides comprehensive privacy and security controls including:
- Client-side encryption for sensitive data
- Granular privacy settings with real-time updates
- Anonymous mode with secure key management
- Data sharing consent mechanisms
- Audit trails for all data access and modifications
- Security testing framework

Task 12 Implementation - Privacy and Security Controls
"""

from .privacy_security import (
    PrivacyLevel, DataType, ConsentType, AuditAction,
    EncryptionKey, PrivacySetting, ConsentRecord, AuditLog, AnonymousProfile,
    EncryptionManager, PrivacyManager,
    encryption_manager, privacy_manager
)

from .consent_manager import ConsentManager, consent_manager
from .anonymous_mode import AnonymousManager, AnonymousSession, anonymous_manager
from .audit_trail import AuditTrail, audit_trail
from .security_controller import SecurityController, security_controller

# Export main interfaces
__all__ = [
    # Enums
    'PrivacyLevel', 'DataType', 'ConsentType', 'AuditAction',
    
    # Data Classes
    'EncryptionKey', 'PrivacySetting', 'ConsentRecord', 'AuditLog', 'AnonymousProfile',
    
    # Managers
    'EncryptionManager', 'PrivacyManager', 'ConsentManager', 
    'AnonymousManager', 'AuditTrail', 'SecurityController',
    
    # Global Instances
    'encryption_manager', 'privacy_manager', 'consent_manager',
    'anonymous_manager', 'audit_trail', 'security_controller'
]

# Version info
__version__ = '1.0.0'
__author__ = 'Find Your Team Security Team'
__description__ = 'Comprehensive privacy and security controls for Find Your Team platform'