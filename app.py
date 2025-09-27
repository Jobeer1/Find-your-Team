# core/__init__.py
import os
import logging
from flask import Flask
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.speech import SpeechConfig
from google import genai
import configparser
from pathlib import Path

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

class ConfigManager:
    """Handles configuration loading and validation"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from environment variables or config.ini"""
        self.config = configparser.ConfigParser()
        config_file = Path('config.ini')
        
        if not config_file.exists():
            self._create_default_config(config_file)
        
        self.config.read(config_file)
        self._validate_config()
    
    def _create_default_config(self, config_file):
        """Create default config file if it doesn't exist"""
        self.config['API_KEYS'] = {
            'azure_subscription_key': 'your_azure_subscription_key_here',
            'azure_region': 'your_azure_region_here',
            'gemini_api_key': 'your_gemini_api_key_here',
            'azure_computer_vision_key': 'your_azure_computer_vision_key_here',
            'azure_computer_vision_endpoint': 'your_azure_computer_vision_endpoint_here',
            'email_password': 'your_email_password_here',
        }
        with open(config_file, 'w') as f:
            self.config.write(f)
        logging.warning("Created default config.ini. Please update with your API keys.")
    
    def _validate_config(self):
        """Validate required configuration values"""
        required_keys = {
            'subscription_key': ('AZURE_SUBSCRIPTION_KEY', 'azure_subscription_key'),
            'region': ('AZURE_REGION', 'azure_region'),
            'gemini_api_key': ('GEMINI_API_KEY', 'gemini_api_key'),
            'computer_vision_key': ('AZURE_COMPUTER_VISION_KEY', 'azure_computer_vision_key'),
            'computer_vision_endpoint': ('AZURE_COMPUTER_VISION_ENDPOINT', 'azure_computer_vision_endpoint'),
            'email_password': ('EMAIL_PASSWORD', 'email_password')
        }
        
        self.values = {}
        for key, (env_var, config_key) in required_keys.items():
            self.values[key] = os.getenv(env_var) or self.config.get('API_KEYS', config_key, fallback=None)
            if self.values[key] is None:
                raise ValueError(f"Missing required configuration: {key}")

# Initialize Flask app
app = Flask(__name__)

# Initialize configuration
try:
    config = ConfigManager()
    app.config.update({
        'API_KEYS': config.values,
        'FILE_PATHS': {
            'user_context': "data/user_context.json",
            'conversations': "data/conversations.json",
            'chat_messages': "data/chat_messages.json",
            'tasks': "data/tasks.json",
            'notification_interval': "data/notification_interval.json",
            'area_of_interest': "data/area_of_interest.json",
            'message_icon': "data/message_icon.json"
        }
    })
except ValueError as e:
    logging.error(f"Configuration error: {e}")
    raise

# Initialize clients
speech_config = SpeechConfig(
    subscription=app.config['API_KEYS']['subscription_key'],
    region=app.config['API_KEYS']['region']
)

vision_client = ComputerVisionClient(
    endpoint=app.config['API_KEYS']['computer_vision_endpoint'],
    credentials=CognitiveServicesCredentials(app.config['API_KEYS']['computer_vision_key'])
)

gemini_client = genai.Client(api_key=app.config['API_KEYS']['gemini_api_key'])

import json
import logging
from pathlib import Path
from flask import current_app
from typing import Any, Callable, Optional, Union

