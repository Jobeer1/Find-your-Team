"""
Security API Routes

This module contains all API endpoints related to privacy and security controls.
Extracted from app.py for better maintainability.
"""

from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta

# Create blueprint for security routes
security_bp = Blueprint('security', __name__, url_prefix='/api/security')

logger = logging.getLogger(__name__)

# Import security modules
try:
    from security import (
        security_controller, privacy_manager, consent_manager, anonymous_manager,
        audit_trail, DataType, ConsentType, PrivacyLevel, AuditAction
    )
    SECURITY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Security modules not available: {e}")
    SECURITY_AVAILABLE = False


@security_bp.route('/privacy-settings/<user_id>', methods=['GET', 'POST'])
def manage_privacy_settings(user_id):
    """Manage user privacy settings"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        if request.method == 'GET':
            # Get current privacy settings
            dashboard = security_controller.get_privacy_dashboard(user_id)
            return jsonify(dashboard)
        
        elif request.method == 'POST':
            # Update privacy settings
            data = request.get_json()
            settings_data = data.get('settings', {})
            
            # Convert string keys back to DataType enums
            settings = {}
            for data_type_str, setting_data in settings_data.items():
                try:
                    data_type = DataType(data_type_str)
                    settings[data_type] = setting_data
                except ValueError:
                    continue
            
            result = security_controller.update_privacy_settings(
                user_id=user_id,
                settings=settings,
                ip_address=request.remote_addr
            )
            
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error managing privacy settings: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/consent/<user_id>', methods=['GET', 'POST', 'DELETE'])
def manage_consent(user_id):
    """Manage user consent for data processing"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        if request.method == 'GET':
            # Get consent summary
            consent_summary = consent_manager.get_consent_summary(user_id)
            return jsonify(consent_summary)
        
        elif request.method == 'POST':
            # Grant consent
            data = request.get_json()
            consent_type = ConsentType(data.get('consent_type'))
            purpose = data.get('purpose', '')
            data_types = [DataType(dt) for dt in data.get('data_types', [])]
            expires_in_days = data.get('expires_in_days')
            
            result = security_controller.grant_user_consent(
                user_id=user_id,
                consent_type=consent_type,
                purpose=purpose,
                data_types=data_types,
                expires_in_days=expires_in_days,
                ip_address=request.remote_addr
            )
            
            return jsonify(result)
        
        elif request.method == 'DELETE':
            # Withdraw consent
            data = request.get_json()
            consent_type = ConsentType(data.get('consent_type'))
            
            result = security_controller.withdraw_user_consent(
                user_id=user_id,
                consent_type=consent_type,
                ip_address=request.remote_addr
            )
            
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error managing consent: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/anonymous/create', methods=['POST'])
def create_anonymous_session():
    """Create anonymous session"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json() or {}
        user_data = data.get('user_data')
        
        result = security_controller.create_anonymous_session(
            user_data=user_data,
            ip_address=request.remote_addr
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error creating anonymous session: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/anonymous/<anonymous_id>/operate', methods=['POST'])
def perform_anonymous_operation(anonymous_id):
    """Perform operation in anonymous mode"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        operation_data = data.get('operation_data', {})
        
        result = security_controller.perform_anonymous_operation(
            anonymous_id=anonymous_id,
            operation_type=operation_type,
            operation_data=operation_data,
            ip_address=request.remote_addr
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error performing anonymous operation: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/anonymous/<anonymous_id>/convert', methods=['POST'])
def convert_anonymous_to_user(anonymous_id):
    """Convert anonymous session to registered user"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id required'}), 400
        
        result = anonymous_manager.convert_to_registered_user(anonymous_id, user_id)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error converting anonymous session: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/audit/<user_id>', methods=['GET'])
def get_user_audit_trail(user_id):
    """Get user audit trail"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        # Parse query parameters
        limit = request.args.get('limit', 50, type=int)
        hours = request.args.get('hours', 24 * 7, type=int)  # Default: 1 week
        action_filter = request.args.getlist('actions')
        
        start_date = datetime.utcnow() - timedelta(hours=hours)
        
        # Convert action filter to enum
        actions = []
        for action_str in action_filter:
            try:
                actions.append(AuditAction(action_str))
            except ValueError:
                pass
        
        audit_records = audit_trail.get_user_audit_trail(
            user_id=user_id,
            start_date=start_date,
            action_filter=actions if actions else None,
            limit=limit
        )
        
        return jsonify({
            'audit_trail': audit_records,
            'total_records': len(audit_records),
            'time_range_hours': hours,
            'filters': action_filter
        })
    
    except Exception as e:
        logger.error(f"Error getting audit trail: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/export/<user_id>', methods=['POST'])
def export_user_data(user_id):
    """Export user data with proper consent validation"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json() or {}
        data_types = []
        
        # Parse requested data types
        for dt_str in data.get('data_types', []):
            try:
                data_types.append(DataType(dt_str))
            except ValueError:
                pass
        
        result = security_controller.export_user_data(
            user_id=user_id,
            data_types=data_types if data_types else None,
            ip_address=request.remote_addr
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error exporting user data: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/status', methods=['GET'])
def get_security_status():
    """Get comprehensive security status"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        user_id = request.args.get('user_id')
        status = security_controller.get_security_status(user_id)
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Error getting security status: {e}")
        return jsonify({'error': str(e)}), 500


@security_bp.route('/compliance-report', methods=['GET'])
def generate_compliance_report():
    """Generate compliance report for audit purposes"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        # Parse query parameters
        days = request.args.get('days', 30, type=int)
        include_details = request.args.get('include_details', 'false').lower() == 'true'
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        report = audit_trail.generate_compliance_report(
            start_date=start_date,
            end_date=end_date,
            include_details=include_details
        )
        
        return jsonify(report)
    
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}")
        return jsonify({'error': str(e)}), 500