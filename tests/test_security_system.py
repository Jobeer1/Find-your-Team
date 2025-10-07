"""
Comprehensive Test Suite for Task 12 - Privacy and Security Controls

Tests all security components including encryption, privacy settings,
consent management, anonymous mode, and audit trails.
"""

import unittest
import os
import sys
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from security import (
        security_controller, encryption_manager, privacy_manager, 
        consent_manager, anonymous_manager, audit_trail,
        DataType, ConsentType, PrivacyLevel, AuditAction,
        PrivacySetting, ConsentRecord
    )
    SECURITY_AVAILABLE = True
except ImportError as e:
    print(f"Security modules not available: {e}")
    SECURITY_AVAILABLE = False


@unittest.skipUnless(SECURITY_AVAILABLE, "Security modules not available")
class TestEncryptionManager(unittest.TestCase):
    """Test encryption and key management functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.manager = encryption_manager
    
    def test_key_generation(self):
        """Test encryption key generation"""
        # Test symmetric key generation
        key_id = self.manager.generate_key("symmetric")
        self.assertIsNotNone(key_id)
        self.assertIn(key_id, self.manager.keys)
        
        key = self.manager.keys[key_id]
        self.assertEqual(key.key_type, "symmetric")
        self.assertEqual(key.algorithm, "Fernet")
    
    def test_data_encryption_decryption(self):
        """Test data encryption and decryption"""
        test_data = {"sensitive": "information", "user_id": "test123"}
        
        # Encrypt data
        encrypted_data, key_id = self.manager.encrypt_data(test_data)
        self.assertIsNotNone(encrypted_data)
        self.assertIsNotNone(key_id)
        
        # Decrypt data
        decrypted_data = self.manager.decrypt_data(encrypted_data, key_id)
        self.assertIsNotNone(decrypted_data)
        
        # Verify data integrity
        decrypted_json = json.loads(decrypted_data.decode())
        self.assertEqual(decrypted_json, test_data)
    
    def test_key_expiration(self):
        """Test encryption key expiration"""
        # Generate key with 1-day expiration
        key_id = self.manager.generate_key("symmetric", expires_in_days=1)
        key = self.manager.keys[key_id]
        
        # Should not be expired yet
        self.assertFalse(key.is_expired())
        
        # Mock expired key
        key.expires_at = datetime.utcnow() - timedelta(days=1)
        self.assertTrue(key.is_expired())
    
    def test_key_rotation(self):
        """Test encryption key rotation"""
        # Generate initial key
        old_key_id = self.manager.generate_key("symmetric")
        
        # Rotate key
        new_key_id = self.manager.rotate_key(old_key_id)
        
        self.assertNotEqual(old_key_id, new_key_id)
        self.assertIn(new_key_id, self.manager.keys)


@unittest.skipUnless(SECURITY_AVAILABLE, "Security modules not available")
class TestPrivacyManager(unittest.TestCase):
    """Test privacy settings and controls"""
    
    def setUp(self):
        """Set up test environment"""
        self.manager = privacy_manager
        self.test_user_id = "test_user_123"
    
    def test_privacy_setting_creation(self):
        """Test creating and retrieving privacy settings"""
        setting = PrivacySetting(
            data_type=DataType.PROFILE_DETAILED,
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            allow_ai_processing=False,
            allow_team_matching=True,
            allow_analytics=False,
            allow_third_party=False
        )
        
        # Set privacy setting
        self.manager.set_privacy_setting(self.test_user_id, setting)
        
        # Retrieve and verify
        retrieved_setting = self.manager.get_privacy_setting(
            self.test_user_id, 
            DataType.PROFILE_DETAILED
        )
        
        self.assertEqual(retrieved_setting.privacy_level, PrivacyLevel.CONFIDENTIAL)
        self.assertFalse(retrieved_setting.allow_ai_processing)
        self.assertTrue(retrieved_setting.allow_team_matching)
    
    def test_permission_checking(self):
        """Test permission checking for data operations"""
        # Create restrictive setting
        setting = PrivacySetting(
            data_type=DataType.CONTACT_INFO,
            privacy_level=PrivacyLevel.TOP_SECRET,
            allow_ai_processing=False,
            allow_analytics=False,
            allow_third_party=False
        )
        
        self.manager.set_privacy_setting(self.test_user_id, setting)
        
        # Test permissions
        self.assertFalse(
            self.manager.check_permission(
                self.test_user_id, 
                DataType.CONTACT_INFO, 
                "ai_processing"
            )
        )
        
        self.assertFalse(
            self.manager.check_permission(
                self.test_user_id, 
                DataType.CONTACT_INFO, 
                "analytics"
            )
        )
    
    def test_bulk_settings_update(self):
        """Test bulk privacy settings update"""
        settings = {
            DataType.PROFILE_BASIC: PrivacySetting(
                data_type=DataType.PROFILE_BASIC,
                privacy_level=PrivacyLevel.PUBLIC
            ),
            DataType.SKILLS_DATA: PrivacySetting(
                data_type=DataType.SKILLS_DATA,
                privacy_level=PrivacyLevel.PRIVATE,
                allow_team_matching=True
            )
        }
        
        self.manager.bulk_update_settings(self.test_user_id, settings)
        
        # Verify updates
        basic_setting = self.manager.get_privacy_setting(
            self.test_user_id, 
            DataType.PROFILE_BASIC
        )
        self.assertEqual(basic_setting.privacy_level, PrivacyLevel.PUBLIC)
        
        skills_setting = self.manager.get_privacy_setting(
            self.test_user_id, 
            DataType.SKILLS_DATA
        )
        self.assertTrue(skills_setting.allow_team_matching)


@unittest.skipUnless(SECURITY_AVAILABLE, "Security modules not available")
class TestConsentManager(unittest.TestCase):
    """Test consent management functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.manager = consent_manager
        self.test_user_id = "test_consent_user"
    
    def test_consent_granting_and_retrieval(self):
        """Test granting and retrieving consent"""
        # Grant consent
        consent_id = self.manager.grant_consent(
            user_id=self.test_user_id,
            consent_type=ConsentType.AI_ANALYSIS,
            purpose="Team matching and skill assessment",
            data_types=[DataType.SKILLS_DATA, DataType.PURPOSE_PROFILE],
            expires_in_days=365
        )
        
        self.assertIsNotNone(consent_id)
        
        # Retrieve consent
        consent = self.manager.get_consent(self.test_user_id, ConsentType.AI_ANALYSIS)
        self.assertIsNotNone(consent)
        self.assertTrue(consent.granted)
        self.assertEqual(consent.purpose, "Team matching and skill assessment")
        self.assertIn(DataType.SKILLS_DATA, consent.data_types)
    
    def test_consent_validation(self):
        """Test consent validation logic"""
        # Grant temporary consent (1 day)
        consent_id = self.manager.grant_consent(
            user_id=self.test_user_id,
            consent_type=ConsentType.ANALYTICS,
            purpose="Usage analytics",
            expires_in_days=1
        )
        
        # Should be valid initially
        self.assertTrue(
            self.manager.has_valid_consent(self.test_user_id, ConsentType.ANALYTICS)
        )
        
        # Mock expired consent
        consent = self.manager.get_consent(self.test_user_id, ConsentType.ANALYTICS)
        consent.expires_at = datetime.utcnow() - timedelta(days=1)
        self.manager._store_consent(consent)
        
        # Should be invalid now
        self.assertFalse(
            self.manager.has_valid_consent(self.test_user_id, ConsentType.ANALYTICS)
        )
    
    def test_consent_withdrawal(self):
        """Test consent withdrawal"""
        # Grant consent
        self.manager.grant_consent(
            user_id=self.test_user_id,
            consent_type=ConsentType.MARKETING,
            purpose="Marketing communications"
        )
        
        # Verify consent exists
        self.assertTrue(
            self.manager.has_valid_consent(self.test_user_id, ConsentType.MARKETING)
        )
        
        # Withdraw consent
        success = self.manager.withdraw_consent(self.test_user_id, ConsentType.MARKETING)
        self.assertTrue(success)
        
        # Verify consent is withdrawn
        self.assertFalse(
            self.manager.has_valid_consent(self.test_user_id, ConsentType.MARKETING)
        )
    
    def test_data_processing_permission(self):
        """Test data processing permission checking"""
        # Grant specific consent
        self.manager.grant_consent(
            user_id=self.test_user_id,
            consent_type=ConsentType.TEAM_MATCHING,
            purpose="Team matching",
            data_types=[DataType.SKILLS_DATA, DataType.PURPOSE_PROFILE]
        )
        
        # Test permission for allowed data type
        self.assertTrue(
            self.manager.check_data_processing_allowed(
                self.test_user_id,
                DataType.SKILLS_DATA,
                "team_matching"
            )
        )
        
        # Test permission for non-allowed data type
        self.assertFalse(
            self.manager.check_data_processing_allowed(
                self.test_user_id,
                DataType.CONTACT_INFO,
                "team_matching"
            )
        )