class DataManager:
    """Handles all data persistence operations"""
    
    @staticmethod
    def _get_file_path(file_key: str) -> Path:
        """Get full path for a data file"""
        return Path(current_app.config['FILE_PATHS'][file_key])
    
    @staticmethod
    def _load_data(file_path: Path, default: Optional[Union[Callable, Any]] = None) -> Any:
        """Generic data loader with error handling"""
        try:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    return json.load(f)
            return default() if callable(default) else default
        except Exception as e:
            logging.error(f"Error loading {file_path.name}: {e}")
            return default() if callable(default) else default
    
    @staticmethod
    def _save_data(file_path: Path, data: Any) -> None:
        """Generic data saver with error handling"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving {file_path.name}: {e}")
            raise
    
    # User Context Operations
    @classmethod
    def load_user_context(cls) -> dict:
        return cls._load_data(cls._get_file_path('user_context'), default=dict)
    
    @classmethod
    def save_user_context(cls, context: dict) -> None:
        cls._save_data(cls._get_file_path('user_context'), context)
    
    # Conversation Operations
    @classmethod
    def load_conversations(cls) -> list:
        return cls._load_data(cls._get_file_path('conversations'), default=list)
    
    @classmethod
    def save_conversations(cls, conversations: list) -> None:
        cls._save_data(cls._get_file_path('conversations'), conversations)
    
    # Chat Message Operations
    @classmethod
    def load_chat_messages(cls) -> list:
        return cls._load_data(cls._get_file_path('chat_messages'), default=list)
    
    @classmethod
    def save_chat_messages(cls, messages: list) -> None:
        cls._save_data(cls._get_file_path('chat_messages'), messages)
    
    # Task Operations
    @classmethod
    def load_tasks(cls) -> list:
        return cls._load_data(cls._get_file_path('tasks'), default=list)
    
    @classmethod
    def save_tasks(cls, tasks: list) -> None:
        cls._save_data(cls._get_file_path('tasks'), tasks)
    
    # Notification Settings
    @classmethod
    def load_notification_interval(cls) -> int:
        data = cls._load_data(
            cls._get_file_path('notification_interval'),
            default=lambda: {"interval": 10}
        )
        return data.get("interval", 10)
    
    @classmethod
    def save_notification_interval(cls, interval: int) -> None:
        cls._save_data(cls._get_file_path('notification_interval'), {"interval": interval})
    
    # Area of Interest
    @classmethod
    def load_area_of_interest(cls) -> dict:
        return cls._load_data(
            cls._get_file_path('area_of_interest'),
            default=lambda: {"x1": 0, "y1": 0, "x2": 100, "y2": 100}
        )
    
    @classmethod
    def save_area_of_interest(cls, area: dict) -> None:
        cls._save_data(cls._get_file_path('area_of_interest'), area)
    
    # Message Icon Settings
    @classmethod
    def load_message_icon(cls) -> dict:
        return cls._load_data(
            cls._get_file_path('message_icon'),
            default=lambda: {"icon_path": "default_icon.png", "icon_size": 32}
        )
    
    @classmethod
    def save_message_icon(cls, icon_settings: dict) -> None:
        cls._save_data(cls._get_file_path('message_icon'), icon_settings)

import uuid
import time
import threading
import logging
import smtplib
from email.mime.text import MIMEText
import pyautogui
import cv2
import numpy as np
import pytesseract
from azure.cognitiveservices.speech import SpeechSynthesizer, AudioConfig, ResultReason
from flask import current_app
from .data import DataManager

class SpeechService:
    """Handles all text-to-speech operations"""
    
    def __init__(self, speech_config):
        self.speech_config = speech_config
    
    def synthesize(self, text: str, voice_name: str = "zu-ZA-ThandoNeural", 
                 pitch: str = "0%", rate: str = "1.0") -> dict:
        """Convert text to speech using Azure Cognitive Services"""
        try:
            output_filename = f"audio/{uuid.uuid4()}.wav"
            audio_config = AudioConfig(filename=output_filename)
            synthesizer = SpeechSynthesizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )

            ssml_text = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' 
                          xml:lang='{voice_name[:5]}'>
                          <voice name='{voice_name}'>
                          <prosody pitch='{pitch}' rate='{rate}'>{text}</prosody>
                          </voice></speak>"""

            result = synthesizer.speak_ssml_async(ssml_text).get()
            
            if result.reason == ResultReason.SynthesizingAudioCompleted:
                logging.info(f"Successfully synthesized speech to {output_filename}")
                return {'status': 'success', 'audio_file': output_filename}
            
            return {'status': 'failed', 'reason': str(result.reason)}
        
        except Exception as e:
            logging.error(f"Speech synthesis error: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

class NotificationService:
    """Handles notification detection and response"""
    
    def __init__(self, gemini_client):
        self.gemini_client = gemini_client
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the notification detection thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._detect_loop, daemon=True)
            self.thread.start()
            logging.info("Notification service started")
    
    def stop(self):
        """Stop the notification detection thread"""
        self.running = False
        if self.thread:
            self.thread.join()
        logging.info("Notification service stopped")
    
    def _detect_loop(self):
        """Main detection loop"""
        while self.running:
            try:
                self._check_for_notifications()
                time.sleep(DataManager.load_notification_interval())
            except Exception as e:
                logging.error(f"Notification detection error: {e}", exc_info=True)
                time.sleep(10)  # Wait before retrying
    
    def _check_for_notifications(self):
        """Check for new notifications in the area of interest"""
        area = DataManager.load_area_of_interest()
        screenshot = pyautogui.screenshot(
            region=(area["x1"], area["y1"], 
                   area["x2"]-area["x1"], area["y2"]-area["y1"])
        )
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        text = pytesseract.image_to_string(screenshot)
        
        if "New Message" in text or "Email" in text:
            message = self._extract_message_content(screenshot)
            if message:
                response = self._generate_response(message)
                self._send_response(response)
    
    def _extract_message_content(self, screenshot) -> Optional[str]:
        """Extract text content from screenshot"""
        try:
            return pytesseract.image_to_string(screenshot)
        except Exception as e:
            logging.error(f"Content extraction error: {e}")
            return None
    
    def _generate_response(self, message: str) -> str:
        """Generate response using Gemini AI"""
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=message
            )
            return response.text
        except Exception as e:
            logging.error(f"Response generation error: {e}")
            return "Error generating response."
    
    def _send_response(self, response: str):
        """Send response via email"""
        try:
            msg = MIMEText(response)
            msg['Subject'] = "Auto-Response"
            msg['From'] = "your_email@example.com"
            msg['To'] = "recipient@example.com"

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(
                    "your_email@example.com", 
                    current_app.config['API_KEYS']['email_password']
                )
                server.send_message(msg)
            logging.info("Response sent via email")
        except Exception as e:
            logging.error(f"Error sending response: {e}")

