from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason, SpeechSynthesisCancellationDetails, CancellationReason
import json
import uuid
import os
import configparser
from datetime import datetime
import logging
import time  # Added for polling delay

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from google import genai  # Import the Gemini AI client library
except ImportError:
    raise ImportError("Please install the google-genai package")

# Load API keys from environment variables or config.ini
def load_config():
    config = configparser.ConfigParser()

    # Check if config.ini exists
    if not os.path.exists('config.ini'):
        logging.warning("config.ini file not found. Please create one with your API keys.")
        # Create a sample config.ini file
        config['API_KEYS'] = {
            'azure_subscription_key': 'your_azure_subscription_key_here',
            'azure_region': 'your_azure_region_here',
            'gemini_api_key': 'your_gemini_api_key_here',
            'azure_computer_vision_key': 'your_azure_computer_vision_key_here',
            'azure_computer_vision_endpoint': 'your_azure_computer_vision_endpoint_here'
        }
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
        logging.info("A sample config.ini file has been created. Please update it with your API keys.")
    else:
        config.read('config.ini')

    # Load keys from environment variables or config.ini
    subscription_key = os.getenv('AZURE_SUBSCRIPTION_KEY') or config.get('API_KEYS', 'azure_subscription_key', fallback=None)
    region = os.getenv('AZURE_REGION') or config.get('API_KEYS', 'azure_region', fallback=None)
    gemini_api_key = os.getenv('GEMINI_API_KEY') or config.get('API_KEYS', 'gemini_api_key', fallback=None)
    computer_vision_key = os.getenv('AZURE_COMPUTER_VISION_KEY') or config.get('API_KEYS', 'azure_computer_vision_key', fallback=None)
    computer_vision_endpoint = os.getenv('AZURE_COMPUTER_VISION_ENDPOINT') or config.get('API_KEYS', 'azure_computer_vision_endpoint', fallback=None)

    # Validate keys
    if not all([subscription_key, region, gemini_api_key, computer_vision_key, computer_vision_endpoint]):
        raise ValueError(
            "Missing required API keys. Please set them in config.ini or as environment variables.\n"
            "Required keys: azure_subscription_key, azure_region, gemini_api_key, azure_computer_vision_key, azure_computer_vision_endpoint"
        )

    return subscription_key, region, gemini_api_key, computer_vision_key, computer_vision_endpoint

# Load API keys
subscription_key, region, gemini_api_key, computer_vision_key, computer_vision_endpoint = load_config()

# Initialize the Gemini client with your API key
client = genai.Client(api_key=gemini_api_key)

app = Flask(__name__)

USER_CONTEXT_FILE = "user_context.json"
CONVERSATIONS_FILE = "conversations.json"
CHAT_MESSAGES_FILE = "chat_messages.json"  # New file to store chat messages

# Initialize the SpeechConfig with your Azure subscription key and region
speech_config = SpeechConfig(subscription=subscription_key, region=region)

# Initialize the ComputerVisionClient for Azure OCR
vision_client = ComputerVisionClient(
    endpoint=computer_vision_endpoint,
    credentials=CognitiveServicesCredentials(computer_vision_key)
)

# Load user context from a JSON file
def load_user_context():
    try:
        if os.path.exists(USER_CONTEXT_FILE):
            with open(USER_CONTEXT_FILE, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"Error loading user context: {e}")
        return {}

