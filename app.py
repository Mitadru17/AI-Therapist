from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import google.generativeai as genai
import os
import time
import random
import uuid
import json
import requests
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from functools import wraps
import firebase_admin
from firebase_admin import credentials, auth, firestore
from mood_tracker import MoodTracker, MoodEntry
from emotion_detector import detect_emotion
from typing import Optional
import re
from affirmations import get_affirmation
import math

def is_crisis_message(text):
    """
    Checks if a message contains crisis indicators related to suicide, self-harm, or panic.
    
    Args:
        text (str): The message text to analyze
        
    Returns:
        bool: True if crisis indicators are detected, False otherwise
    """
    if not text or not isinstance(text, str):
        return False
        
    # Convert to lowercase for case-insensitive matching
    text = text.lower()
    
    # Crisis keywords related to suicide, self-harm, and panic
    crisis_keywords = [
        # Suicide-related
        'suicide', 'kill myself', 'end my life', 'take my life', 'don\'t want to live',
        'no reason to live', 'better off dead', 'want to die', 'rather be dead',
        'should just die', 'going to end it', 'saying goodbye', 'final goodbye',
        
        # Self-harm related
        'cut myself', 'cutting myself', 'harm myself', 'hurt myself', 'self-harm',
        'self harm', 'injure myself', 'burning myself', 'hurting myself',
        
        # Severe distress/panic
        'can\'t breathe', 'heart racing', 'panic attack', 'having a breakdown',
        'losing control', 'can\'t take it anymore', 'unbearable pain', 'overwhelmed',
        'no way out', 'trapped', 'hopeless', 'helpless',
        
        # Immediate danger
        'overdose', 'pills', 'gun', 'jump', 'hanging', 'bridge', 'roof'
    ]
    
    # Check for presence of any crisis keywords
    for keyword in crisis_keywords:
        if keyword in text:
            return True
            
    return False

def get_calming_resources():
    """
    Returns a list of calming techniques and grounding exercises for crisis situations.
    
    Returns:
        list: A list of dictionaries containing calming resources
    """
    return [
        {
            "title": "5-4-3-2-1 Grounding Technique",
            "description": "Acknowledge 5 things you see, 4 things you can touch, 3 things you hear, 2 things you smell, and 1 thing you taste.",
            "type": "grounding"
        },
        {
            "title": "Deep Breathing Exercise",
            "description": "Breathe in slowly through your nose for 4 counts, hold for 2, then exhale through your mouth for 6 counts. Repeat 5 times.",
            "type": "breathing"
        },
        {
            "title": "Progressive Muscle Relaxation",
            "description": "Tense and then release each muscle group in your body, starting from your toes and working up to your head.",
            "type": "relaxation"
        },
        {
            "title": "Safe Place Visualization",
            "description": "Close your eyes and imagine a place where you feel completely safe and at peace. Focus on the details of this place.",
            "type": "visualization"
        },
        {
            "title": "Body Scan Meditation",
            "description": "Starting from your toes and moving up, pay attention to each part of your body without judgment, noticing any sensations.",
            "type": "meditation"
        }
    ]

def get_crisis_response():
    """
    Returns a standard compassionate response for crisis situations.
    
    Returns:
        str: A supportive message for someone in crisis
    """
    return "I notice you may be going through a difficult time right now. Your safety and well-being are important. Please consider reaching out to a mental health professional or crisis support service who can provide immediate help. Remember that you're not alone, and support is available 24/7."

# Load environment variables
load_dotenv()

# Configure Gemini API
API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=API_KEY)

# Define Gemini configuration with a supported model
GEMINI_CONFIG = {
    "model": "gemini-1.5-flash",  # Using a confirmed supported model
    "generation_config": {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 512,
    }
}

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 7  # 7 days
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize Firebase Admin SDK
db = None
try:
    # Check for Firebase credentials in environment variable
    firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if firebase_credentials_path and os.path.exists(firebase_credentials_path):
        # Initialize Firebase Admin with credentials file
        cred = credentials.Certificate(firebase_credentials_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Admin SDK initialized with credentials file")
    else:
        # Try using the FIREBASE_CREDENTIALS environment variable directly
        firebase_credentials_json = os.getenv("FIREBASE_CREDENTIALS")
        if firebase_credentials_json:
            try:
                # Parse the JSON string into a dict
                cred_dict = json.loads(firebase_credentials_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                db = firestore.client()
                print("Firebase Admin SDK initialized with credentials JSON")
            except json.JSONDecodeError:
                print("Invalid Firebase credentials JSON format")
        else:
            print("No Firebase credentials found. Using in-memory database.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {str(e)}")
    print("Falling back to in-memory database")

# Initialize in-memory data storage for development
in_memory_db = {
    'users': {},  # user_id -> user data
    'chats': {},  # user_id -> {chat_id -> chat data}
    'quotes': {}  # user_id -> [quote data]
}

# Initialize mood tracker
mood_tracker = MoodTracker(db)

# Initialize chat emotion logger
class ChatEmotionLogger:
    def __init__(self, db: Optional[firestore.Client]):
        self.db = db
        self.in_memory_storage = []  # Fallback storage when db is None
        if db is not None:
            self.collection = self.db.collection('chat_emotions')
        else:
            print("Using in-memory storage for chat emotions")

    def log_emotion(self, user_id: str, message: str, detected_emotion: str, timestamp: int = None):
        """
        Log a chat message and its detected emotion.
        """
        if timestamp is None:
            timestamp = int(time.time())

        entry = {
            'user_id': user_id,
            'message': message,
            'emotion': detected_emotion,
            'timestamp': timestamp
        }

        if self.db is not None:
            doc_ref = self.collection.document()
            doc_ref.set(entry)
            return doc_ref.id
        else:
            # Use in-memory storage
            entry_id = str(len(self.in_memory_storage))
            self.in_memory_storage.append(entry)
            return entry_id

chat_emotion_logger = ChatEmotionLogger(db)

# Firebase authentication middleware - simplified for development
def firebase_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For development, we'll create a test user ID if none exists
        if 'user_id' not in session:
            # Check for Firebase Auth
            if firebase_admin._apps and db is not None:
                # Try to get user from authentication token
                session_token = request.cookies.get('__session')
                if session_token:
                    try:
                        # Verify token and get user info
                        decoded_token = auth.verify_id_token(session_token)
                        user_id = decoded_token['uid']
                        session['user_id'] = user_id
                        
                        # Check if user exists in Firestore
                        user_ref = db.collection('users').document(user_id)
                        user_doc = user_ref.get()
                        
                        if not user_doc.exists:
                            # Create user document with basic info
                            user_ref.set({
                                'email': decoded_token.get('email', ''),
                                'name': decoded_token.get('name', ''),
                                'photo_url': decoded_token.get('picture', ''),
                                'created_at': int(time.time())
                            })
                            
                            # Create initial collections
                            user_ref.collection('chats')
                            user_ref.collection('quotes')
                    except Exception as e:
                        print(f"Firebase auth error: {str(e)}")
                        # Fall back to test user
                        user_id = 'test-user-' + str(uuid.uuid4())
                        session['user_id'] = user_id
                else:
                    # No session token, create test user
                    user_id = 'test-user-' + str(uuid.uuid4())
                    session['user_id'] = user_id
            else:
                # Firebase Admin not initialized, create test user
                user_id = 'test-user-' + str(uuid.uuid4())
                session['user_id'] = user_id
            
            # Initialize user data in memory if needed
            user_id = session['user_id']
            if user_id not in in_memory_db['users']:
                in_memory_db['users'][user_id] = {
                    'email': 'test@example.com',
                    'name': 'Test User'
                }
                in_memory_db['chats'][user_id] = {}
                in_memory_db['quotes'][user_id] = []
        
        return f(*args, **kwargs)
    
    return decorated_function

# Authentication routes
@app.route('/sign-in')
def sign_in():
    # Allow access regardless of authentication status
    # The client-side JS will handle redirecting authenticated users
    firebase_config = {
        'apiKey': os.getenv('FIREBASE_API_KEY', ''),
        'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN', 'ai-therapist-30c16.firebaseapp.com'),
        'projectId': os.getenv('FIREBASE_PROJECT_ID', 'ai-therapist-30c16'),
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', ''),
        'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
        'appId': os.getenv('FIREBASE_APP_ID', '')
    }
    return render_template('sign-in.html', firebase_config=firebase_config)

@app.route('/sign-up')
def sign_up():
    # Allow access regardless of authentication status
    # The client-side JS will handle redirecting authenticated users
    firebase_config = {
        'apiKey': os.getenv('FIREBASE_API_KEY', ''),
        'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN', 'ai-therapist-30c16.firebaseapp.com'),
        'projectId': os.getenv('FIREBASE_PROJECT_ID', 'ai-therapist-30c16'),
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', ''),
        'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
        'appId': os.getenv('FIREBASE_APP_ID', '')
    }
    return render_template('sign-up.html', firebase_config=firebase_config)