# Initialize services
speech_service = SpeechService(current_app.speech_config)
notification_service = NotificationService(current_app.gemini_client)
notification_service.start()

# routes/__init__.py
from flask import jsonify, request, send_file, send_from_directory
from datetime import datetime
import logging
import os
import uuid
from core import app, vision_client
from data import *
from services import synthesize_speech
from azure.cognitiveservices.speech import ResultReason, SpeechSynthesisCancellationDetails, CancellationReason

# Notification Settings Routes
@app.route('/set_notification_interval', methods=['POST'])
def set_notification_interval():
    try:
        data = request.get_json()
        interval = data.get('interval')
        if not interval or not isinstance(interval, int) or interval < 1:
            return jsonify({'status': 'Invalid interval. Must be a positive integer.'}), 400

        save_notification_interval(interval)
        return jsonify({'status': 'Notification interval updated', 'interval': interval})
    except Exception as e:
        logging.error(f"Error setting notification interval: {e}")
        return jsonify({'status': 'Error setting notification interval', 'error': str(e)}), 500

@app.route('/set_area_of_interest', methods=['POST'])
def set_area_of_interest():
    try:
        data = request.get_json()
        x1 = data.get('x1')
        y1 = data.get('y1')
        x2 = data.get('x2')
        y2 = data.get('y2')

        if not all([x1, y1, x2, y2]):
            return jsonify({'status': 'Invalid area of interest. All coordinates are required.'}), 400

        area = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        save_area_of_interest(area)
        return jsonify({'status': 'Area of interest updated', 'area': area})
    except Exception as e:
        logging.error(f"Error setting area of interest: {e}")
        return jsonify({'status': 'Error setting area of interest', 'error': str(e)}), 500