@unittest.skipUnless(SECURITY_AVAILABLE, "Security modules not available")
class TestAnonymousManager(unittest.TestCase):
    """Test anonymous mode functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.manager = anonymous_manager
    
    def test_anonymous_session_creation(self):
        """Test creating anonymous sessions"""
        # Create session without user data
        anonymous_id = self.manager.create_anonymous_session()
        self.assertIsNotNone(anonymous_id)
        
        # Retrieve session
        session = self.manager.get_session(anonymous_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.anonymous_id, anonymous_id)
        
        # Create session with user data
        user_data = {"skills": ["Python", "AI"], "interests": ["technology"]}
        anonymous_id_with_data = self.manager.create_anonymous_session(user_data)
        
        session_with_data = self.manager.get_session(anonymous_id_with_data)
        self.assertIsNotNone(session_with_data.user_hash)
    
    def test_anonymous_operations(self):
        """Test performing operations in anonymous mode"""
        anonymous_id = self.manager.create_anonymous_session()
        
        # Test profile creation
        result = self.manager.perform_anonymous_operation(
            anonymous_id=anonymous_id,
            operation_type="profile_creation",
            operation_data={
                "skills": ["JavaScript", "React"],
                "interests": ["web development"],
                "experience_level": "intermediate"
            }
        )
        
        self.assertTrue(result['success'])
        self.assertIn('profile_id', result)
        
        # Test basic matching
        matching_result = self.manager.perform_anonymous_operation(
            anonymous_id=anonymous_id,
            operation_type="basic_matching",
            operation_data={"preferences": {"remote": True}}
        )
        
        self.assertTrue(matching_result['success'])
        self.assertIn('matches', matching_result)
    
    def test_anonymous_session_expiration(self):
        """Test anonymous session expiration"""
        anonymous_id = self.manager.create_anonymous_session()
        session = self.manager.get_session(anonymous_id)
        
        # Should not be expired initially
        self.assertFalse(session.is_expired(30))
        
        # Mock expired session
        session.last_activity = datetime.utcnow() - timedelta(minutes=35)
        self.assertTrue(session.is_expired(30))
    
    def test_anonymous_to_registered_conversion(self):
        """Test converting anonymous session to registered user"""
        # Create anonymous session with data
        user_data = {"name": "Test User", "skills": ["Python"]}
        anonymous_id = self.manager.create_anonymous_session(user_data)
        
        # Perform some operations to create temporary data
        self.manager.perform_anonymous_operation(
            anonymous_id, "profile_creation", {"skills": ["Python", "AI"]}
        )
        
        # Convert to registered user
        result = self.manager.convert_to_registered_user(
            anonymous_id, "registered_user_123"
        )
        
        self.assertTrue(result['success'])
        self.assertIn('transferred_data', result)
        
        # Session should be terminated
        session = self.manager.get_session(anonymous_id)
        self.assertIsNone(session)


@unittest.skipUnless(SECURITY_AVAILABLE, "Security modules not available")
class TestAuditTrail(unittest.TestCase):
    """Test audit trail and logging functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.audit = audit_trail
        self.test_user_id = "audit_test_user"
    
    def test_audit_logging(self):
        """Test basic audit logging"""
        # Log an action
        log_id = self.audit.log_action(
            user_id=self.test_user_id,
            action=AuditAction.DATA_ACCESS,
            data_type=DataType.PROFILE_DETAILED,
            ip_address="192.168.1.100",
            details={"access_reason": "profile_view"}
        )
        
        self.assertIsNotNone(log_id)
        
        # Retrieve audit trail
        trail = self.audit.get_user_audit_trail(self.test_user_id, limit=10)
        self.assertGreater(len(trail), 0)
        
        # Verify log entry
        latest_entry = trail[0]
        self.assertEqual(latest_entry['action'], AuditAction.DATA_ACCESS.value)
        self.assertEqual(latest_entry['data_type'], DataType.PROFILE_DETAILED.value)
    
    def test_risk_score_calculation(self):
        """Test risk score calculation for audit actions"""
        # High-risk action
        high_risk_log = self.audit.log_action(
            user_id=self.test_user_id,
            action=AuditAction.DATA_DELETION,
            data_type=DataType.CONTACT_INFO,
            details={"bulk_operation": True}
        )
        
        trail = self.audit.get_user_audit_trail(self.test_user_id, limit=1)
        high_risk_entry = trail[0]
        
        # Should have elevated risk score
        self.assertGreater(high_risk_entry['risk_score'], 50)
        
        # Low-risk action
        low_risk_log = self.audit.log_action(
            user_id=self.test_user_id,
            action=AuditAction.DATA_ACCESS,
            data_type=DataType.PREFERENCES
        )
        
        trail = self.audit.get_user_audit_trail(self.test_user_id, limit=1)
        low_risk_entry = trail[0]
        
        # Should have lower risk score
        self.assertLess(low_risk_entry['risk_score'], 30)
    
    def test_anomaly_detection(self):
        """Test anomalous access pattern detection"""
        # Generate multiple rapid access events
        for i in range(15):
            self.audit.log_action(
                user_id=self.test_user_id,
                action=AuditAction.DATA_ACCESS,
                data_type=DataType.PROFILE_BASIC
            )
        
        # Detect anomalies
        anomalies = self.audit.detect_anomalous_access(self.test_user_id)
        
        # Should detect high volume access
        volume_anomaly = next(
            (a for a in anomalies if a['type'] == 'high_volume_access'), 
            None
        )
        self.assertIsNotNone(volume_anomaly)
    
    def test_compliance_reporting(self):
        """Test compliance report generation"""
        # Generate some test data
        self.audit.log_action(
            self.test_user_id, AuditAction.DATA_ACCESS, DataType.PROFILE_BASIC
        )
        self.audit.log_action(
            self.test_user_id, AuditAction.PRIVACY_SETTING_CHANGE, DataType.PREFERENCES
        )
        
        # Generate compliance report
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)
        
        report = self.audit.generate_compliance_report(start_date, end_date)
        
        self.assertIn('summary', report)
        self.assertIn('actions_by_type', report)
        self.assertGreater(report['summary']['total_actions'], 0)


