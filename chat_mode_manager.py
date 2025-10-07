"""
Bandwidth Detection and Chat Mode Manager
Provides intelligent detection of connection quality and chat mode selection
Gives users clear visibility and control over their chat experience
"""

import time
import threading
import json
from datetime import datetime
from typing import Dict, List, Optional, Callable
from enum import Enum
import logging

from local_storage_manager import ChatMode, LocalStorageManager

logger = logging.getLogger(__name__)

class BandwidthQuality(Enum):
    """Bandwidth quality levels"""
    HIGH = "high"      # >1 Mbps, <100ms latency
    MEDIUM = "medium"  # 256Kbps-1Mbps, 100-300ms latency  
    LOW = "low"        # <256Kbps, >300ms latency
    UNKNOWN = "unknown"

class NetworkType(Enum):
    """Network connection types"""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    CELLULAR_4G = "cellular_4g"
    CELLULAR_3G = "cellular_3g"
    CELLULAR_2G = "cellular_2g"
    UNKNOWN = "unknown"

class ChatModeManager:
    """
    Manages chat modes with intelligent bandwidth detection
    Provides user notifications and manual mode selection
    """
    
    def __init__(self, user_id: str, storage_manager: LocalStorageManager):
        self.user_id = user_id
        self.storage_manager = storage_manager
        
        # Current connection state
        self.current_mode = ChatMode.OFFLINE_MODE
        self.bandwidth_quality = BandwidthQuality.UNKNOWN
        self.network_type = NetworkType.UNKNOWN
        self.is_lan_available = False
        
        # Mode change callbacks
        self.mode_change_callbacks: List[Callable] = []
        
        # Auto-detection settings
        self.auto_detection_enabled = True
        self.detection_interval = 30  # seconds
        self.detection_thread = None
        
        # Mode restrictions and user preferences
        self.available_modes = set()
        self.user_preferred_mode = None
        self.force_mode = None  # Manual override
        
        logger.info(f"ChatModeManager initialized for user {user_id}")
    
    def start_monitoring(self):
        """Start continuous bandwidth monitoring and mode management"""
        if self.detection_thread and self.detection_thread.is_alive():
            logger.warning("Monitoring already active")
            return
        
        self.detection_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.detection_thread.start()
        logger.info("Bandwidth monitoring started")
    
    def stop_monitoring(self):
        """Stop bandwidth monitoring"""
        self.auto_detection_enabled = False
        if self.detection_thread:
            self.detection_thread.join(timeout=5)
        logger.info("Bandwidth monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop for bandwidth detection"""
        while self.auto_detection_enabled:
            try:
                # Detect current network conditions
                self._detect_bandwidth()
                self._detect_network_type()
                self._detect_lan_availability()
                
                # Update available modes
                self._update_available_modes()
                
                # Auto-select best mode if not manually overridden
                if not self.force_mode:
                    self._auto_select_mode()
                
                # Sleep until next detection
                time.sleep(self.detection_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.detection_interval)
    
    def _detect_bandwidth(self):
        """Detect current bandwidth quality"""
        try:
            # Simple bandwidth test using small data transfer timing
            start_time = time.time()
            
            # Simulate bandwidth test (in real implementation, use actual network test)
            # For demo, we'll use simulated values based on network type
            test_duration = 0.1  # 100ms baseline
            
            if self.network_type == NetworkType.ETHERNET:
                test_duration = 0.05  # Fast ethernet
                quality = BandwidthQuality.HIGH
            elif self.network_type == NetworkType.WIFI:
                test_duration = 0.08  # Good WiFi
                quality = BandwidthQuality.HIGH
            elif self.network_type == NetworkType.CELLULAR_4G:
                test_duration = 0.12  # Decent 4G
                quality = BandwidthQuality.MEDIUM
            elif self.network_type == NetworkType.CELLULAR_3G:
                test_duration = 0.25  # Slow 3G
                quality = BandwidthQuality.LOW
            else:
                test_duration = 0.15
                quality = BandwidthQuality.MEDIUM
            
            # Update bandwidth quality
            old_quality = self.bandwidth_quality
            self.bandwidth_quality = quality
            
            if old_quality != quality:
                logger.info(f"Bandwidth quality changed: {old_quality.value} -> {quality.value}")
                self._notify_mode_change()
            
        except Exception as e:
            logger.error(f"Bandwidth detection failed: {e}")
            self.bandwidth_quality = BandwidthQuality.UNKNOWN
    
    def _detect_network_type(self):
        """Detect network connection type"""
        try:
            # In real implementation, use system network APIs
            # For demo, simulate network type detection
            import platform
            import subprocess
            
            if platform.system() == "Windows":
                # Check for ethernet/wifi on Windows
                try:
                    result = subprocess.run(['netsh', 'interface', 'show', 'interface'], 
                                          capture_output=True, text=True, timeout=5)
                    if 'Ethernet' in result.stdout and 'Connected' in result.stdout:
                        self.network_type = NetworkType.ETHERNET
                    elif 'Wi-Fi' in result.stdout and 'Connected' in result.stdout:
                        self.network_type = NetworkType.WIFI
                    else:
                        self.network_type = NetworkType.UNKNOWN
                except:
                    self.network_type = NetworkType.UNKNOWN
            else:
                # Default for other systems
                self.network_type = NetworkType.WIFI
                
        except Exception as e:
            logger.error(f"Network type detection failed: {e}")
            self.network_type = NetworkType.UNKNOWN
    
    def _detect_lan_availability(self):
        """Check if LAN chat is available"""
        try:
            # Simple LAN detection by checking for other devices on network
            import socket
            
            # Check if we can bind to LAN discovery port
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind(('', 0))  # Bind to any available port
                sock.close()
                self.is_lan_available = True
            except:
                self.is_lan_available = False
                
        except Exception as e:
            logger.error(f"LAN detection failed: {e}")
            self.is_lan_available = False
    
    def update_network_conditions(self, bandwidth_info: Dict[str, any] = None):
        """Update network conditions with provided information or trigger detection"""
        try:
            if bandwidth_info:
                # Update with provided bandwidth information
                if 'quality' in bandwidth_info:
                    quality_str = bandwidth_info['quality'].lower()
                    if quality_str in [q.value for q in BandwidthQuality]:
                        self.bandwidth_quality = BandwidthQuality(quality_str)
                
                if 'network_type' in bandwidth_info:
                    type_str = bandwidth_info['network_type'].lower()
                    if type_str in [t.value for t in NetworkType]:
                        self.network_type = NetworkType(type_str)
                
                if 'is_lan_available' in bandwidth_info:
                    self.is_lan_available = bool(bandwidth_info['is_lan_available'])
                    
                logger.info(f"Network conditions updated from provided info: "
                           f"Quality={self.bandwidth_quality.value}, Type={self.network_type.value}")
            else:
                # Trigger fresh detection
                self._detect_bandwidth()
                self._detect_network_type()
                self._detect_lan_availability()
                logger.info("Network conditions updated via fresh detection")
            
            # Update available modes and auto-select if needed
            self._update_available_modes()
            if not self.force_mode:
                self._auto_select_mode()
                
        except Exception as e:
            logger.error(f"Failed to update network conditions: {e}")
            # Set to safe defaults
            self.bandwidth_quality = BandwidthQuality.MEDIUM
            self.network_type = NetworkType.UNKNOWN
            self.is_lan_available = False
    
    def _update_available_modes(self):
        """Update available chat modes based on current conditions"""
        self.available_modes.clear()
        
        # Always available: Offline mode
        self.available_modes.add(ChatMode.OFFLINE_MODE)
        
        # Global modes based on bandwidth
        if self.bandwidth_quality == BandwidthQuality.HIGH:
            self.available_modes.add(ChatMode.HIGH_BANDWIDTH_GLOBAL)
            self.available_modes.add(ChatMode.LOW_BANDWIDTH_GLOBAL)  # Can downgrade
        elif self.bandwidth_quality == BandwidthQuality.MEDIUM:
            self.available_modes.add(ChatMode.HIGH_BANDWIDTH_GLOBAL)  # Can try
            self.available_modes.add(ChatMode.LOW_BANDWIDTH_GLOBAL)
        elif self.bandwidth_quality == BandwidthQuality.LOW:
            self.available_modes.add(ChatMode.LOW_BANDWIDTH_GLOBAL)
        
        # LAN modes if available
        if self.is_lan_available:
            if self.bandwidth_quality in [BandwidthQuality.HIGH, BandwidthQuality.MEDIUM]:
                self.available_modes.add(ChatMode.LAN_HIGH_BANDWIDTH)
            self.available_modes.add(ChatMode.LAN_LOW_BANDWIDTH)
    
    def _auto_select_mode(self):
        """Automatically select the best chat mode"""
        if self.force_mode:
            return  # User has manually selected a mode
        
        # Priority order for auto-selection
        mode_priority = [
            ChatMode.HIGH_BANDWIDTH_GLOBAL,
            ChatMode.LAN_HIGH_BANDWIDTH,
            ChatMode.LOW_BANDWIDTH_GLOBAL,
            ChatMode.LAN_LOW_BANDWIDTH,
            ChatMode.OFFLINE_MODE
        ]
        
        # Find best available mode
        for preferred_mode in mode_priority:
            if preferred_mode in self.available_modes:
                if preferred_mode != self.current_mode:
                    self._change_mode(preferred_mode, auto_selected=True)
                break
    
    def _change_mode(self, new_mode: ChatMode, auto_selected: bool = False):
        """Change to a new chat mode"""
        old_mode = self.current_mode
        self.current_mode = new_mode
        
        # Update storage manager
        self.storage_manager.update_chat_mode(new_mode, self.bandwidth_quality.value)
        
        # Notify callbacks
        self._notify_mode_change()
        
        logger.info(f"Chat mode changed: {old_mode.value} -> {new_mode.value} " + 
                   f"({'auto' if auto_selected else 'manual'})")
    
    def manually_select_mode(self, mode: ChatMode) -> bool:
        """Allow user to manually select chat mode"""
        if mode not in self.available_modes:
            logger.warning(f"Mode {mode.value} not available in current conditions")
            return False
        
        self.force_mode = mode
        self._change_mode(mode, auto_selected=False)
        return True
    
    def enable_auto_mode(self):
        """Re-enable automatic mode selection"""
        self.force_mode = None
        self._auto_select_mode()
        logger.info("Auto mode selection enabled")
    
    def get_mode_info(self) -> Dict[str, any]:
        """Get comprehensive information about current mode and options"""
        return {
            'current_mode': {
                'mode': self.current_mode.value,
                'display_name': self._get_mode_display_name(self.current_mode),
                'description': self._get_mode_description(self.current_mode),
                'auto_selected': self.force_mode is None
            },
            'network_status': {
                'bandwidth_quality': self.bandwidth_quality.value,
                'network_type': self.network_type.value,
                'lan_available': self.is_lan_available
            },
            'available_modes': [
                {
                    'mode': mode.value,
                    'display_name': self._get_mode_display_name(mode),
                    'description': self._get_mode_description(mode),
                    'recommended': mode == self._get_recommended_mode()
                }
                for mode in self.available_modes
            ],
            'mode_indicators': {
                'global_high': ChatMode.HIGH_BANDWIDTH_GLOBAL in self.available_modes,
                'global_low': ChatMode.LOW_BANDWIDTH_GLOBAL in self.available_modes,
                'lan_high': ChatMode.LAN_HIGH_BANDWIDTH in self.available_modes,
                'lan_low': ChatMode.LAN_LOW_BANDWIDTH in self.available_modes,
                'offline': True  # Always available
            }
        }
    
    def _get_recommended_mode(self) -> ChatMode:
        """Get the recommended mode for current conditions"""
        if self.bandwidth_quality == BandwidthQuality.HIGH:
            return ChatMode.HIGH_BANDWIDTH_GLOBAL if not self.is_lan_available else ChatMode.LAN_HIGH_BANDWIDTH
        elif self.bandwidth_quality == BandwidthQuality.MEDIUM:
            return ChatMode.HIGH_BANDWIDTH_GLOBAL
        elif self.bandwidth_quality == BandwidthQuality.LOW:
            return ChatMode.LAN_LOW_BANDWIDTH if self.is_lan_available else ChatMode.LOW_BANDWIDTH_GLOBAL
        else:
            return ChatMode.OFFLINE_MODE
    
    def _get_mode_display_name(self, mode: ChatMode) -> str:
        """Get user-friendly display name for chat mode"""
        display_names = {
            ChatMode.HIGH_BANDWIDTH_GLOBAL: "🌐 Global Chat (High Speed)",
            ChatMode.LOW_BANDWIDTH_GLOBAL: "🌐 Global Chat (Low Bandwidth)",
            ChatMode.LAN_HIGH_BANDWIDTH: "🏠 LAN Chat (High Speed)",
            ChatMode.LAN_LOW_BANDWIDTH: "🏠 LAN Chat (Low Bandwidth)",
            ChatMode.OFFLINE_MODE: "📱 Offline Mode"
        }
        return display_names.get(mode, mode.value)
    
    def _get_mode_description(self, mode: ChatMode) -> str:
        """Get detailed description for chat mode"""
        descriptions = {
            ChatMode.HIGH_BANDWIDTH_GLOBAL: "Full-featured global chat with rich media, file sharing, and real-time features. Best for high-speed connections.",
            ChatMode.LOW_BANDWIDTH_GLOBAL: "Text-focused global chat optimized for slow connections. Limited media and file sharing to save bandwidth.",
            ChatMode.LAN_HIGH_BANDWIDTH: "Local network chat with full features. Fast file sharing within your local network.",
            ChatMode.LAN_LOW_BANDWIDTH: "Local network chat optimized for slower LAN connections. Text-focused with basic file sharing.",
            ChatMode.OFFLINE_MODE: "Local-only mode. Messages stored locally until connection is restored."
        }
        return descriptions.get(mode, "Standard chat mode")
    
    def add_mode_change_callback(self, callback: Callable):
        """Add callback to be notified of mode changes"""
        self.mode_change_callbacks.append(callback)
    
    def _notify_mode_change(self):
        """Notify all callbacks of mode change"""
        for callback in self.mode_change_callbacks:
            try:
                callback(self.get_mode_info())
            except Exception as e:
                logger.error(f"Mode change callback failed: {e}")
    
    def get_usage_statistics(self) -> Dict[str, any]:
        """Get usage statistics for different modes"""
        try:
            import sqlite3
            with sqlite3.connect(self.storage_manager.db_path) as conn:
                cursor = conn.cursor()
                
                # Mode usage statistics
                cursor.execute("""
                    SELECT chat_mode, 
                           COUNT(*) as sessions,
                           AVG(CASE WHEN connection_end IS NOT NULL 
                               THEN (julianday(connection_end) - julianday(connection_start)) * 24 * 60 
                               ELSE 0 END) as avg_session_minutes,
                           SUM(messages_sent) as total_messages,
                           SUM(bytes_transferred) as total_bytes
                    FROM connection_history 
                    GROUP BY chat_mode
                """)
                
                stats = {}
                for row in cursor.fetchall():
                    mode, sessions, avg_minutes, messages, bytes_transferred = row
                    stats[mode] = {
                        'sessions': sessions,
                        'avg_session_minutes': round(avg_minutes or 0, 1),
                        'total_messages': messages or 0,
                        'total_bytes': bytes_transferred or 0,
                        'avg_messages_per_session': round((messages or 0) / sessions if sessions > 0 else 0, 1)
                    }
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get usage statistics: {e}")
            return {}
    
    def export_mode_config(self) -> Dict[str, any]:
        """Export current mode configuration for backup"""
        return {
            'user_id': self.user_id,
            'export_timestamp': datetime.now().isoformat(),
            'current_mode': self.current_mode.value,
            'force_mode': self.force_mode.value if self.force_mode else None,
            'auto_detection_enabled': self.auto_detection_enabled,
            'detection_interval': self.detection_interval,
            'bandwidth_quality': self.bandwidth_quality.value,
            'network_type': self.network_type.value,
            'is_lan_available': self.is_lan_available,
            'usage_statistics': self.get_usage_statistics()
        }