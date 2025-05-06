from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import google.generativeai as genai
import os
import time
import random
import uuid
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from functools import wraps
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Load environment variables
load_dotenv()

# Configure Gemini API
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDFgqb56dp44rR5oM7CKxxuwJIEN-bfHs8")
genai.configure(api_key=API_KEY)

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
    return render_template('sign-in.html')

@app.route('/sign-up')
def sign_up():
    # Allow access regardless of authentication status
    # The client-side JS will handle redirecting authenticated users
    return render_template('sign-up.html')

# Main routes
@app.route('/')
@firebase_required
def index():
    return render_template('index.html')

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
        "description": "24/7, free and confidential support for people in distress"
    },
    {
        "name": "Crisis Text Line",
        "contact": "Text HOME to 741741",
        "description": "Free 24/7 support from trained crisis counselors"
    },
    {
        "name": "SAMHSA's National Helpline",
        "contact": "1-800-662-4357",
        "description": "Treatment referral and information service (24/7)"
    },
    {
        "name": "National Domestic Violence Hotline",
        "contact": "1-800-799-7233",
        "description": "24/7 support, resources, and advice for safety"
    },
    {
        "name": "Trevor Project (LGBTQ+)",
        "contact": "1-866-488-7386",
        "description": "Crisis intervention and suicide prevention for LGBTQ+ youth"
    },
    {
        "name": "Veterans Crisis Line",
        "contact": "988, Press 1 or text 838255",
        "description": "Connects veterans with qualified responders"
    },
    {
        "name": "IMAlive",
        "contact": "www.imalive.org",
        "description": "Virtual crisis center with 24/7 chat support"
    }
]

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
        
        # Create user message object
        user_message_obj = {
            'sender': 'user',
            'text': user_message,
            'timestamp': timestamp
        }
        
        # If Firestore is available, use it
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
            
            # Update title if it's the first user message and has meaningful content
            if len([m for m in messages if m['sender'] == 'user']) == 1 and len(user_message) > 3:
                # Use first few words of user message as title
                chat_data['title'] = ' '.join(user_message.split()[:5])
                if len(chat_data['title']) > 30:
                    chat_data['title'] = chat_data['title'][:27] + '...'
            
            # Get recent messages for context
            recent_messages = messages[-5:] if len(messages) > 5 else messages
            
            # Analyze sentiment for mood
            sentiment_result = analyze_sentiment_internal(user_message, recent_messages)
            current_mood = sentiment_result.get('mood', 'neutral')
            is_emergency = sentiment_result.get('emergency', False)
            
            # Generate AI response
            therapeutic_prompt = BASE_THERAPEUTIC_PROMPT + MOOD_PROMPTS[current_mood]
            
            # Add emergency content to the prompt if needed
            if is_emergency:
                therapeutic_prompt += """
                IMPORTANT: This appears to be a crisis situation that requires immediate attention.
                
                Your response MUST:
                - Express genuine concern for their wellbeing with warmth and compassion
                - Explicitly acknowledge their pain without minimizing it
                - Emphasize that they are not alone and that help is available
                - State clearly that difficult feelings are temporary and can improve with support
                - Encourage them to reach out to a crisis resource right away
                - Mention specific resources like the 988 Suicide & Crisis Lifeline or Crisis Text Line
                - Use a calm, supportive tone that conveys hope without being dismissive
                - Avoid platitudes like "it will get better" without acknowledging their current pain
                
                Remember that your response could be critical in helping someone in distress connect with professional help.
                """
            
            # Generate response using Gemini
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 0,
                "max_output_tokens": 1024,
            }
            
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
            
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Include conversation history in the prompt
            message_history = "\n".join([f"{'User' if msg['sender'] == 'user' else 'AI'}: {msg['text']}" for msg in recent_messages[:-1]])
            conversation_context = f"Recent conversation:\n{message_history}\n\n" if message_history else ""
            
            # Combine prompt with conversation context and user message
            prompt = f"{therapeutic_prompt}\n\n{conversation_context}User: {user_message}"
            response = model.generate_content(prompt)
            
            # Get response timestamp
            response_timestamp = int(time.time())
            
            # Create bot message object
            bot_message_obj = {
                'sender': 'bot',
                'text': response.text,
                'timestamp': response_timestamp
            }
            
            # Add bot message to messages
            messages.append(bot_message_obj)
            
            # Update chat data
            chat_data['messages'] = messages
            chat_data['updated_at'] = response_timestamp
            
            # Update chat document in Firestore
            chat_ref.set(chat_data)
            
            return jsonify({
                'message': bot_message_obj,
                'detected_mood': current_mood,
                'is_emergency': is_emergency,
                'resources': EMERGENCY_RESOURCES if is_emergency else []
            })
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
            
            # Update title if it's the first user message and has meaningful content
            if len([m for m in chat_data['messages'] if m['sender'] == 'user']) == 1 and len(user_message) > 3:
                # Use first few words of user message as title
                chat_data['title'] = ' '.join(user_message.split()[:5])
                if len(chat_data['title']) > 30:
                    chat_data['title'] = chat_data['title'][:27] + '...'
            
            # Get recent messages for context
            recent_messages = chat_data['messages'][-5:] if len(chat_data['messages']) > 5 else chat_data['messages']
            
            # Analyze sentiment for mood
            sentiment_result = analyze_sentiment_internal(user_message, recent_messages)
            current_mood = sentiment_result.get('mood', 'neutral')
            is_emergency = sentiment_result.get('emergency', False)
            
            # Generate AI response using our existing logic
            therapeutic_prompt = BASE_THERAPEUTIC_PROMPT + MOOD_PROMPTS[current_mood]
            
            # Add emergency content to the prompt if needed
            if is_emergency:
                therapeutic_prompt += """
                IMPORTANT: This appears to be a crisis situation that requires immediate attention.
                
                Your response MUST:
                - Express genuine concern for their wellbeing with warmth and compassion
                - Explicitly acknowledge their pain without minimizing it
                - Emphasize that they are not alone and that help is available
                - State clearly that difficult feelings are temporary and can improve with support
                - Encourage them to reach out to a crisis resource right away
                - Mention specific resources like the 988 Suicide & Crisis Lifeline or Crisis Text Line
                - Use a calm, supportive tone that conveys hope without being dismissive
                - Avoid platitudes like "it will get better" without acknowledging their current pain
                
                Remember that your response could be critical in helping someone in distress connect with professional help.
                """
            
            # Generate response using Gemini
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 0,
                "max_output_tokens": 1024,
            }
            
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
            
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Include conversation history in the prompt
            message_history = "\n".join([f"{'User' if msg['sender'] == 'user' else 'AI'}: {msg['text']}" for msg in recent_messages[:-1]])
            conversation_context = f"Recent conversation:\n{message_history}\n\n" if message_history else ""
            
            # Combine prompt with conversation context and user message
            prompt = f"{therapeutic_prompt}\n\n{conversation_context}User: {user_message}"
            response = model.generate_content(prompt)
            
            # Get response timestamp
            response_timestamp = int(time.time())
            
            # Add AI response to chat
            chat_data['messages'].append({
                'sender': 'bot',
                'text': response.text,
                'timestamp': response_timestamp
            })
            
            # Update chat's updated_at timestamp
            chat_data['updated_at'] = response_timestamp
            
            return jsonify({
                'message': {
                    'sender': 'bot',
                    'text': response.text,
                    'timestamp': response_timestamp
                },
                'detected_mood': current_mood,
                'is_emergency': is_emergency,
                'resources': EMERGENCY_RESOURCES if is_emergency else []
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Internal function for sentiment analysis (not exposed as an endpoint)
def analyze_sentiment_internal(message, chat_history=None):
    try:
        # Combine recent messages for context if available
        context = ""
        if chat_history:
            context = "\n".join([f"{'User' if msg['sender'] == 'user' else 'AI'}: {msg['text']}" for msg in chat_history])
            context = f"Recent conversation:\n{context}\n\n"
        
        # Improved prompt for sentiment analysis with stronger emphasis on detecting crisis situations
        sentiment_prompt = f"""
        You are a mental health professional specializing in crisis detection. Analyze the following message to determine the user's emotional state.

        CRITICAL: Pay very close attention to signals of distress, depression, suicidal ideation, self-harm, or crisis. Look for phrases like:
        - "I want to kill myself", "kms", "end it all", "don't want to live", "life isn't worth living"
        - "I'm depressed", "can't go on", "giving up", "no hope", "no reason to live"
        - "I'm going to hurt myself", "cut myself", "harm myself"
        - Any mention of suicide, death wishes, or plans to harm oneself
        - Extreme feelings of despair, hopelessness, or worthlessness

        If ANY of these signals are present, even if subtle or abbreviated, classify as an emergency (true).
        
        For mood classification, choose the MOST appropriate from: happy, sad, anxious, angry, or neutral.
        - If the message contains any crisis signals, the mood should NOT be neutral.
        - Depression or hopelessness should be classified as "sad"
        - Panic, worry, or fear should be classified as "anxious"
        - Frustration, rage, or irritation should be classified as "angry"
        - Joy, excitement, or gratitude should be classified as "happy"
        
        {context}
        Current message: {message}
        
        Return your analysis in the following JSON format without any additional text or explanations:
        {{
            "mood": "detected_mood",
            "emergency": true_or_false
        }}
        """
        
        # Generate the sentiment analysis - use temperature=0 for consistent outputs
        sentiment_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.0,
                "top_p": 0.95,
                "top_k": 0,
                "max_output_tokens": 256,
            }
        )
        
        sentiment_response = sentiment_model.generate_content(sentiment_prompt)
        
        try:
            # Parse the analysis result
            result = json.loads(sentiment_response.text)
            return result
        except:
            # Fallback to text-based detection if JSON parsing fails
            lowerMessage = message.lower()
            crisisKeywords = ['suicide', 'kill myself', 'kms', 'end it all', 'want to die', 'don\'t want to live', 'self harm', 'hurt myself']
            isEmergency = any(keyword in lowerMessage for keyword in crisisKeywords)
            
            return {
                'mood': 'sad' if isEmergency else 'neutral',
                'emergency': isEmergency
            }
    
    except Exception as e:
        # Default response if something goes wrong
        return {
            'mood': 'neutral',
            'emergency': False
        }