# Save user context to a JSON file
def save_user_context(context):
    try:
        with open(USER_CONTEXT_FILE, "w") as f:
            json.dump(context, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving user context: {e}")

# Load conversations from a JSON file
def load_conversations():
    try:
        if os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading conversations: {e}")
        return []

# Save conversations to a JSON file
def save_conversations(conversations):
    try:
        with open(CONVERSATIONS_FILE, "w") as f:
            json.dump(conversations, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving conversations: {e}")

# Load chat messages from a JSON file
def load_chat_messages():
    try:
        if os.path.exists(CHAT_MESSAGES_FILE):
            with open(CHAT_MESSAGES_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logging.error(f"Error loading chat messages: {e}")
        return []

# Save chat messages to a JSON file
def save_chat_messages(messages):
    try:
        with open(CHAT_MESSAGES_FILE, "w") as f:
            json.dump(messages, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving chat messages: {e}")

# Speech synthesis function
def synthesize_speech(text, voice_name="zu-ZA-ThandoNeural", pitch="0%", rate="1.0"):
    try:
        output_filename = str(uuid.uuid4()) + ".wav"
        audio_config = AudioConfig(filename=output_filename)
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        ssml_text = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{voice_name[:5]}'>
            <voice name='{voice_name}'>
                <prosody pitch='{pitch}' rate='{rate}'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """

        result = synthesizer.speak_ssml_async(ssml_text).get()

        if result.reason == ResultReason.SynthesizingAudioCompleted:
            logging.info(f"Speech synthesis succeeded. Audio saved to {output_filename}")
            return jsonify({'status': 'Speech synthesis complete', 'audio_file': output_filename})
        elif result.reason == ResultReason.Canceled:
            cancellation_details = SpeechSynthesisCancellationDetails(result)
            logging.error(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == CancellationReason.Error:
                logging.error(f"Error details: {cancellation_details.error_details}")
                return jsonify({'status': 'Speech synthesis failed', 'error': str(cancellation_details.error_details)}), 500
            return jsonify({'status': 'Speech synthesis failed', 'reason': str(cancellation_details.reason)}), 500
        else:
            return jsonify({'status': 'Speech synthesis failed', 'reason': str(result.reason)}), 500
    except Exception as e:
        logging.error(f"Error during speech synthesis: {e}")
        return jsonify({'status': 'Speech synthesis failed', 'error': str(e)}), 500

@app.route('/audio/<filename>')
def serve_audio(filename):
    try:
        return send_from_directory(directory=".", path=filename)
    except Exception as e:
        logging.error(f"Error serving audio file: {e}")
        return jsonify({'status': 'Error serving audio file', 'error': str(e)}), 500

class ConversationManager:
    def __init__(self):
        self.memory = []

    def generate_response(self, text):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=text
            )
            return response.text
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return "Error generating response. Please check the API key and try again."

    def add_to_memory(self, user_input, bot_response):
        self.memory.append(f"User: {user_input}")
        self.memory.append(f"Bot: {bot_response}")

    def analyze_conversation(self, conversation_text, context):
        recommendations = (
            "Based on the provided conversation, here are some recommendations to improve human connections and communication:\n"
            "- Encourage regular and open communication.\n"
            "- Foster a supportive and empathetic environment.\n"
            "- Promote face-to-face interactions and reduce excessive screen time.\n"
            "- Create opportunities for social engagement and community activities.\n"
            "- Address any underlying issues that may hinder effective communication."
        )
        return recommendations

    def adjust_tone(self, message, tone):
        adjusted_message = f"Rewrite the following message in a {tone} tone:\n\n{message}"
        response = self.generate_response(adjusted_message)
        return response

    def analyze_text_conversation(self, conversation_text):
        analysis = self.generate_response(f"Analyze the following conversation:\n\n{conversation_text}")
        return analysis

    def save_conversation(self, user_input, bot_response):
        conversations = load_conversations()
        conversations.append({"user_input": user_input, "bot_response": bot_response})
        save_conversations(conversations)

conversation_manager = ConversationManager()

@app.route('/', methods=['GET'])
def index():
    context = load_user_context()
    return render_template('index.html', context=context)

@app.route('/generate', methods=['POST'])
def generate_content_route():
    try:
        data = request.get_json()
        user_input = data['input']
        context = load_user_context()
        if "meeting" in user_input.lower():
            context["last_interaction_type"] = "meeting"
        elif "follow-up" in user_input.lower():
            context["last_interaction_type"] = "follow-up"
        save_user_context(context)
        response_text = conversation_manager.generate_response(user_input)
        conversation_manager.add_to_memory(user_input, response_text)
        conversation_manager.save_conversation(user_input, response_text)
        save_user_context(context)  # Ensure the context is saved after updating
        return jsonify({'response': response_text, 'context': context})
    except Exception as e:
        logging.error(f"Error generating content: {e}")
        return jsonify({'status': 'Error generating content', 'error': str(e)}), 500

@app.route('/synthesize', methods=['POST'])
def synthesize_route():
    try:
        data = request.get_json()
        text = data['text']
        voice_name = data.get('voice_name', "zu-ZA-ThandoNeural")
        pitch = data.get('pitch', "0%")  # Default pitch
        rate = data.get('rate', "1.0")   # Default rate

        response = synthesize_speech(text, voice_name, pitch, rate)
        return response
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

        response = synthesize_speech(text, voice_name, pitch, rate)
        return response
    except Exception as e:
        logging.error(f"Error during voice preview: {e}")
        return jsonify({'status': 'Voice preview failed', 'error': str(e)}), 500

@app.route('/clear_conversation', methods=['POST'])
def clear_conversation():
    conversation_manager.memory = []
    save_conversations([])
    return jsonify({'status': 'Conversation cleared'})

@app.route('/download_conversation', methods=['GET'])
def download_conversation():
    try:
        conversations = load_conversations()
        conversation_text = "\n".join([f"User: {conv['user_input']}\nBot: {conv['bot_response']}\n" for conv in conversations])
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
        recommendations = conversation_manager.analyze_conversation(conversation_text, context)
        save_user_context(context)  # Ensure the context is saved after analysis
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
        adjusted_message = conversation_manager.adjust_tone(message, tone)
        return jsonify({'adjusted_message': adjusted_message})
    except Exception as e:
        logging.error(f"Error adjusting tone: {e}")
        return jsonify({'status': 'Error adjusting tone', 'error': str(e)}), 500

@app.route('/analyze_conversation', methods=['POST'])
def analyze_conversation():
    try:
        data = request.get_json()
        conversation_text = data['conversation_text']
        analysis = conversation_manager.analyze_text_conversation(conversation_text)
        return jsonify({'analysis': analysis})
    except Exception as e:
        logging.error(f"Error analyzing conversation: {e}")
        return jsonify({'status': 'Error analyzing conversation', 'error': str(e)}), 500

@app.route('/extract_text', methods=['POST'])
def extract_text():
    try:
        # Check if an image file is present in the request
        if 'image' not in request.files:
            return jsonify({'status': 'Image file not found'}), 400
        
        image = request.files['image']
        
        # Use Azure OCR to extract text
        ocr_result = vision_client.read_in_stream(image, raw=True)
        
        if ocr_result is None:
            raise ValueError("OCR result is None")

        # Polling to get the OCR result
        result_url = ocr_result.headers.get('Operation-Location')
        if not result_url:
            raise ValueError("Operation-Location header not found in the response")

        # Extract the operation ID from the result URL
        operation_id = result_url.split('/')[-1]

        # Polling loop to check the status of the OCR operation
        while True:
            ocr_result = vision_client.get_read_result(operation_id)
            if ocr_result.status.lower() not in ['notstarted', 'running']:
                break
            time.sleep(1)  # Wait for 1 second before polling again
        
        # Extracted text
        extracted_text = ""
        if ocr_result.status == 'succeeded':
            for text_result in ocr_result.analyze_result.read_results:
                for line in text_result.lines:
                    extracted_text += line.text + "\n"
        
        return jsonify({'status': 'Text extraction complete', 'extracted_text': extracted_text})
    except Exception as e:
        logging.error(f"Error extracting text: {e}")
        return jsonify({'status': 'Text extraction failed', 'error': str(e)}), 500

# New routes for chat functionality
@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        username = data.get('username', 'Anonymous')
        message = data.get('message', '')

        if not message:
            return jsonify({'status': 'Message is empty'}), 400

        messages = load_chat_messages()
        messages.append({'username': username, 'message': message, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)