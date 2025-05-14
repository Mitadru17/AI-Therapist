import os
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

# Configure Gemini API
API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=API_KEY)

# Define generation parameters
generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 100,
}

# Emotion-specific prompts for better context
EMOTION_PROMPTS = {
    "happy": "Create an affirmation that celebrates and reinforces positive feelings",
    "sad": "Create a gentle, uplifting affirmation that acknowledges pain while offering hope",
    "anxious": "Create a grounding, calming affirmation that promotes peace and safety",
    "angry": "Create an empowering affirmation that acknowledges feelings while promoting constructive energy",
    "neutral": "Create a balanced, mindful affirmation that promotes self-awareness",
    "excited": "Create an affirmation that channels enthusiasm into positive focus",
    "stressed": "Create a soothing affirmation that promotes relaxation and perspective",
    "tired": "Create an affirmation that acknowledges the need for rest while maintaining hope",
    "overwhelmed": "Create an affirmation that simplifies and brings focus to the present moment",
    "confident": "Create an affirmation that reinforces self-belief and capability"
}

def generate_affirmation(emotion: str) -> Optional[str]:
    """
    Generates a personalized affirmation based on the detected emotion using Gemini API.
    
    Args:
        emotion (str): The detected emotion (e.g., 'sad', 'happy', 'anxious')
        
    Returns:
        str: A personalized affirmation string, or None if generation fails
    """
    try:
        # Normalize emotion to lowercase and get appropriate prompt
        emotion = emotion.lower()
        emotion_prompt = EMOTION_PROMPTS.get(emotion, EMOTION_PROMPTS["neutral"])
        
        # Construct the full prompt
        prompt = f"""As an empathetic AI therapist, {emotion_prompt}.
        The affirmation should be:
        - Short (one sentence, max 100 characters)
        - Personal (using "I" or "my")
        - Present tense
        - Positive and empowering
        - Specific to someone feeling {emotion}
        
        Return only the affirmation text, nothing else."""
        
        # Create Gemini model with appropriate configuration
        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash",
            generation_config=generation_config
        )
        
        # Generate the affirmation
        response = model.generate_content(prompt)
        
        # Extract and clean the affirmation
        if response and hasattr(response, 'text'):
            affirmation = response.text.strip()
            # Remove quotes if present
            affirmation = affirmation.strip('"\'')
            return affirmation
            
        return None
        
    except Exception as e:
        print(f"Error generating affirmation: {str(e)}")
        return None

# Default affirmations as fallback
DEFAULT_AFFIRMATIONS = {
    "happy": "I embrace and celebrate the joy in my life.",
    "sad": "I acknowledge my feelings and trust that better days are ahead.",
    "anxious": "I am safe, grounded, and capable of handling this moment.",
    "angry": "I channel my energy into positive change and growth.",
    "neutral": "I am present and mindful in this moment.",
    "excited": "I direct my enthusiasm into meaningful actions.",
    "stressed": "I breathe deeply and release what I cannot control.",
    "tired": "I honor my need for rest and renewal.",
    "overwhelmed": "I take one step at a time with clarity and purpose.",
    "confident": "I trust in my abilities and inner strength."
}

def get_affirmation(emotion: str) -> str:
    """
    Gets an affirmation for the given emotion, falling back to defaults if generation fails.
    
    Args:
        emotion (str): The detected emotion
        
    Returns:
        str: An affirmation string
    """
    # Try to generate a custom affirmation
    affirmation = generate_affirmation(emotion)
    
    # Fall back to default if generation fails
    if not affirmation:
        return DEFAULT_AFFIRMATIONS.get(
            emotion.lower(),
            "I am worthy of love, respect, and positive energy."
        )
    
    return affirmation 