# Main routes
@app.route('/')
@firebase_required
def index():
    """
    Main application page
    """
    # Get user ID from session
    user_id = session.get('user_id', 'test-user')
    
    # Get Google Maps API key
    google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', 'AIzaSyBu60Y-R7XrkTJF-YDkLsSvkMZMxnuueOw')
    
    # Firebase configuration
    firebase_config = {
        'apiKey': os.environ.get('FIREBASE_API_KEY', ''),
        'authDomain': os.environ.get('FIREBASE_AUTH_DOMAIN', ''),
        'projectId': os.environ.get('FIREBASE_PROJECT_ID', ''),
        'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET', ''),
        'messagingSenderId': os.environ.get('FIREBASE_MESSAGING_SENDER_ID', ''),
        'appId': os.environ.get('FIREBASE_APP_ID', '')
    }
    
    # Get user data from Firestore
    user_data = {}
    if firebase_admin._apps:
        db = firestore.client()
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
    
    # Render the template with user data
    return render_template('index.html', 
                          user_id=user_id, 
                          user_data=user_data, 
                          firebase_config=firebase_config,
                          google_maps_api_key=google_maps_api_key)

# Define the base therapeutic system prompt
BASE_THERAPEUTIC_PROMPT = """
You are a calm, empathetic mental health therapist. Your responses should be:
- Warm and supportive, using phrases like "It's okay to feel that way" or "You're doing your best"
- Non-judgmental and validating of the user's feelings
- Thoughtful but concise
- Focused on helping the user explore their thoughts and feelings
- Encouraging and gentle in your approach

Always prioritize a compassionate tone while providing helpful guidance.
"""

# List of quote prompt variations to ensure diversity
QUOTE_PROMPTS = [
    """
    Generate a single, inspiring therapeutic quote about self-compassion and personal growth.
    The quote should be brief (under 150 characters), uplifting, and meaningful.
    Do not include any explanation, attribution, or quotation marks unless it's from a specific person.
    """,
    
    """
    Create one short, powerful quote about resilience and overcoming challenges.
    Make it inspirational, concise (under 150 characters), and focused on inner strength.
    Only provide the quote itself without any additional context or formatting.
    """,
    
    """
    Provide a single mindfulness quote that offers perspective on being present.
    Keep it brief (under 150 characters), insightful, and calming.
    No explanation or context needed, just the quote itself.
    """,
    
    """
    Generate one unique quote about healing and emotional well-being.
    It should be short (under 150 characters), hopeful, and emotionally resonant.
    Just the quote text with no additional formatting or context.
    """,
    
    """
    Create a single motivational quote about self-acceptance and personal value.
    Keep it concise (under 150 characters), affirming, and positive.
    Only the quote text is needed, no attribution unless it's from someone specific.
    """
]

# Define mood-specific additions to the prompt
MOOD_PROMPTS = {
    "happy": """
The user is feeling happy. While maintaining your therapeutic approach:
- Celebrate their positive emotions
- Help them savor this feeling
- Explore what's contributing to their happiness
- Encourage them to build on these positive experiences
""",
    "sad": """
The user is feeling sad. While maintaining your therapeutic approach:
- Be especially gentle and compassionate
- Validate that sadness is a normal human emotion
- Offer comfort with phrases like "I hear how difficult this is for you"
- Provide hope while acknowledging their current feelings
- Suggest small, manageable ways to care for themselves
""",
    "anxious": """
The user is feeling anxious. While maintaining your therapeutic approach:
- Help them feel grounded with your calm responses
- Acknowledge their anxiety without minimizing it
- Use reassuring phrases like "Many people experience anxiety"
- Suggest breathing techniques or mindfulness if appropriate
- Focus on what they can control in the present moment
""",
    "angry": """
The user is feeling angry. While maintaining your therapeutic approach:
- Acknowledge their anger as valid without judgment
- Help them express their feelings in a constructive way
- Use phrases like "It makes sense that you feel this way"
- Guide them toward understanding what's beneath the anger
- Offer perspective while respecting their emotions
""",
    "neutral": """
The user hasn't shown strong emotional signals in their messages. Maintain your general therapeutic approach and:
- Be attentive to emotional cues in their messages
- Adjust your tone accordingly as the conversation progresses
- Use open-ended questions to explore how they're feeling
"""
}

# Emergency resources to display when crisis is detected
EMERGENCY_RESOURCES = [
    {
        "name": "National Suicide Prevention Lifeline",
        "contact": "988 or 1-800-273-8255",
        "description": "24/7, free and confidential support for people in distress, prevention and crisis resources for you or your loved ones",
        "category": "crisis",
        "website": "https://988lifeline.org/",
        "tags": ["suicide", "crisis", "24/7"]
    },
    {
        "name": "Crisis Text Line",
        "contact": "Text HOME to 741741",
        "description": "Free 24/7 support from trained crisis counselors via text message for anyone in crisis",
        "category": "crisis",
        "website": "https://www.crisistextline.org/",
        "tags": ["text", "crisis", "24/7"]
    },
    {
        "name": "SAMHSA's National Helpline",
        "contact": "1-800-662-4357",
        "description": "Treatment referral and information service (24/7) for individuals and families facing mental and/or substance use disorders",
        "category": "mental",
        "website": "https://www.samhsa.gov/find-help/national-helpline",
        "tags": ["substance abuse", "referral", "24/7"]
    },
    {
        "name": "National Domestic Violence Hotline",
        "contact": "1-800-799-7233",
        "description": "24/7 support, resources, and advice for safety for anyone experiencing domestic violence or abuse",
        "category": "crisis",
        "website": "https://www.thehotline.org/",
        "tags": ["domestic violence", "abuse", "safety"]
    },
    {
        "name": "Trevor Project (LGBTQ+)",
        "contact": "1-866-488-7386",
        "description": "Crisis intervention and suicide prevention services for LGBTQ+ young people under 25",
        "category": "specialized",
        "website": "https://www.thetrevorproject.org/",
        "tags": ["LGBTQ+", "youth", "suicide prevention"]
    },
    {
        "name": "Veterans Crisis Line",
        "contact": "988, Press 1 or text 838255",
        "description": "Connects veterans and their families with qualified VA responders through a confidential toll-free hotline",
        "category": "specialized",
        "website": "https://www.veteranscrisisline.net/",
        "tags": ["veterans", "military", "crisis"]
    },
    {
        "name": "IMAlive",
        "contact": "www.imalive.org",
        "description": "Virtual crisis center with 24/7 chat support from trained volunteers providing emotional support",
        "category": "crisis",
        "website": "https://www.imalive.org/",
        "tags": ["chat", "emotional support", "volunteer"]
    },
    {
        "name": "7 Cups",
        "contact": "www.7cups.com",
        "description": "Online therapy and free emotional support chat with trained volunteer listeners",
        "category": "mental",
        "website": "https://www.7cups.com/",
        "tags": ["chat", "emotional support", "therapy"]
    },
    {
        "name": "Psychology Today Therapist Finder",
        "contact": "www.psychologytoday.com/us/therapists",
        "description": "Directory to find therapists, psychiatrists, treatment centers and support groups near you",
        "category": "mental",
        "website": "https://www.psychologytoday.com/us/therapists",
        "tags": ["therapist", "directory", "mental health"]
    },
    {
        "name": "National Alliance on Mental Illness (NAMI)",
        "contact": "1-800-950-6264",
        "description": "Helpline provides information, resource referrals and support for people living with mental health conditions and their family members",
        "category": "mental",
        "website": "https://www.nami.org/",
        "tags": ["resources", "education", "mental illness"]
    },
    {
        "name": "Postpartum Support International",
        "contact": "1-800-944-4773",
        "description": "Help for women and families suffering from perinatal mood disorders, including postpartum depression",
        "category": "specialized",
        "website": "https://www.postpartum.net/",
        "tags": ["postpartum", "pregnancy", "depression"]
    },
    {
        "name": "Trans Lifeline",
        "contact": "1-877-565-8860",
        "description": "Peer support phone service run by and for trans people, with operators available daily",
        "category": "specialized",
        "website": "https://translifeline.org/",
        "tags": ["transgender", "peer support", "LGBTQ+"]
    }
]