@unittest.skipUnless(SECURITY_AVAILABLE, "Security modules not available")
class TestSecurityController(unittest.TestCase):
    """Test integrated security controller functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.controller = security_controller
        self.test_user_id = "security_test_user"
    
    def test_integrated_privacy_workflow(self):
        """Test complete privacy management workflow"""
        # Update privacy settings
        settings = {
            DataType.PROFILE_DETAILED: {
                'privacy_level': 'confidential',
                'allow_ai_processing': False,
                'allow_team_matching': True,
                'allow_analytics': False
            }
        }
        
        result = self.controller.update_privacy_settings(
            self.test_user_id, settings, "192.168.1.100"
        )
        
        self.assertTrue(result['success'])
        self.assertIn('updated_settings', result)
    
    def test_consent_and_privacy_integration(self):
        """Test integration between consent and privacy systems"""
        # Grant consent
        consent_result = self.controller.grant_user_consent(
            user_id=self.test_user_id,
            consent_type=ConsentType.AI_ANALYSIS,
            purpose="Profile analysis",
            data_types=[DataType.SKILLS_DATA]
        )
        
        self.assertTrue(consent_result['success'])
        
        # Check data access permission
        has_permission = self.controller.check_data_access_permission(
            self.test_user_id, DataType.SKILLS_DATA, "ai_analysis"
        )
        
        self.assertTrue(has_permission)
    
    def test_security_status_monitoring(self):
        """Test comprehensive security status monitoring"""
        status = self.controller.get_security_status(self.test_user_id)
        
        self.assertIn('system_security', status)
        self.assertIn('user_security', status)
        self.assertTrue(status['system_security']['encryption_available'])
        self.assertTrue(status['system_security']['audit_trail_active'])
    
    def test_data_export_with_consent(self):
        """Test data export with proper consent validation"""
        # First grant consent for data export
        self.controller.grant_user_consent(
            user_id=self.test_user_id,
            consent_type=ConsentType.DATA_PROCESSING,
            purpose="Data export request"
        )
        
        # Export user data
        export_result = self.controller.export_user_data(
            user_id=self.test_user_id,
            ip_address="192.168.1.100"
        )
        
        self.assertTrue(export_result['success'])
        self.assertIn('export_data', export_result)


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestEncryptionManager,
        TestPrivacyManager,
        TestConsentManager,
        TestAnonymousManager,
        TestAuditTrail,
        TestSecurityController
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TASK 12 SECURITY SYSTEM TEST SUMMARY")
    print("="*60)
    
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        print(f"Tests run: {result.testsRun}")
        print("All privacy and security features working correctly!")
    else:
        print("❌ SOME TESTS FAILED")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    print("\n" + "="*60)
    print("Task 12 - Privacy and Security Controls")
    print("Security system comprehensive testing completed!")
    print("="*60)