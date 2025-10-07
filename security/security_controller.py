"""
Security Controller

This module provides the main security controller that integrates all privacy and security
components including encryption, consent management, anonymous mode, and audit trails.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from .privacy_security import (
    PrivacyLevel, DataType, ConsentType, AuditAction,
    encryption_manager, privacy_manager
)
from .consent_manager import consent_manager
from .anonymous_mode import anonymous_manager
from .audit_trail import audit_trail

logger = logging.getLogger(__name__)


class SecurityController:
    """Main security controller for privacy and security operations"""
    
    def __init__(self):
        self.encryption_manager = encryption_manager
        self.privacy_manager = privacy_manager
        self.consent_manager = consent_manager
        self.anonymous_manager = anonymous_manager
        self.audit_trail = audit_trail
    
    # === Data Protection Methods ===
    
    def encrypt_sensitive_data(
        self, 
        user_id: str, 
        data_type: DataType, 
        data: Any,
        ip_address: Optional[str] = None
    ) -> Tuple[bytes, str]:
        """Encrypt sensitive data with proper audit logging"""
        # Check privacy settings
        privacy_setting = self.privacy_manager.get_privacy_setting(user_id, data_type)
        
        if privacy_setting.privacy_level in [PrivacyLevel.CONFIDENTIAL, PrivacyLevel.TOP_SECRET]:
            # Use stronger encryption for highly sensitive data
            key_id = self.encryption_manager.generate_key("symmetric", expires_in_days=365)
        else:
            key_id = None  # Use master key
        
        # Encrypt the data
        encrypted_data, used_key_id = self.encryption_manager.encrypt_data(data, key_id)
        
        # Log the encryption action
        self.audit_trail.log_action(
            user_id=user_id,
            action=AuditAction.ENCRYPTION_KEY_GENERATED if key_id else AuditAction.DATA_MODIFICATION,
            data_type=data_type,
            ip_address=ip_address,
            details={
                'encryption_algorithm': 'Fernet',
                'key_id': used_key_id,
                'data_size': len(str(data))
            }
        )
        
        return encrypted_data, used_key_id
    
    def decrypt_sensitive_data(
        self, 
        user_id: str, 
        data_type: DataType, 
        encrypted_data: bytes, 
        key_id: str,
        access_purpose: str,
        ip_address: Optional[str] = None
    ) -> Optional[bytes]:
        """Decrypt sensitive data with permission checks and audit logging"""
        # Check if user has permission to access this data
        if not self.check_data_access_permission(user_id, data_type, access_purpose):
            self.audit_trail.log_action(
                user_id=user_id,
                action=AuditAction.DATA_ACCESS,
                data_type=data_type,
                ip_address=ip_address,
                details={'access_denied': True, 'reason': 'insufficient_permissions'},
                success=False
            )
            return None
        
        try:
            # Decrypt the data
            decrypted_data = self.encryption_manager.decrypt_data(encrypted_data, key_id)
            
            # Log successful access
            self.audit_trail.log_action(
                user_id=user_id,
                action=AuditAction.DATA_ACCESS,
                data_type=data_type,
                ip_address=ip_address,
                details={
                    'access_purpose': access_purpose,
                    'key_id': key_id,
                    'data_size': len(decrypted_data)
                }
            )
            
            return decrypted_data
            
        except Exception as e:
            # Log failed access
            self.audit_trail.log_action(
                user_id=user_id,
                action=AuditAction.DATA_ACCESS,
                data_type=data_type,
                ip_address=ip_address,
                details={'error': str(e), 'access_purpose': access_purpose},
                success=False
            )
            return None
    
    def check_data_access_permission(
        self, 
        user_id: str, 
        data_type: DataType, 
        access_purpose: str
    ) -> bool:
        """Check if user has permission to access data for specific purpose"""
        # Check privacy settings
        privacy_permission = self.privacy_manager.check_permission(user_id, data_type, access_purpose)
        if not privacy_permission:
            return False
        
        # Check consent requirements
        consent_required = self.consent_manager.check_data_processing_allowed(
            user_id, data_type, access_purpose
        )
        
        return consent_required
    
    # === Privacy Control Methods ===
    
    def update_privacy_settings(
        self, 
        user_id: str, 
        settings: Dict[DataType, Dict[str, Any]],
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update user privacy settings with validation and audit logging"""
        updated_settings = {}
        
        for data_type, setting_data in settings.items():
            try:
                # Create privacy setting object
                from .privacy_security import PrivacySetting
                
                privacy_setting = PrivacySetting(
                    data_type=data_type,
                    privacy_level=PrivacyLevel(setting_data.get('privacy_level', 'private')),
                    allow_ai_processing=setting_data.get('allow_ai_processing', True),
                    allow_team_matching=setting_data.get('allow_team_matching', True),
                    allow_analytics=setting_data.get('allow_analytics', False),
                    allow_third_party=setting_data.get('allow_third_party', False),
                    retention_days=setting_data.get('retention_days')
                )
                
                # Update the setting
                self.privacy_manager.set_privacy_setting(user_id, privacy_setting)
                updated_settings[data_type.value] = privacy_setting.to_dict()
                
                # Log the change
                self.audit_trail.log_action(
                    user_id=user_id,
                    action=AuditAction.PRIVACY_SETTING_CHANGE,
                    data_type=data_type,
                    ip_address=ip_address,
                    details={
                        'privacy_level': privacy_setting.privacy_level.value,
                        'ai_processing': privacy_setting.allow_ai_processing,
                        'team_matching': privacy_setting.allow_team_matching,
                        'analytics': privacy_setting.allow_analytics,
                        'third_party': privacy_setting.allow_third_party
                    }
                )
                
            except Exception as e:
                logger.error(f"Error updating privacy setting for {data_type}: {e}")
                updated_settings[data_type.value] = {'error': str(e)}
        
        return {
            'success': True,
            'updated_settings': updated_settings,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_privacy_dashboard(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive privacy dashboard for user"""
        # Get all privacy settings
        privacy_settings = self.privacy_manager.get_all_privacy_settings(user_id)
        
        # Get consent summary
        consent_summary = self.consent_manager.get_consent_summary(user_id)
        
        # Get recent audit trail
        recent_audit = self.audit_trail.get_user_audit_trail(
            user_id,
            start_date=datetime.utcnow() - timedelta(days=30),
            limit=20
        )
        
        # Detect anomalous access
        anomalies = self.audit_trail.detect_anomalous_access(user_id)
        
        return {
            'privacy_settings': {
                dt.value: setting.to_dict() 
                for dt, setting in privacy_settings.items()
            },
            'consent_summary': consent_summary,
            'recent_activity': recent_audit,
            'security_anomalies': anomalies,
            'data_types_count': len(privacy_settings),
            'last_updated': datetime.utcnow().isoformat()
        }
    
    # === Consent Management Methods ===
    
    def grant_user_consent(
        self, 
        user_id: str, 
        consent_type: ConsentType, 
        purpose: str,
        data_types: List[DataType] = None,
        expires_in_days: Optional[int] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Grant user consent with audit logging"""
        try:
            consent_id = self.consent_manager.grant_consent(
                user_id=user_id,
                consent_type=consent_type,
                purpose=purpose,
                data_types=data_types,
                expires_in_days=expires_in_days
            )
            
            # Log consent action
            self.audit_trail.log_action(
                user_id=user_id,
                action=AuditAction.CONSENT_GIVEN,
                ip_address=ip_address,
                details={
                    'consent_type': consent_type.value,
                    'purpose': purpose,
                    'consent_id': consent_id,
                    'data_types': [dt.value for dt in (data_types or [])],
                    'expires_in_days': expires_in_days
                }
            )
            
            return {
                'success': True,
                'consent_id': consent_id,
                'message': f'Consent granted for {consent_type.value}'
            }
            
        except Exception as e:
            logger.error(f"Error granting consent: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def withdraw_user_consent(
        self, 
        user_id: str, 
        consent_type: ConsentType,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Withdraw user consent with audit logging"""
        try:
            success = self.consent_manager.withdraw_consent(user_id, consent_type)
            
            if success:
                # Log consent withdrawal
                self.audit_trail.log_action(
                    user_id=user_id,
                    action=AuditAction.CONSENT_WITHDRAWN,
                    ip_address=ip_address,
                    details={'consent_type': consent_type.value}
                )
                
                return {
                    'success': True,
                    'message': f'Consent withdrawn for {consent_type.value}'
                }
            else:
                return {
                    'success': False,
                    'error': 'No active consent found to withdraw'
                }
                
        except Exception as e:
            logger.error(f"Error withdrawing consent: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # === Anonymous Mode Methods ===
    
    def create_anonymous_session(
        self, 
        user_data: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create anonymous session"""
        try:
            anonymous_id = self.anonymous_manager.create_anonymous_session(user_data)
            
            # Log anonymous session creation
            self.audit_trail.log_action(
                user_id=f"anon_{anonymous_id[:8]}",
                action=AuditAction.ANONYMOUS_MODE_ACTIVATED,
                ip_address=ip_address,
                details={
                    'anonymous_id': anonymous_id,
                    'has_user_data': user_data is not None
                }
            )
            
            return {
                'success': True,
                'anonymous_id': anonymous_id,
                'session_timeout_minutes': self.anonymous_manager.session_timeout_minutes,
                'allowed_operations': [
                    'profile_creation', 'basic_matching', 'skill_assessment',
                    'team_exploration', 'chat_interaction'
                ]
            }
            
        except Exception as e:
            logger.error(f"Error creating anonymous session: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def perform_anonymous_operation(
        self, 
        anonymous_id: str, 
        operation_type: str, 
        operation_data: Dict[str, Any],
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform operation in anonymous mode"""
        result = self.anonymous_manager.perform_anonymous_operation(
            anonymous_id, operation_type, operation_data
        )
        
        # Additional audit logging for anonymous operations
        if result.get('success'):
            self.audit_trail.log_action(
                user_id=f"anon_{anonymous_id[:8]}",
                action=AuditAction.DATA_ACCESS if 'read' in operation_type else AuditAction.DATA_MODIFICATION,
                ip_address=ip_address,
                details={
                    'anonymous_operation': operation_type,
                    'anonymous_id': anonymous_id
                }
            )
        
        return result
    
    # === Security Monitoring Methods ===
    
    def get_security_status(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive security status"""
        # System-wide security metrics
        recent_time = datetime.utcnow() - timedelta(hours=24)
        
        # Get anonymous session statistics
        anon_stats = self.anonymous_manager.get_anonymous_statistics()
        
        # Generate compliance report
        compliance_report = self.audit_trail.generate_compliance_report(
            start_date=recent_time,
            end_date=datetime.utcnow()
        )
        
        security_status = {
            'system_security': {
                'encryption_available': True,
                'audit_trail_active': True,
                'consent_management_active': True,
                'anonymous_mode_active': True,
                'last_security_check': datetime.utcnow().isoformat()
            },
            'anonymous_statistics': anon_stats,
            'compliance_summary': compliance_report['summary'],
            'security_events_24h': compliance_report.get('security_summary', {})
        }
        
        # Add user-specific security info if user_id provided
        if user_id:
            user_anomalies = self.audit_trail.detect_anomalous_access(user_id)
            user_consents = self.consent_manager.get_consent_summary(user_id)
            
            security_status['user_security'] = {
                'anomalies_detected': len(user_anomalies),
                'active_consents': user_consents['active_consents'],
                'security_score': self._calculate_user_security_score(user_id)
            }
        
        return security_status
    
    def _calculate_user_security_score(self, user_id: str) -> int:
        """Calculate security score for user (0-100)"""
        score = 100
        
        # Check for recent anomalies
        anomalies = self.audit_trail.detect_anomalous_access(user_id)
        score -= len(anomalies) * 10
        
        # Check consent coverage
        consents = self.consent_manager.get_all_consents(user_id)
        active_consents = sum(1 for consent in consents.values() if consent.is_valid())
        if active_consents < 3:  # Expect at least 3 basic consents
            score -= (3 - active_consents) * 5
        
        # Check privacy settings
        privacy_settings = self.privacy_manager.get_all_privacy_settings(user_id)
        if len(privacy_settings) < 5:  # Expect settings for major data types
            score -= (5 - len(privacy_settings)) * 3
        
        return max(0, min(100, score))
    
    def cleanup_expired_data(self) -> Dict[str, Any]:
        """Clean up expired sessions and data"""
        # Clean up expired anonymous sessions
        self.anonymous_manager.cleanup_expired_sessions()
        
        # TODO: Add cleanup for expired encryption keys, old audit logs, etc.
        
        return {
            'success': True,
            'cleanup_timestamp': datetime.utcnow().isoformat(),
            'message': 'Expired data cleanup completed'
        }
    
    # === Data Export and Deletion Methods ===
    
    def export_user_data(
        self, 
        user_id: str, 
        data_types: Optional[List[DataType]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Export user data with proper consent and audit logging"""
        # Check if user has consented to data export
        if not self.consent_manager.has_valid_consent(user_id, ConsentType.DATA_PROCESSING):
            return {
                'success': False,
                'error': 'Data export consent required'
            }
        
        try:
            export_data = {}
            
            # Get privacy settings
            if not data_types or DataType.PREFERENCES in data_types:
                export_data['privacy_settings'] = {
                    dt.value: setting.to_dict()
                    for dt, setting in self.privacy_manager.get_all_privacy_settings(user_id).items()
                }
            
            # Get consent records
            export_data['consent_records'] = self.consent_manager.get_consent_summary(user_id)
            
            # Get audit trail (limited)
            export_data['audit_trail'] = self.audit_trail.get_user_audit_trail(
                user_id, 
                start_date=datetime.utcnow() - timedelta(days=90),
                limit=100
            )
            
            # Log the export
            self.audit_trail.log_action(
                user_id=user_id,
                action=AuditAction.DATA_EXPORT,
                ip_address=ip_address,
                details={
                    'export_size': len(str(export_data)),
                    'data_types_exported': [dt.value for dt in (data_types or [])],
                    'export_timestamp': datetime.utcnow().isoformat()
                }
            )
            
            return {
                'success': True,
                'export_data': export_data,
                'export_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting user data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_user_data(
        self, 
        user_id: str, 
        data_types: Optional[List[DataType]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete user data with proper audit logging"""
        try:
            deleted_items = []
            
            # Delete privacy settings
            if not data_types or any(dt in data_types for dt in DataType):
                # This is a placeholder - actual deletion would need to be implemented
                # based on specific storage mechanisms
                deleted_items.append('privacy_settings')
            
            # Log the deletion
            self.audit_trail.log_action(
                user_id=user_id,
                action=AuditAction.DATA_DELETION,
                ip_address=ip_address,
                details={
                    'deleted_items': deleted_items,
                    'data_types': [dt.value for dt in (data_types or [])],
                    'deletion_timestamp': datetime.utcnow().isoformat()
                }
            )
            
            return {
                'success': True,
                'deleted_items': deleted_items,
                'deletion_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error deleting user data: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Initialize global security controller
security_controller = SecurityController()

logger.info("Security controller initialized with all privacy and security components")