# Helper function to safely generate Gemini response
def generate_safe_response(prompt, max_retries=2):
    """Helper function to safely generate responses from Gemini with retries"""
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(
                model_name="models/" + GEMINI_CONFIG["model"],  # Use full model name with "models/" prefix
                generation_config=GEMINI_CONFIG["generation_config"]
            )
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(1)  # Short delay before retry
    return None

def get_therapy_prompt(user_message, emotion=None):
    """Helper function to construct the therapy prompt"""
    base_prompt = """You are a compassionate AI therapist. Your responses should be:
    - Warm and supportive
    - Non-judgmental and validating
    - Brief but thoughtful (2-3 sentences)
    - Focused on the user's feelings
    """
    
    emotion_context = f"\nThe user's current emotion is: {emotion}\n" if emotion else "\n"
    return f"{base_prompt}{emotion_context}\nUser: {user_message}\nTherapist:"

@app.route('/api/chats', methods=['GET'])
@firebase_required
def get_chats():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # If Firestore is available, use it
        if db is not None:
            # Get chats from Firestore
            chats_ref = db.collection('users').document(user_id).collection('chats')
            chats_query = chats_ref.order_by('updated_at', direction=firestore.Query.DESCENDING)
            chat_docs = chats_query.stream()
            
            chats = []
            for doc in chat_docs:
                chat_data = doc.to_dict()
                chat_data['id'] = doc.id
                chats.append(chat_data)
                
            if not chats:
                # If no chats exist, return empty list
                return jsonify([])
                
            return jsonify(chats)
        else:
            # Get chats from in-memory database
            user_chats = in_memory_db['chats'].get(user_id, {})
            
            # Convert to list and sort by updated_at (newest first)
            chats = []
            for chat_id, chat_data in user_chats.items():
                chat_with_id = dict(chat_data)
                chat_with_id['id'] = chat_id
                chats.append(chat_with_id)
            
            chats.sort(key=lambda x: x.get('updated_at', 0), reverse=True)
            
            return jsonify(chats)
    except Exception as e:
        print(f"Error getting chats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chats/new', methods=['POST'])
@firebase_required
def create_chat():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        timestamp = int(time.time())
        
        # Get title from request or use default
        data = request.get_json() or {}
        title = data.get('title', 'New Therapy Session')
        
        chat_data = {
            'title': title,
            'created_at': timestamp,
            'updated_at': timestamp,
            'messages': [
                {
                    'sender': 'system',
                    'text': 'Hello there! 👋 I\'m your friendly AI Therapist, here to support you on your journey. Feel free to share what\'s on your mind, and I\'ll listen and respond to how you\'re feeling. I\'m here to help. 💖',
                    'timestamp': timestamp
                }
            ]
        }
        
        # If Firestore is available, use it
        if db is not None:
            # Check if user document exists, if not create it
            user_ref = db.collection('users').document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                # Create user document with basic info
                user_ref.set({
                    'email': in_memory_db['users'].get(user_id, {}).get('email', 'user@example.com'),
                    'name': in_memory_db['users'].get(user_id, {}).get('name', 'User'),
                    'created_at': timestamp
                })
            
            # Create chat document with auto-generated ID
            chat_ref = user_ref.collection('chats').document()
            chat_ref.set(chat_data)
            chat_id = chat_ref.id
        else:
            # Store in in-memory database
            chat_id = str(uuid.uuid4())
            if user_id not in in_memory_db['chats']:
                in_memory_db['chats'][user_id] = {}
            in_memory_db['chats'][user_id][chat_id] = chat_data
        
        # Include the ID in the response
        response_data = dict(chat_data)
        response_data['id'] = chat_id
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Error creating chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chats/<chat_id>', methods=['GET'])
@firebase_required
def get_chat(chat_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # If Firestore is available, use it
        if db is not None:
            # Get chat from Firestore
            chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
            chat_doc = chat_ref.get()
            
            if not chat_doc.exists:
                return jsonify({'error': 'Chat not found'}), 404
                
            chat_data = chat_doc.to_dict()
            chat_data['id'] = chat_id
            
            return jsonify(chat_data)
        else:
            # Get chat from in-memory database
            user_chats = in_memory_db['chats'].get(user_id, {})
            
            if chat_id not in user_chats:
                return jsonify({'error': 'Chat not found'}), 404
            
            chat_data = dict(user_chats[chat_id])
            chat_data['id'] = chat_id
            
            return jsonify(chat_data)
    except Exception as e:
        print(f"Error getting chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
@firebase_required
def delete_chat(chat_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # If Firestore is available, use it
        if db is not None:
            # Delete chat from Firestore
            chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
            chat_doc = chat_ref.get()
            
            if not chat_doc.exists:
                return jsonify({'error': 'Chat not found'}), 404
                
            # Delete the chat document
            chat_ref.delete()
            
            return jsonify({'success': True})
        else:
            # Delete chat from in-memory database
            user_chats = in_memory_db['chats'].get(user_id, {})
            
            if chat_id not in user_chats:
                return jsonify({'error': 'Chat not found'}), 404
            
            del user_chats[chat_id]
            
            return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chats/<chat_id>/messages', methods=['POST'])
@firebase_required
def add_message(chat_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Get message from request
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message'}), 400
        
        user_message = data['message']
        timestamp = int(time.time())
        
        # First check if this is a crisis message
        is_crisis = is_crisis_message(user_message)
        
        # Detect emotion from user message
        detected_emotion = detect_emotion(user_message)
        print(f"Chat message received. Detected emotion: {detected_emotion}")
        print(f"Message: {user_message[:50]}...")
        
        # Log emotion to mood tracker if not neutral
        if detected_emotion != 'neutral':
            log_mood_to_tracker(user_id, detected_emotion, user_message)
        
        # Create user message object
        user_message_obj = {
            'sender': 'user',
            'text': user_message,
            'timestamp': timestamp,
            'emotion': detected_emotion,
            'is_crisis': is_crisis
        }
        
        # Get chat from database
        if db is not None:
            # Get chat from Firestore
            chat_ref = db.collection('users').document(user_id).collection('chats').document(chat_id)
            chat_doc = chat_ref.get()
            
            if not chat_doc.exists:
                return jsonify({'error': 'Chat not found'}), 404
            
            # Get chat data
            chat_data = chat_doc.to_dict()
            messages = chat_data.get('messages', [])
            
            # Add user message
            messages.append(user_message_obj)
        else:
            # Get chat from in-memory database
            user_chats = in_memory_db['chats'].get(user_id, {})
            
            if chat_id not in user_chats:
                return jsonify({'error': 'Chat not found'}), 404
            
            chat_data = user_chats[chat_id]
            
            # Add user message to chat
            if 'messages' not in chat_data:
                chat_data['messages'] = []
            
            chat_data['messages'].append(user_message_obj)
            messages = chat_data['messages']
        
        # If this is a crisis message, provide a static response with resources
        if is_crisis:
            print("CRISIS MESSAGE DETECTED in chat!")
            
            # Log the crisis message if database is available
            if db is not None:
                try:
                    db.collection('crisis_logs').add({
                        'user_id': user_id,
                        'message': user_message,
                        'timestamp': timestamp,
                        'session_type': 'chat',
                        'chat_id': chat_id,
                        'detected_keywords': True
                    })
                except Exception as e:
                    print(f"Error logging crisis message: {str(e)}")
            
            # Define calming resources and grounding techniques
            calming_resources = get_calming_resources()
            
            # Select relevant emergency resources
            selected_emergency_resources = EMERGENCY_RESOURCES[:5]
            
            # Create static crisis response
            crisis_response = get_crisis_response()
            
            # Create bot message object
            bot_message_obj = {
                'sender': 'bot',
                'text': crisis_response,
                'timestamp': timestamp,
                'responding_to_emotion': detected_emotion,
                'responding_to_crisis': True
            }
            
            # Add bot message to messages
            messages.append(bot_message_obj)
            
            # Update chat data
            if db is not None:
                chat_data['messages'] = messages
                chat_data['updated_at'] = timestamp
                
                # Update chat document in Firestore
                chat_ref.set(chat_data)
            else:
                chat_data['messages'] = messages
                chat_data['updated_at'] = timestamp
            
            return jsonify({
                'message': {
                    'sender': 'bot',
                    'text': crisis_response,
                    'timestamp': timestamp
                },
                'detected_emotion': detected_emotion,
                'is_crisis': True,
                'show_resources': True,
                'emergency_resources': selected_emergency_resources,
                'resource_message': "Here are some resources that can provide immediate support:",
                'calming_resources': calming_resources,
                'calming_message': "While you seek help, here are some techniques that might help you feel more grounded:"
            })
        
        # If not a crisis, proceed with normal AI response
        try:
            # Simple direct model creation
            model = genai.GenerativeModel(
                model_name="models/gemini-1.5-flash"
            )
            
            # Generate response with a simple prompt
            prompt = f"You are a compassionate AI therapist. The user is feeling {detected_emotion}. Respond with empathy in 2-3 sentences.\n\nUser: {user_message}\nYour response:"
            print(f"Sending prompt to Gemini: {prompt[:50]}...")
            
            # Generate response
            response = model.generate_content(prompt)
            
            # Extract text safely
            ai_message = "I'm here to listen. Could you please share that again?"
            if response and hasattr(response, 'text'):
                ai_message = response.text.strip()
                print(f"AI response received: {ai_message[:50]}...")
            else:
                print("Warning: Empty or invalid response from Gemini API")
            
            # Create bot message object
            bot_message_obj = {
                'sender': 'bot',
                'text': ai_message,
                'timestamp': timestamp,
                'responding_to_emotion': detected_emotion,
                'responding_to_crisis': False
            }
            
            # Add bot message to messages
            messages.append(bot_message_obj)
            
            # Update chat data
            if db is not None:
                chat_data['messages'] = messages
                chat_data['updated_at'] = timestamp
                
                # Update chat document in Firestore
                chat_ref.set(chat_data)
            else:
                chat_data['messages'] = messages
                chat_data['updated_at'] = timestamp
            
            return jsonify({
                'message': {
                    'sender': 'bot',
                    'text': ai_message,
                    'timestamp': timestamp
                },
                'detected_emotion': detected_emotion,
                'is_crisis': False,
                'show_resources': False
            })
            
        except Exception as e:
            print(f"Error generating AI response: {str(e)}")
            return jsonify({
                'message': {
                    'text': "I'm here to listen. Could you please share that again?",
                    'sender': 'bot',
                    'timestamp': timestamp
                },
                'error': str(e)
            }), 500
            
    except Exception as e:
        print(f"Error in add_message: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
@firebase_required
def chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message'}), 400
        
        user_message = data['message']
        print(f"Chat request received: {user_message[:50]}...")
        timestamp = int(time.time())
        user_id = session.get('user_id', 'anonymous')
        
        # First check if this is a crisis message
        is_crisis = is_crisis_message(user_message)
        
        if is_crisis:
            print(f"CRISIS MESSAGE DETECTED in general chat from user {user_id}")
            
            # Log the crisis message if database is available
            if db is not None:
                try:
                    db.collection('crisis_logs').add({
                        'user_id': user_id,
                        'message': user_message,
                        'timestamp': timestamp,
                        'session_type': 'general',
                        'detected_keywords': True
                    })
                except Exception as e:
                    print(f"Error logging crisis message: {str(e)}")
            
            # Define calming resources and grounding techniques
            calming_resources = get_calming_resources()
            
            # Return crisis response with resources
            return jsonify({
                'response': get_crisis_response(),
                'is_crisis': True,
                'resources': EMERGENCY_RESOURCES[:5],
                'resource_message': "Here are some resources that can provide immediate support:",
                'calming_resources': calming_resources,
                'calming_message': "While you seek help, here are some techniques that might help you feel more grounded:"
            })
        
        # If not a crisis, proceed with normal response generation
        try:
            # Simple direct model creation
            model = genai.GenerativeModel(
                model_name="models/gemini-1.5-flash"
            )
            
            # Simple prompt
            prompt = f"You are a helpful and compassionate AI therapist. User: {user_message}\nYour response:"
            print(f"Sending prompt to Gemini: {prompt[:50]}...")
            
            # Generate response
            response = model.generate_content(prompt)
            
            # Extract text safely
            ai_response = "I'm here to listen. Could you please share that again?"
            if response and hasattr(response, 'text'):
                ai_response = response.text.strip()
                print(f"AI response received: {ai_response[:50]}...")
            else:
                print("Warning: Empty or invalid response from Gemini API")
            
            return jsonify({
                'response': ai_response,
                'is_crisis': False
            })
        
        except Exception as e:
            print(f"Error generating chat response: {str(e)}")
            return jsonify({
                'response': "I'm here to listen. Could you please share that again?",
                'error': str(e)
            })
            
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/quote', methods=['GET'])
@firebase_required
def get_quote():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Add randomization factors
        current_timestamp = int(time.time())
        
        # Get requested category from query params, default to random
        category = request.args.get('category', 'random')
        
        # Map category to appropriate prompt
        category_prompts = {
            'inspiration': """
                Generate a single, inspiring therapeutic quote that motivates action and positive change.
                The quote should be brief (under 150 characters), uplifting, and focused on motivation.
                Do not include any explanation, attribution, or quotation marks unless it's from a specific person.
            """,
            'mindfulness': """
                Provide a single mindfulness quote that helps ground someone in the present moment.
                Keep it brief (under 150 characters), insightful, and focused on awareness and presence.
                Just the quote text with no additional formatting.
            """,
            'growth': """
                Create a single therapeutic quote about personal growth, learning, and self-improvement.
                Make it concise (under 150 characters), affirming, and focused on the journey of becoming better.
                Only provide the quote itself without any additional context.
            """,
            'resilience': """
                Generate one unique quote about resilience, overcoming challenges, and inner strength.
                It should be short (under 150 characters), empowering, and focused on bouncing back from difficulty.
                Just the quote text with no additional formatting or context.
            """
        }
        
        # Select a prompt based on category or random if not specified
        if category != 'random' and category in category_prompts:
            selected_prompt = category_prompts[category]
        else:
            # If random or invalid category, choose randomly from all prompts
            all_prompts = list(category_prompts.values()) + QUOTE_PROMPTS
            selected_prompt = random.choice(all_prompts)
            
            # Also randomly assign a category for the quote
            category = random.choice(list(category_prompts.keys()))
        
        # Add timestamp to ensure uniqueness
        prompt_with_timestamp = f"{selected_prompt}\n\nGenerate something completely unique. Current timestamp: {current_timestamp}"
        
        # Configure for higher creativity
        generation_config = {
            "temperature": 1.0,  # Increased temperature for more randomness
            "top_p": 1.0,
            "top_k": 40,
            "max_output_tokens": 256,
        }
        
        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash",  # Use full model name with "models/" prefix
            generation_config=generation_config
        )
        
        response = model.generate_content(prompt_with_timestamp)
        
        # Format the quote (remove extra quotes if present)
        if not response:
            quote_text = "Every moment is a fresh beginning."
        else:
            quote_text = response.text.strip()
            if quote_text.startswith('"') and quote_text.endswith('"'):
                quote_text = quote_text[1:-1]
        
        # Create quote object with category
        quote_data = {
            'text': quote_text,
            'category': category,
            'created_at': current_timestamp
        }
        
        # Store the quote in Firestore if available
        if db is not None:
            # Add a new quote document with auto-generated ID
            quotes_ref = db.collection('users').document(user_id).collection('quotes')
            quote_ref = quotes_ref.document()
            quote_ref.set(quote_data)
            
            # Include the document ID in the response
            quote_data['id'] = quote_ref.id
        
        # Return the quote as JSON
        return jsonify(quote_data)
    
    except Exception as e:
        print(f"Error generating quote: {str(e)}")
        return jsonify({
            'text': "Every moment is a fresh beginning.",
            'category': "resilience",
            'error': str(e)
        }), 200

@app.route('/api/quotes', methods=['GET'])
@firebase_required
def get_quotes():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters for filtering
        category = request.args.get('category')
        search_term = request.args.get('search')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        
        # Use Firestore if available
        if db is not None:
            # Get all quotes for the user
            quotes_ref = db.collection('users').document(user_id).collection('quotes')
            query = quotes_ref.order_by('created_at', direction=firestore.Query.DESCENDING)
            
            # Apply category filter if provided
            if category and category != 'all':
                query = query.where('category', '==', category)
                
            # Get all quotes that match the query
            quote_docs = query.stream()
            
            # Convert to list for filtering and pagination
            quotes = []
            for doc in quote_docs:
                quote_data = doc.to_dict()
                quote_data['id'] = doc.id  # Add document ID as quote ID
                
                # Apply search term filter if provided
                if search_term and search_term.lower() not in quote_data.get('text', '').lower():
                    continue
                    
                quotes.append(quote_data)
                
            # Calculate pagination
            total_quotes = len(quotes)
            total_pages = max(1, (total_quotes + per_page - 1) // per_page)
            page = min(page, total_pages)  # Ensure page doesn't exceed total pages
            
            # Get paginated subset
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_quotes)
            paginated_quotes = quotes[start_idx:end_idx]
            
            # Return quotes with pagination metadata
            return jsonify({
                'quotes': paginated_quotes,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_quotes': total_quotes,
                    'total_pages': total_pages
                }
            })
        else:
            # If Firestore is not available, return empty list with pagination metadata
            return jsonify({
                'quotes': [],
                'pagination': {
                    'page': 1,
                    'per_page': per_page,
                    'total_quotes': 0,
                    'total_pages': 1
                }
            })
    except Exception as e:
        print(f"Error getting quotes: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes/<quote_id>', methods=['DELETE'])
@firebase_required
def delete_quote(quote_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Use Firestore if available
        if db is not None:
            # Delete the quote from Firestore
            db.collection('users').document(user_id).collection('quotes').document(quote_id).delete()
            return jsonify({'success': True})
        else:
            # If Firestore is not available, return error
            return jsonify({'error': 'Quotes storage not available in development mode'}), 500
    except Exception as e:
        print(f"Error deleting quote: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clerk/user-data', methods=['GET'])
def clerk_user_data():
    """This endpoint is kept for backward compatibility but now redirects to Firebase user data"""
    return redirect(url_for('firebase_user_data'))

# Firebase user data endpoint
@app.route('/api/firebase/user-data', methods=['GET'])
def firebase_user_data():
    """Return user data from the session token"""
    session_token = request.cookies.get('__session')
    
    # If no token, return empty data
    if not session_token:
        return jsonify({
            'isSignedIn': False,
            'userId': None
        })
    
    try:
        # Store the session token in the Flask session for consistency
        session['firebase_session_token'] = session_token
        
        # Try to verify the token and get Firebase user data
        user_data = {}
        try:
            if firebase_admin._apps:
                decoded_token = auth.verify_id_token(session_token)
                user_id = decoded_token['uid']
                user_data = {
                    'displayName': decoded_token.get('name'),
                    'email': decoded_token.get('email'),
                    'photoURL': decoded_token.get('picture')
                }
        except Exception as e:
            print(f"Token verification error: {str(e)}")
            # Continue with session user ID if token verification fails
        
        # Get or create user ID for the session
        user_id = session.get('user_id', str(uuid.uuid4()))
        session['user_id'] = user_id
        
        return jsonify({
            'isSignedIn': True,
            'userId': user_id,
            'userData': user_data
        })
    
    except Exception as e:
        print(f"Error getting user data: {str(e)}")
        return jsonify({
            'isSignedIn': False,
            'userId': None,
            'error': str(e)
        }), 500

# Add user verification endpoint
@app.route('/api/verify-auth', methods=['GET'])
def verify_auth():
    # Get session token from cookie
    session_token = request.cookies.get('__session')
    
    if not session_token:
        return jsonify({
            'isSignedIn': False,
            'userId': None
        })
    
    # Store the session token in the Flask session for consistency
    session['firebase_session_token'] = session_token
    
    # Try to verify the token if Firebase Admin is initialized
    user_data = {}
    try:
        if firebase_admin._apps:
            decoded_token = auth.verify_id_token(session_token)
            user_id = decoded_token['uid']
            session['user_id'] = user_id
            user_data = {
                'displayName': decoded_token.get('name'),
                'email': decoded_token.get('email'),
                'photoURL': decoded_token.get('picture')
            }
    except Exception as e:
        print(f"Auth verification error: {str(e)}")
        # Fall back to session user ID
    
    # Get or create user ID for the session
    user_id = session.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
        session['user_id'] = user_id
    
    return jsonify({
        'isSignedIn': True,
        'userId': user_id,
        'userData': user_data
    })

# Session management middleware
@app.before_request
def check_session():
    # Get session token from cookie
    session_token = request.cookies.get('__session')
    
    # If user has a token but we don't have it in the session, add it
    if session_token and not session.get('firebase_session_token'):
        session['firebase_session_token'] = session_token
    
    # If user doesn't have a token but we have one in the session, clear it
    if not session_token and session.get('firebase_session_token'):
        session.clear()
    
    # Allow access to sign-in and sign-up pages without authentication
    if request.path == '/sign-in' or request.path == '/sign-up':
        return
    
    # If user is accessing protected routes but doesn't have a token, redirect to sign-in
    if not session_token and request.path.startswith('/api/'):
        session.clear()
        return jsonify({'error': 'Authentication required'}), 401

@app.route('/api/mood', methods=['POST'])
@firebase_required
def add_mood():
    data = request.get_json()
    
    if not all(k in data for k in ['date', 'mood']):
        return jsonify({'error': 'Missing required fields'}), 400
        
    entry = MoodEntry(
        user_id=session.get('user_id'),
        date=data['date'],
        mood=data['mood'],
        note=data.get('note')
    )
    
    entry_id = mood_tracker.add_mood_entry(entry)
    return jsonify({'id': entry_id}), 201

@app.route('/api/mood/<entry_id>', methods=['GET'])
@firebase_required
def get_mood(entry_id):
    entry = mood_tracker.get_mood_entry(entry_id)
    
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    if entry.user_id != session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    return jsonify(entry.to_dict())

@app.route('/api/mood/user', methods=['GET'])
@firebase_required
def get_user_moods():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    entries = mood_tracker.get_user_mood_entries(
        session.get('user_id'),
        start_date=start_date,
        end_date=end_date
    )
    
    return jsonify([entry.to_dict() for entry in entries])

@app.route('/api/mood/<entry_id>', methods=['PUT'])
@firebase_required
def update_mood(entry_id):
    entry = mood_tracker.get_mood_entry(entry_id)
    
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    if entry.user_id != session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    success = mood_tracker.update_mood_entry(
        entry_id,
        mood=data.get('mood'),
        note=data.get('note')
    )
    
    return jsonify({'success': success})

@app.route('/api/mood/<entry_id>', methods=['DELETE'])
@firebase_required
def delete_mood(entry_id):
    entry = mood_tracker.get_mood_entry(entry_id)
    
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    if entry.user_id != session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    success = mood_tracker.delete_mood_entry(entry_id)
    return jsonify({'success': success})

@app.route('/log_mood', methods=['POST'])
@firebase_required
def log_mood():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get the mood from request or detect it from the note
        mood = data.get('mood')
        note = data.get('note', '')
        
        # If no mood is provided but there's a note, detect the mood
        if not mood and note:
            mood = detect_emotion(note)
        elif not mood:
            return jsonify({'error': 'Mood is required if no note is provided'}), 400
            
        # Get the date, default to today if not provided
        try:
            mood_date = data.get('date', date.today().isoformat())
            # Validate date format
            datetime.strptime(mood_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Create mood entry
        entry = MoodEntry(
            user_id=session.get('user_id'),
            date=mood_date,
            mood=mood,
            note=note
        )
        
        # Save to Firestore
        try:
            entry_id = mood_tracker.add_mood_entry(entry)
            
            return jsonify({
                'success': True,
                'entry_id': entry_id,
                'message': 'Mood logged successfully',
                'data': entry.to_dict(),
                'detected_mood': mood if not data.get('mood') else None
            }), 201
            
        except Exception as e:
            return jsonify({
                'error': 'Failed to save mood entry',
                'details': str(e)
            }), 500
            
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/mood_chart')
@firebase_required
def mood_chart():
    return render_template('mood_chart.html')

@app.route('/get_moods')
@firebase_required
def get_moods():
    try:
        # Get date range from query parameters, default to last 30 days
        end_date = date.today().isoformat()
        start_date = (datetime.now() - timedelta(days=30)).date().isoformat()
        
        # Get mood entries for the user
        entries = mood_tracker.get_user_mood_entries(
            user_id=session.get('user_id'),
            start_date=start_date,
            end_date=end_date
        )
        
        # Define mood colors and values
        mood_data = {
            'happy': {'value': 5, 'color': '#4CAF50'},  # Green
            'excited': {'value': 5, 'color': '#8BC34A'},  # Light Green
            'neutral': {'value': 3, 'color': '#FFC107'},  # Amber
            'anxious': {'value': 2, 'color': '#FF9800'},  # Orange
            'sad': {'value': 1, 'color': '#F44336'},  # Red
            'angry': {'value': 1, 'color': '#D32F2F'}   # Dark Red
        }
        
        # Format data for Chart.js
        chart_data = {
            'labels': [],  # dates
            'values': [],  # numeric mood values
            'notes': [],   # notes for tooltips
            'moods': [],   # original mood strings
            'colors': []   # colors for each data point
        }
        
        for entry in entries:
            mood_lower = entry.mood.lower()
            mood_info = mood_data.get(mood_lower, {'value': 3, 'color': '#9E9E9E'})  # Default gray
            
            chart_data['labels'].append(entry.date)
            chart_data['values'].append(mood_info['value'])
            chart_data['notes'].append(entry.note if entry.note else '')
            chart_data['moods'].append(entry.mood)
            chart_data['colors'].append(mood_info['color'])
        
        return jsonify(chart_data)
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch mood data',
            'details': str(e)
        }), 500

@app.route('/live-session')
def live_session():
    return render_template('live_session.html')

# Add helper function to log mood to mood tracker
def log_mood_to_tracker(user_id, detected_emotion, message=None):
    """
    Helper function to log detected emotions to the mood tracker
    """
    try:
        # Convert emotion to mood format
        mood_map = {
            'happy': 'happy',
            'excited': 'happy',
            'neutral': 'neutral',
            'anxious': 'anxious',
            'sad': 'sad',
            'angry': 'angry'
        }
        mood = mood_map.get(detected_emotion, 'neutral')
        
        # Create mood entry
        entry = MoodEntry(
            user_id=user_id,
            date=date.today().isoformat(),
            mood=mood,
            note=f"Auto-detected during therapy session: {message[:50]}..." if message else "Auto-detected during therapy session"
        )
        
        # Save to the mood tracker
        entry_id = mood_tracker.add_mood_entry(entry)
        print(f"Mood logged to tracker: {mood}, entry_id: {entry_id}")
        
        return entry_id
    except Exception as e:
        print(f"Error logging mood to tracker: {str(e)}")
        return None

@app.route('/api/chats/current/messages', methods=['POST'])
def process_live_session_message():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message'}), 400
        
        user_message = data['message']
        timestamp = int(time.time())
        
        # Get user ID from session
        user_id = session.get('user_id')
        if not user_id:
            # Create a temporary user ID if none exists in session
            user_id = f'temp_user_{str(uuid.uuid4())}'
            session['user_id'] = user_id
        
        # First check if this is a crisis message
        is_crisis = is_crisis_message(user_message)
        if is_crisis:
            print("CRISIS MESSAGE DETECTED in live session!")
            
            # Log the crisis message if database is available
            if db is not None:
                try:
                    db.collection('crisis_logs').add({
                        'user_id': user_id,
                        'message': user_message,
                        'timestamp': timestamp,
                        'session_type': 'live',
                        'detected_keywords': True
                    })
                except Exception as e:
                    print(f"Error logging crisis message: {str(e)}")
            
            # Define calming resources and grounding techniques
            calming_resources = get_calming_resources()
            
            # Select relevant emergency resources
            selected_emergency_resources = EMERGENCY_RESOURCES[:5]
            
            # Return a compassionate crisis response with resources
            return jsonify({
                'message': {
                    'text': get_crisis_response(),
                    'timestamp': timestamp
                },
                'detected_emotion': 'distressed',
                'wellness_score': 20,
                'is_crisis': True,
                'show_emergency': True,
                'emergency_resources': selected_emergency_resources,
                'resource_message': "Here are some resources that can provide immediate support:",
                'calming_resources': calming_resources,
                'calming_message': "While you seek help, here are some techniques that might help you feel more grounded:",
                'success': True
            })
        
        # If not a crisis, proceed with normal processing
        # Detect emotion from user message
        detected_emotion = detect_emotion(user_message)
        print(f"Live session message received. Detected emotion: {detected_emotion}")
        print(f"Message: {user_message[:50]}...")
        
        # Log emotion to mood tracker
        if detected_emotion != 'neutral':
            log_mood_to_tracker(user_id, detected_emotion, user_message)
        
        try:
            # Simple direct model creation
            model = genai.GenerativeModel(
                model_name="models/gemini-1.5-flash"
            )
            
            # Generate response with a simple prompt
            base_prompt = f"You are a compassionate AI therapist. The user is feeling {detected_emotion}. Respond with empathy in 2-3 sentences."
            
            prompt = f"{base_prompt}\n\nUser: {user_message}\nYour response:"
            print(f"Sending prompt to Gemini: {prompt[:50]}...")
            
            # Generate response
            response = model.generate_content(prompt)
            
            # Extract text safely
            ai_response = "I'm here to listen. Could you please share that again?"
            if response and hasattr(response, 'text'):
                ai_response = response.text.strip()
                print(f"AI response received: {ai_response[:50]}...")
            else:
                print("Warning: Empty or invalid response from Gemini API")
            
            # Generate a simple wellness score based on emotion
            wellness_score = {
                'happy': 85,
                'excited': 90,
                'neutral': 70,
                'anxious': 40,
                'sad': 30,
                'angry': 35
            }.get(detected_emotion, 60)
            
            # Set show_emergency flag if wellness score is low
            show_emergency = wellness_score < 40
            
            if show_emergency:
                print(f"Emergency flag triggered! Wellness score: {wellness_score}")
            
            # Store session data in Firebase if available
            if db is not None:
                try:
                    # Store session data in a live-sessions collection
                    session_data = {
                        'user_id': user_id,
                        'timestamp': timestamp,
                        'user_message': user_message,
                        'ai_response': ai_response,
                        'emotion': detected_emotion,
                        'is_crisis': is_crisis,
                        'wellness_score': wellness_score
                    }
                    
                    # Add to live-sessions collection
                    db.collection('live_sessions').add(session_data)
                    print("Live session data stored in Firebase")
                except Exception as db_error:
                    print(f"Error storing live session data: {str(db_error)}")
            
            return jsonify({
                'message': {
                    'text': ai_response,
                    'timestamp': timestamp
                },
                'detected_emotion': detected_emotion,
                'wellness_score': wellness_score,
                'is_crisis': False,
                'show_emergency': show_emergency,
                'success': True
            })
            
        except Exception as e:
            print(f"Error generating AI response: {str(e)}")
            return jsonify({
                'message': {
                    'text': "I'm here to listen. Could you please share that again?",
                    'timestamp': timestamp
                },
                'detected_emotion': detected_emotion,
                'error': str(e)
            })
            
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_affirmation')
@firebase_required
def get_daily_affirmation():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
            
        # Get the user's most recent mood from the mood tracker
        entries = mood_tracker.get_user_mood_entries(
            user_id=user_id,
            start_date=(datetime.now() - timedelta(days=1)).date().isoformat(),
            end_date=date.today().isoformat()
        )
        
        # Use the most recent mood, or default to 'neutral'
        current_mood = 'neutral'
        if entries:
            current_mood = entries[0].mood
            
        # Generate affirmation based on mood
        affirmation = get_affirmation(current_mood)
        
        return jsonify({
            'affirmation': affirmation,
            'mood': current_mood
        })
        
    except Exception as e:
        print(f"Error generating affirmation: {str(e)}")
        return jsonify({
            'error': 'Failed to generate affirmation',
            'details': str(e)
        }), 500

@app.route('/api/emergency-resources')
def get_emergency_resources():
    """Return the list of emergency resources with categories and tags"""
    try:
        # Return the emergency resources list with all metadata
        return jsonify(EMERGENCY_RESOURCES)
    except Exception as e:
        print(f"Error getting emergency resources: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve emergency resources',
            'details': str(e)
        }), 500

@app.route('/nearby_therapists')
def nearby_therapists_api():
    """
    API endpoint to return nearby therapists based on location
    """
    # Get parameters from the request
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    distance = request.args.get('distance', 10, type=int)
    specialty = request.args.get('specialty', 'all')
    insurance = request.args.get('insurance', 'all')
    availability = request.args.get('availability', 'any')
    
    # Validate required parameters
    if lat is None or lng is None:
        return jsonify({'error': 'Latitude and longitude are required'}), 400
    
    # In a real application, this would query a database of therapists
    # For this prototype, we'll generate mock data around the provided location
    
    # Generate mock data
    import random
    import math
    
    # List of possible specialties
    specialties = [
        'Anxiety & Depression', 
        'Relationship Counseling', 
        'Trauma & PTSD', 
        'Cognitive Behavioral Therapy',
        'Family Therapy',
        'Addiction Recovery',
        'Grief Counseling',
        'Child & Adolescent',
        'Eating Disorders',
        'Stress Management'
    ]
    
    # List of possible insurance providers
    insurances = [
        'Medicare',
        'Medicaid',
        'Blue Cross Blue Shield',
        'Aetna',
        'Cigna',
        'UnitedHealthcare',
        'Humana',
        'Kaiser Permanente',
        'Tricare',
        'Oscar Health'
    ]
    
    # List of possible streets
    streets = [
        'Main Street',
        'Oak Avenue',
        'Park Road',
        'Maple Drive',
        'Cedar Lane',
        'Elm Street',
        'Washington Avenue',
        'Pine Street',
        'Willow Way',
        'Highland Avenue'
    ]
    
    # Therapist descriptions
    descriptions = [
        "I specialize in providing compassionate therapy for individuals dealing with anxiety and depression. My approach combines cognitive behavioral techniques with mindfulness practices to help clients develop coping strategies and find peace.",
        "As a relationship counselor, I work with couples and individuals to improve communication, resolve conflicts, and rebuild trust. I create a safe space for honest dialogue and emotional growth.",
        "My practice focuses on trauma recovery using evidence-based approaches including EMDR and somatic experiencing. I help clients process difficult experiences and rebuild a sense of safety and empowerment.",
        "I offer CBT-focused therapy to help clients identify and change negative thought patterns. I work collaboratively with clients to develop practical skills for managing emotions and behaviors.",
        "With over 15 years of experience in family therapy, I help families improve communication, resolve conflicts, and strengthen relationships. I work with families of all structures and backgrounds.",
        "My approach combines cognitive-behavioral techniques with mindfulness practices to help clients manage stress and anxiety. I teach practical skills that can be applied to everyday situations."
    ]
    
    # Helper function to generate a random point within a certain radius
    def random_point_in_radius(center_lat, center_lng, radius_miles):
        # Earth's radius in miles
        earth_radius = 3958.8
        
        # Convert radius from miles to radians
        radius_radians = radius_miles / earth_radius
        
        # Random distance within radius
        random_distance = math.sqrt(random.random()) * radius_radians
        
        # Random angle
        random_angle = random.random() * 2 * math.pi
        
        # Calculate offset
        lat_offset = random_distance * math.sin(random_angle)
        lng_offset = random_distance * math.cos(random_angle)
        
        # Adjust for longitude scale
        lng_offset = lng_offset / math.cos(math.radians(center_lat))
        
        # Calculate new coordinates
        new_lat = center_lat + math.degrees(lat_offset)
        new_lng = center_lng + math.degrees(lng_offset)
        
        # Calculate distance from center point
        actual_distance = calculate_distance(center_lat, center_lng, new_lat, new_lng)
        
        return (new_lat, new_lng, actual_distance)
    
    # Helper function to calculate distance between two points
    def calculate_distance(lat1, lon1, lat2, lon2):
        # Convert degrees to radians
        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 3958.8  # Radius of earth in miles
        return c * r
    
    # Generate random therapists
    num_therapists = random.randint(5, 15)
    therapists = []
    
    for i in range(num_therapists):
        # Generate random point
        therapist_lat, therapist_lng, dist = random_point_in_radius(lat, lng, distance)
        
        # Generate random specialty
        therapist_specialty = random.choice(specialties)
        
        # Check if specialty filter applies
        if specialty != 'all' and specialty.lower() != therapist_specialty.lower().replace(' & ', '-').replace(' ', '-'):
            continue
        
        # Generate random insurances
        num_insurances = random.randint(2, 5)
        therapist_insurances = random.sample(insurances, num_insurances)
        
        # Check if insurance filter applies
        if insurance != 'all' and insurance not in [ins.lower().replace(' ', '-') for ins in therapist_insurances]:
            continue
        
        # Generate random availability
        accepting_new = random.choice([True, False, True])  # More likely to be accepting
        telehealth = random.choice([True, False])
        
        # Check if availability filter applies
        if availability == 'accepting' and not accepting_new:
            continue
        if availability == 'telehealth' and not telehealth:
            continue
        
        # Generate random address
        street_num = random.randint(100, 9999)
        street = random.choice(streets)
        
        # Generate random hours
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        hours = {}
        for day in days:
            if random.random() > 0.1:  # 90% chance of being open
                start_hour = random.randint(8, 10)
                end_hour = random.randint(16, 18)
                hours[day] = f"{start_hour}:00 AM - {end_hour}:00 PM"
            else:
                hours[day] = "Closed"
        
        # Weekend hours
        if random.random() > 0.7:  # 30% chance of Saturday hours
            start_hour = random.randint(9, 11)
            end_hour = random.randint(14, 16)
            hours['Saturday'] = f"{start_hour}:00 AM - {end_hour}:00 PM"
        else:
            hours['Saturday'] = "Closed"
        
        hours['Sunday'] = "Closed"
        
        # Check weekend hours filter
        if availability == 'weekend' and hours['Saturday'] == "Closed":
            continue
        
        # Generate phone number
        phone = f"({random.randint(100, 999)}) {random.randint(100, 999)}-{random.randint(1000, 9999)}"
        
        # Create therapist object
        therapist = {
            'id': f"t{i+1}",
            'name': f"Dr. {random.choice(['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'Robert', 'Lisa', 'James', 'Linda'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Jones', 'Brown', 'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor'])}",
            'specialty': therapist_specialty,
            'latitude': therapist_lat,
            'longitude': therapist_lng,
            'distance': dist,
            'address': f"{street_num} {street}, Your City, State",
            'phone': phone,
            'email': f"therapist{i+1}@example.com",
            'website': f"https://therapist{i+1}.example.com" if random.random() > 0.3 else None,
            'insurance': therapist_insurances,
            'accepting_new': accepting_new,
            'telehealth': telehealth,
            'hours': hours,
            'description': random.choice(descriptions)
        }
        
        therapists.append(therapist)
    
    # Sort therapists by distance
    therapists.sort(key=lambda x: x['distance'])
    
    return jsonify(therapists)

@app.route('/api/check-crisis', methods=['POST'])
@firebase_required
def check_crisis():
    """
    API endpoint to check if a message contains crisis indicators and return appropriate resources
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message'}), 400
            
        message = data['message']
        
        # Check if the message contains crisis indicators
        is_crisis = is_crisis_message(message)
        
        # If this is a crisis message, log it
        if is_crisis:
            user_id = session.get('user_id', 'anonymous')
            print(f"Crisis message detected from user {user_id}")
            
            # Log to database if available
            if db is not None:
                try:
                    db.collection('crisis_logs').add({
                        'user_id': user_id,
                        'message': message,
                        'timestamp': int(time.time()),
                        'detected_keywords': True
                    })
                except Exception as e:
                    print(f"Error logging crisis message: {str(e)}")
        
        # Return result with resources if it's a crisis
        return jsonify({
            'is_crisis': is_crisis,
            'resources': EMERGENCY_RESOURCES if is_crisis else [],
            'message': "Please consider reaching out to one of these resources for immediate support." if is_crisis else None
        })
        
    except Exception as e:
        print(f"Error checking crisis message: {str(e)}")
        return jsonify({
            'error': str(e),
            'is_crisis': False
        }), 500

@app.route('/get_response', methods=['POST'])
@firebase_required
def get_response():
    """
    Process user input, detect crisis messages, and generate appropriate responses.
    If a crisis is detected, skip the Gemini API call and return emergency resources.
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message'}), 400
            
        user_input = data['message']
        user_id = session.get('user_id', 'anonymous')
        timestamp = int(time.time())
        
        # First check if this is a crisis message
        crisis_detected = is_crisis_message(user_input)
        
        if crisis_detected:
            print(f"Crisis detected in message from user {user_id}")
            
            # Log the crisis message if database is available
            if db is not None:
                try:
                    db.collection('crisis_logs').add({
                        'user_id': user_id,
                        'message': user_input,
                        'timestamp': timestamp,
                        'detected_keywords': True
                    })
                except Exception as e:
                    print(f"Error logging crisis message: {str(e)}")
            
            # Define calming resources and grounding techniques
            calming_resources = get_calming_resources()
            
            # Select the most relevant emergency resources based on the message content
            # For simplicity, we're just taking the first 5, but you could implement more sophisticated selection
            selected_emergency_resources = EMERGENCY_RESOURCES[:5]
            
            # Return a static compassionate response with emergency resources and calming techniques
            static_response = {
                'text': get_crisis_response(),
                'is_crisis': True,
                'emergency_resources': selected_emergency_resources,
                'resource_message': "Here are some resources that can provide immediate support:",
                'calming_resources': calming_resources,
                'calming_message': "While you seek help, here are some techniques that might help you feel more grounded:",
                'timestamp': timestamp
            }
            
            return jsonify(static_response)
        
        # If not a crisis, proceed with normal response generation
        try:
            # Detect emotion
            detected_emotion = detect_emotion(user_input)
            
            # Create Gemini model
            model = genai.GenerativeModel(
                model_name="models/gemini-1.5-flash"
            )
            
            # Generate response
            prompt = f"You are a compassionate AI therapist. The user is feeling {detected_emotion}. Respond with empathy in 2-3 sentences.\n\nUser: {user_input}\nYour response:"
            response = model.generate_content(prompt)
            
            # Extract text safely
            ai_response = "I'm here to listen. Could you please share more about what you're experiencing?"
            if response and hasattr(response, 'text'):
                ai_response = response.text.strip()
            
            return jsonify({
                'text': ai_response,
                'is_crisis': False,
                'detected_emotion': detected_emotion,
                'timestamp': timestamp
            })
            
        except Exception as e:
            print(f"Error generating AI response: {str(e)}")
            return jsonify({
                'text': "I'm here to listen. Could you please share more about what you're experiencing?",
                'is_crisis': False,
                'error': str(e),
                'timestamp': timestamp
            })
            
    except Exception as e:
        print(f"Error in get_response: {str(e)}")
        return jsonify({
            'error': str(e),
            'text': "I apologize, but I'm having trouble processing your message right now. Please try again."
        }), 500

@app.route('/find-therapists')
@firebase_required
def find_therapists_page():
    """
    Render the specialized page for finding nearby therapists
    """
    # Get Google Maps API key from environment variables
    # Hardcoded for testing - remove before production
    # google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    google_maps_api_key = "AIzaSyBu60Y-R7XrkTJF-YDkLsSvkMZMxnuueOw"
    
    # Debug: Check if API key is loaded
    print(f"DEBUG - Google Maps API Key available: {bool(google_maps_api_key)}")
    if not google_maps_api_key:
        print("WARNING: Google Maps API key is missing or empty")
    
    return render_template('nearby_therapists.html', google_maps_api_key=google_maps_api_key)

def generate_bengaluru_therapist_data():
    """Generate sample therapist data for Bengaluru."""
    # Bengaluru coordinates
    bengaluru_lat = 12.9716
    bengaluru_lng = 77.5946
    
    specialties = [
        'Anxiety', 'Depression', 'Trauma & PTSD', 'Couples Therapy', 
        'Addiction', 'Child Therapy', 'Grief', 'Stress Management'
    ]
    
    # Bengaluru-specific areas
    areas = [
        'Indiranagar', 'Koramangala', 'Whitefield', 'HSR Layout', 
        'JP Nagar', 'Jayanagar', 'Malleshwaram', 'Bannerghatta Road',
        'MG Road', 'Electronic City', 'Marathahalli', 'Bellandur'
    ]
    
    # Indian names
    first_names = [
        'Anil', 'Priya', 'Rahul', 'Ananya', 'Vikram', 'Meera', 
        'Arjun', 'Deepika', 'Sanjay', 'Divya', 'Rajesh', 'Kavita'
    ]
    
    last_names = [
        'Sharma', 'Patel', 'Verma', 'Gupta', 'Singh', 'Kumar',
        'Rao', 'Reddy', 'Nair', 'Menon', 'Iyer', 'Joshi'
    ]
    
    results = []
    
    for i in range(12):
        # Random coordinates around Bengaluru
        random_lat = bengaluru_lat + (random.random() - 0.5) * 0.08
        random_lng = bengaluru_lng + (random.random() - 0.5) * 0.08
        
        # Calculate distance from Bengaluru center
        distance = calculate_distance(bengaluru_lat, bengaluru_lng, random_lat, random_lng)
        
        # Random specialty
        place_specialty = random.choice(specialties)
        
        # Random area in Bengaluru
        area = random.choice(areas)
        
        # Random name
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        
        # Random credentials
        credentials = random.choice(['MD', 'PhD', 'LMFT', 'PsyD', 'MSW', 'MBBS'])
        
        name = f"Dr. {first_name} {last_name}, {credentials}"
        
        # Create a therapist object
        place = {
            'place_id': f'bengaluru-{i}',
            'name': name,
            'geometry': {
                'location': {
                    'lat': random_lat,
                    'lng': random_lng
                }
            },
            'vicinity': f"{random.randint(100, 999)} {area} Main Road, {area}, Bengaluru",
            'formatted_address': f"{random.randint(100, 999)} {area} Main Road, {area}, Bengaluru, Karnataka 560001, India",
            'rating': round(3.5 + random.random() * 1.5, 1),
            'user_ratings_total': random.randint(5, 50),
            'types': ['health', 'doctor', 'point_of_interest', 'establishment'],
            'formatted_phone_number': f"+91 {random.randint(7000000000, 9999999999)}",
            'website': f"https://example.com/therapist-bengaluru-{i}",
            'reviews': generate_bengaluru_reviews(),
            'specialty': place_specialty
        }
        
        results.append(place)
    
    # Sort by distance
    results.sort(key=lambda x: calculate_distance(
        bengaluru_lat, bengaluru_lng, 
        x['geometry']['location']['lat'], 
        x['geometry']['location']['lng']
    ))
    
    return {'results': results}

def generate_bengaluru_reviews():
    """Generate sample reviews for Bengaluru therapists."""
    review_texts = [
        "Dr. X helped me overcome my anxiety with practical exercises and compassionate care. Highly recommend!",
        "I've been seeing Dr. X for six months now and my mental health has improved significantly.",
        "Very professional and attentive. I felt comfortable from our first session.",
        "Excellent therapist who creates a safe space for healing. The office in Bengaluru is also very peaceful.",
        "Dr. X has helped me develop coping mechanisms for my stress. The location is convenient in Bengaluru.",
        "Great experience with Dr. X. Their approach is both scientific and compassionate."
    ]
    
    authors = ['Amit', 'Priya', 'Ravi', 'Neha', 'Kiran', 'Anjali', 'Deepak', 'Shalini']
    
    reviews = []
    for _ in range(random.randint(2, 5)):
        review = {
            'author_name': random.choice(authors),
            'rating': random.randint(3, 5),
            'relative_time_description': f"{random.randint(1, 11)} months ago",
            'text': random.choice(review_texts).replace('Dr. X', 'this therapist')
        }
        reviews.append(review)
    
    return reviews

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two points in miles."""
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 3956  # Radius of Earth in miles
    
    return round(c * r, 1)

@app.route('/api/nearby-therapists')
def google_nearby_therapists_api():
    """Proxy endpoint to fetch therapists from Google Places API."""
    # Get parameters from request
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    specialty = request.args.get('specialty', '')
    
    print(f"DEBUG - Nearby therapists API called with lat={lat}, lng={lng}, specialty={specialty}")
    print("DEBUG - Returning Bengaluru therapists regardless of location")
    
    # Generate Bengaluru therapist data
    bengaluru_data = generate_bengaluru_therapist_data()
    
    # If specialty is specified, filter the results
    if specialty and specialty != 'all' and specialty != '':
        print(f"DEBUG - Filtering by specialty: {specialty}")
        filtered_results = []
        for therapist in bengaluru_data['results']:
            if specialty.lower() in therapist.get('specialty', '').lower():
                filtered_results.append(therapist)
        
        # If no results after filtering, return all results
        if filtered_results:
            bengaluru_data['results'] = filtered_results
    
    return jsonify(bengaluru_data)

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 3001))
    
    # Run app with host set to 0.0.0.0 to be accessible from the outside
    app.run(host='0.0.0.0', port=port, debug=True) 