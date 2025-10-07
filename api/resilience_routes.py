"""
Resilience API Routes

This module contains all API endpoints related to resilience and error handling.
Extracted from app.py for better maintainability.
"""

from flask import Blueprint, request, jsonify
import logging
import asyncio
from datetime import datetime, timedelta

# Create blueprint for resilience routes
resilience_bp = Blueprint('resilience', __name__, url_prefix='/api/resilience')

logger = logging.getLogger(__name__)

# Import resilience modules
try:
    from resilience.error_handling import (
        resilience_manager, resilient_operation, resilient_context,
        ErrorCategory, ErrorSeverity
    )
    from resilience.network_resilience import (
        network_resilience, resilient_http_request, get_network_health
    )
    from resilience.agent_resilience import (
        agent_resilience, resilient_agent_call, get_agent_health
    )
    from resilience.data_sync_resilience import (
        data_sync_resilience, resilient_save_data, resilient_load_data,
        get_sync_status, DataOperation
    )
    RESILIENCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Resilience modules not available: {e}")
    RESILIENCE_AVAILABLE = False


@resilience_bp.route('/health', methods=['GET'])
def get_system_health():
    """Get comprehensive system health status"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({'error': 'Resilience features not available'}), 503
    
    try:
        health = resilience_manager.get_system_health()
        return jsonify(health)
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({'error': str(e)}), 500


@resilience_bp.route('/sync-status/<user_id>', methods=['GET'])
def get_user_sync_status(user_id):
    """Get data synchronization status for user"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({'error': 'Resilience features not available'}), 503
    
    try:
        status = data_sync_resilience.get_user_sync_status(user_id)
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return jsonify({'error': str(e)}), 500


@resilience_bp.route('/resolve-conflict', methods=['POST'])
def resolve_data_conflict():
    """Resolve data synchronization conflict"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({'error': 'Resilience features not available'}), 503
    
    try:
        data = request.get_json()
        conflict_id = data.get('conflict_id')
        resolution_strategy = data.get('resolution_strategy', 'latest_timestamp')
        user_choice = data.get('user_choice')
        
        if not conflict_id:
            return jsonify({'error': 'conflict_id is required'}), 400
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                data_sync_resilience.resolve_conflict(
                    conflict_id, 
                    resolution_strategy,
                    user_choice
                )
            )
        finally:
            loop.close()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error resolving conflict: {e}")
        return jsonify({'error': str(e)}), 500


@resilience_bp.route('/network-status', methods=['GET'])
def get_network_status():
    """Get network connectivity and resilience status"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({'error': 'Resilience features not available'}), 503
    
    try:
        status = network_resilience.get_network_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting network status: {e}")
        return jsonify({'error': str(e)}), 500


@resilience_bp.route('/error-history', methods=['GET'])
def get_error_history():
    """Get recent error history for monitoring"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({'error': 'Resilience features not available'}), 503
    
    try:
        limit = request.args.get('limit', 20, type=int)
        hours = request.args.get('hours', 24, type=int)
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_errors = [
            error.to_dict() for error in resilience_manager.error_history
            if error.timestamp > cutoff_time
        ][-limit:]
        
        return jsonify({
            'errors': recent_errors,
            'total_count': len(recent_errors),
            'time_range_hours': hours
        })
    except Exception as e:
        logger.error(f"Error getting error history: {e}")
        return jsonify({'error': str(e)}), 500


@resilience_bp.route('/test-resilience', methods=['POST'])
def test_resilience():
    """Test resilience features (for development/testing)"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({'error': 'Resilience features not available'}), 503
    
    try:
        data = request.get_json() or {}
        test_type = data.get('test_type', 'network')
        
        if test_type == 'network':
            # Test network resilience
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    resilient_http_request(
                        method='GET',
                        url='https://httpbin.org/get',
                        timeout=5
                    )
                )
            finally:
                loop.close()
            
            return jsonify({
                'test_type': 'network',
                'result': result,
                'status': 'success'
            })
            
        elif test_type == 'agent':
            # Test agent resilience
            agent_health = get_agent_health()
            return jsonify({
                'test_type': 'agent',
                'agent_health': agent_health,
                'status': 'success'
            })
            
        elif test_type == 'data_sync':
            # Test data sync resilience
            sync_status = get_sync_status()
            return jsonify({
                'test_type': 'data_sync',
                'sync_status': sync_status,
                'status': 'success'
            })
            
        else:
            return jsonify({
                'error': f'Unknown test type: {test_type}'
            }), 400
            
    except Exception as e:
        logger.error(f"Resilience test failed: {e}")
        return jsonify({
            'error': str(e),
            'status': 'failed'
        }), 500