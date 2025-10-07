"""
Authentication Routes

This module contains authentication-related endpoints.
Extracted from app.py for better maintainability.
"""

from flask import Blueprint, request, jsonify, redirect, url_for, flash, session
import json
import logging
from werkzeug.security import generate_password_hash, check_password_hash

# Create blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)

logger = logging.getLogger(__name__)

# Authentication storage (in production, use proper database)
users_db = {}


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """User signup endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Check if user already exists
        if username in users_db:
            return jsonify({'error': 'Username already exists'}), 400
        
        # Create new user
        users_db[username] = {
            'password': generate_password_hash(password),
            'email': email,
            'created_at': json.dumps(None),  # Would use datetime in real implementation
            'profile': {}
        }
        
        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user_id': username
        })
    
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return jsonify({'error': 'Signup failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Verify user credentials
        user = users_db.get(username)
        if not user or not check_password_hash(user['password'], password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Set session
        session['user_id'] = username
        session['authenticated'] = True
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user_id': username,
            'session_id': session.get('_id', 'unknown')
        })
    
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    try:
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        })
    
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'error': 'Logout failed'}), 500


@auth_bp.route('/check-session')
def check_session():
    """Check if user is authenticated"""
    try:
        user_id = session.get('user_id')
        authenticated = session.get('authenticated', False)
        
        return jsonify({
            'authenticated': authenticated,
            'user_id': user_id if authenticated else None
        })
    
    except Exception as e:
        logger.error(f"Session check error: {e}")
        return jsonify({'error': 'Session check failed'}), 500


@auth_bp.route('/profile/<user_id>')
def get_profile(user_id):
    """Get user profile"""
    try:
        # Check authentication
        current_user = session.get('user_id')
        if current_user != user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        user = users_db.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        profile = user.get('profile', {})
        profile.update({
            'username': user_id,
            'email': user.get('email', ''),
            'created_at': user.get('created_at')
        })
        
        return jsonify(profile)
    
    except Exception as e:
        logger.error(f"Profile get error: {e}")
        return jsonify({'error': 'Failed to get profile'}), 500


@auth_bp.route('/profile/<user_id>', methods=['PUT'])
def update_profile(user_id):
    """Update user profile"""
    try:
        # Check authentication
        current_user = session.get('user_id')
        if current_user != user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user = users_db.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update profile
        if 'profile' not in user:
            user['profile'] = {}
        
        # Update allowed fields
        allowed_fields = ['display_name', 'bio', 'preferences', 'settings']
        for field in allowed_fields:
            if field in data:
                user['profile'][field] = data[field]
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully'
        })
    
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        return jsonify({'error': 'Failed to update profile'}), 500


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_user = session.get('user_id')
        if not current_user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Current and new passwords are required'}), 400
        
        user = users_db.get(current_user)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Verify current password
        if not check_password_hash(user['password'], current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Update password
        user['password'] = generate_password_hash(new_password)
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
    
    except Exception as e:
        logger.error(f"Password change error: {e}")
        return jsonify({'error': 'Failed to change password'}), 500