# Message Icon Routes
@app.route('/set_message_icon', methods=['POST'])
def set_message_icon():
    try:
        data = request.get_json()
        icon_path = data.get('icon_path')
        icon_size = data.get('icon_size')

        if not icon_path or not icon_size:
            return jsonify({'status': 'Invalid icon settings. Both icon path and size are required.'}), 400

        icon_settings = {"icon_path": icon_path, "icon_size": icon_size}
        save_message_icon(icon_settings)
        return jsonify({'status': 'Message icon updated', 'icon_settings': icon_settings})
    except Exception as e:
        logging.error(f"Error setting message icon: {e}")
        return jsonify({'status': 'Error setting message icon', 'error': str(e)}), 500

# Speech Synthesis Routes
@app.route('/synthesize', methods=['POST'])
def synthesize_route():
    try:
        data = request.get_json()
        text = data['text']
        voice_name = data.get('voice_name', "zu-ZA-ThandoNeural")
        pitch = data.get('pitch', "0%")
        rate = data.get('rate', "1.0")

        result = synthesize_speech(text, voice_name, pitch, rate)
        return result
    except Exception as e:
        logging.error(f"Error during speech synthesis: {e}")
        return jsonify({'status': 'Speech synthesis failed', 'error': str(e)}), 500

@app.route('/preview_voice', methods=['POST'])
def preview_voice():
    try:
        data = request.get_json()
        text = data.get('text', "This is a preview of the current voice settings.")
        voice_name = data.get('voice_name', "zu-ZA-ThandoNeural")
        pitch = data.get('pitch', "0%")
        rate = data.get('rate', "1.0")

        result = synthesize_speech(text, voice_name, pitch, rate)
        return result
    except Exception as e:
        logging.error(f"Error during voice preview: {e}")
        return jsonify({'status': 'Voice preview failed', 'error': str(e)}), 500

@app.route('/get_audio/<filename>', methods=['GET'])
def get_audio(filename):
    try:
        return send_from_directory('audio', filename)
    except Exception as e:
        logging.error(f"Error retrieving audio file: {e}")
        return jsonify({'status': 'Error retrieving audio file', 'error': str(e)}), 404

# Conversation Management Routes
@app.route('/clear_conversation', methods=['POST'])
def clear_conversation():
    try:
        save_conversations([])
        return jsonify({'status': 'Conversation cleared'})
    except Exception as e:
        logging.error(f"Error clearing conversation: {e}")
        return jsonify({'status': 'Error clearing conversation', 'error': str(e)}), 500