@app.route('/chat', methods=['POST'])
@firebase_required
def chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message'}), 400
        
        user_message = data['message']
        chat_history = data.get('chat_history', [])
        
        # Use the detected mood from sentiment analysis
        user_mood = data.get('detected_mood', 'neutral')
        is_emergency = data.get('is_emergency', False)
        
        # Ensure mood is valid
        if user_mood not in MOOD_PROMPTS:
            user_mood = 'neutral'
        
        # Combine base prompt with mood-specific prompt
        therapeutic_prompt = BASE_THERAPEUTIC_PROMPT + MOOD_PROMPTS[user_mood]
        
        # Add emergency content to the prompt if needed - enhanced for crisis response
        if is_emergency:
            therapeutic_prompt += """
            IMPORTANT: This appears to be a crisis situation that requires immediate attention.
            
            Your response MUST:
            - Express genuine concern for their wellbeing with warmth and compassion
            - Explicitly acknowledge their pain without minimizing it
            - Emphasize that they are not alone and that help is available
            - State clearly that difficult feelings are temporary and can improve with support
            - Encourage them to reach out to a crisis resource right away
            - Mention specific resources like the 988 Suicide & Crisis Lifeline or Crisis Text Line
            - Use a calm, supportive tone that conveys hope without being dismissive
            - Avoid platitudes like "it will get better" without acknowledging their current pain
            
            Remember that your response could be critical in helping someone in distress connect with professional help.
            """
        
        # Generate response using Gemini Pro with therapeutic prompt
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 0,
            "max_output_tokens": 1024,
        }
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Include conversation history in the prompt if available
        conversation_context = ""
        if chat_history:
            # Include up to last 5 messages for context
            recent_messages = chat_history[-5:]
            conversation_context = "\n".join([f"{'User' if msg['sender'] == 'user' else 'AI'}: {msg['text']}" for msg in recent_messages])
            conversation_context = f"Recent conversation:\n{conversation_context}\n\n"
        
        # Combine prompt with conversation context and user message
        prompt = f"{therapeutic_prompt}\n\n{conversation_context}User: {user_message}"
        response = model.generate_content(prompt)
        
        # Return the response as JSON
        return jsonify({
            'response': response.text,
            'detected_mood': user_mood,
            'is_emergency': is_emergency,
            'resources': EMERGENCY_RESOURCES if is_emergency else []
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        
        # Select a random prompt from the list
        selected_prompt = random.choice(QUOTE_PROMPTS)
        
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
            model_name="gemini-1.5-flash",
            generation_config=generation_config
        )
        
        response = model.generate_content(prompt_with_timestamp)
        
        # Format the quote (remove extra quotes if present)
        quote_text = response.text.strip()
        if quote_text.startswith('"') and quote_text.endswith('"'):
            quote_text = quote_text[1:-1]
        
        # Create quote object
        quote_data = {
            'text': quote_text,
            'created_at': current_timestamp
        }
        
        # Store the quote in Firestore if available
        if db is not None:
            # Add a new quote document with auto-generated ID
            quotes_ref = db.collection('users').document(user_id).collection('quotes')
            _, quote_ref = quotes_ref.add(quote_data)
            
            # Include the document ID in the response
            quote_data['id'] = quote_ref.id
        
        # Return the quote as JSON
        return jsonify(quote_data)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/quotes', methods=['GET'])
@firebase_required
def get_quotes():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Use Firestore if available
        if db is not None:
            # Get all quotes for the user
            quotes_ref = db.collection('users').document(user_id).collection('quotes')
            quote_docs = quotes_ref.order_by('created_at', direction=firestore.Query.DESCENDING).stream()
            
            quotes = []
            for doc in quote_docs:
                quote_data = doc.to_dict()
                quote_data['id'] = doc.id  # Add document ID as quote ID
                quotes.append(quote_data)
                
            return jsonify(quotes)
        else:
            # If Firestore is not available, return empty list
            # In a complete implementation, we could store quotes locally too
            return jsonify([])
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

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 3000))
    
    # Run app with host set to 0.0.0.0 to be accessible from the outside
    app.run(host='0.0.0.0', port=port, debug=True) 