@app.route('/download_conversation', methods=['GET'])
def download_conversation():
    try:
        conversations = load_conversations()
        conversation_text = "\n".join(
            [f"User: {conv['user_input']}\nBot: {conv['bot_response']}\n"
             for conv in conversations]
        )
        filename = f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, "w") as f:
            f.write(conversation_text)
        return send_file(filename, as_attachment=True)
    except Exception as e:
        logging.error(f"Error downloading conversation: {e}")
        return jsonify({'status': 'Error downloading conversation', 'error': str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_content():
    try:
        data = request.get_json()
        conversation_text = data['conversation']
        context = load_user_context()

        # In a real implementation, you would call your analysis service here
        recommendations = {
            "sentiment": "positive",
            "key_topics": ["product inquiry", "technical support"],
            "suggested_responses": ["Would you like more information about this product?"]
        }

        save_user_context(context)
        return jsonify({'recommendations': recommendations, 'context': context})
    except Exception as e:
        logging.error(f"Error analyzing content: {e}")
        return jsonify({'status': 'Error analyzing content', 'error': str(e)}), 500

@app.route('/tone', methods=['POST'])
def change_tone():
    try:
        data = request.get_json()
        message = data['message']
        tone = data['tone']

        # In a real implementation, you would adjust the tone here
        tones = {
            'professional': "Thank you for your inquiry. We appreciate your business.",
            'friendly': "Hey there! Thanks for reaching out. We'd love to help!",
            'formal': "Dear valued customer, we acknowledge receipt of your communication."
        }
        adjusted_message = tones.get(tone, message)

        return jsonify({'adjusted_message': adjusted_message})
    except Exception as e:
        logging.error(f"Error adjusting tone: {e}")
        return jsonify({'status': 'Error adjusting tone', 'error': str(e)}), 500

@app.route('/analyze_conversation', methods=['POST'])
def analyze_conversation():
    try:
        data = request.get_json()
        conversation_text = data['conversation_text']

        # In a real implementation, you would analyze the conversation here
        analysis = {
            "sentiment": "neutral",
            "topics": ["general inquiry", "feedback"],
            "action_items": ["follow up in 24 hours"]
        }

        return jsonify({'analysis': analysis})
    except Exception as e:
        logging.error(f"Error analyzing conversation: {e}")
        return jsonify({'status': 'Error analyzing conversation', 'error': str(e)}), 500

# Text Extraction Routes
@app.route('/extract_text', methods=['POST'])
def extract_text():
    try:
        if 'image' not in request.files:
            return jsonify({'status': 'Image file not found'}), 400

        image = request.files['image']
        ocr_result = vision_client.read_in_stream(image, raw=True)

        if ocr_result is None:
            raise ValueError("OCR result is None")

        result_url = ocr_result.headers.get('Operation-Location')
        if not result_url:
            raise ValueError("Operation-Location header not found")

        operation_id = result_url.split('/')[-1]

        while True:
            ocr_result = vision_client.get_read_result(operation_id)
            if ocr_result.status.lower() not in ['notstarted', 'running']:
                break
            time.sleep(1)

        extracted_text = ""
        if ocr_result.status == 'succeeded':
            for text_result in ocr_result.analyze_result.read_results:
                for line in text_result.lines:
                    extracted_text += line.text + "\n"

        return jsonify({'status': 'Text extraction complete', 'extracted_text': extracted_text})
    except Exception as e:
        logging.error(f"Error extracting text: {e}")
        return jsonify({'status': 'Text extraction failed', 'error': str(e)}), 500

# Chat Routes
@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        username = data.get('username', 'Anonymous')
        message = data.get('message', '')

        if not message:
            return jsonify({'status': 'Message is empty'}), 400

        messages = load_chat_messages()
        messages.append({
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_chat_messages(messages)

        return jsonify({'status': 'Message sent successfully'})
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return jsonify({'status': 'Error sending message', 'error': str(e)}), 500

@app.route('/get_messages', methods=['GET'])
def get_messages():
    try:
        messages = load_chat_messages()
        return jsonify({'messages': messages})
    except Exception as e:
        logging.error(f"Error retrieving messages: {e}")
        return jsonify({'status': 'Error retrieving messages', 'error': str(e)}), 500

# Health Check Route
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

from core import app
from routes import init_routes
from services import notification_service
import logging

def create_app():
    """Application factory function"""
    # Initialize routes
    init_routes(app)
    
    # Ensure data directory exists
    from pathlib import Path
    Path("data").mkdir(exist_ok=True)
    Path("audio").mkdir(exist_ok=True)
    
    @app.teardown_appcontext
    def shutdown_services(exception=None):
        """Cleanup when application shuts down"""
        notification_service.stop()
        if exception:
            logging.error(f"Application shutdown with exception: {exception}")
    
    return app

if __name__ == '__main__':
    application = create_app()
    try:
        application.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        logging.info("Shutting down gracefully...")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        raise