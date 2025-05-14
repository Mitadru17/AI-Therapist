from transformers import pipeline
from functools import lru_cache
import torch

# Map HuggingFace emotions to our mood categories
EMOTION_TO_MOOD = {
    'joy': 'happy',
    'surprise': 'excited',
    'neutral': 'neutral',
    'fear': 'anxious',
    'sadness': 'sad',
    'anger': 'angry',
    'disgust': 'angry'
}

@lru_cache(maxsize=1)
def get_emotion_pipeline():
    """
    Creates and caches the emotion detection pipeline.
    Uses LRU cache to ensure we only load the model once.
    """
    return pipeline(
        "text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        top_k=1
    )

def detect_emotion(text: str) -> str:
    """
    Detects the primary emotion in the given text using the Hugging Face model.
    
    Args:
        text (str): The text to analyze
        
    Returns:
        str: The detected mood (mapped from the emotion)
    """
    try:
        # Get the emotion pipeline
        classifier = get_emotion_pipeline()
        
        # Ensure text is not empty and is a string
        if not text or not isinstance(text, str):
            return 'neutral'
            
        # Truncate text if it's too long (model has a token limit)
        text = text[:512]
        
        # Get emotion prediction
        result = classifier(text)
        
        # Extract the top emotion
        emotion = result[0][0]['label']
        
        # Map the emotion to our mood categories
        mood = EMOTION_TO_MOOD.get(emotion, 'neutral')
        
        return mood
        
    except Exception as e:
        print(f"Error in emotion detection: {str(e)}")
        return 'neutral'  # Default to neutral on error

def batch_detect_emotions(texts: list[str]) -> list[str]:
    """
    Detects emotions for multiple texts in batch.
    
    Args:
        texts (list[str]): List of texts to analyze
        
    Returns:
        list[str]: List of detected moods
    """
    try:
        # Get the emotion pipeline
        classifier = get_emotion_pipeline()
        
        # Filter out empty texts and truncate long ones
        valid_texts = [text[:512] for text in texts if text and isinstance(text, str)]
        
        if not valid_texts:
            return ['neutral'] * len(texts)
        
        # Get predictions for all texts
        results = classifier(valid_texts)
        
        # Map emotions to moods
        moods = [
            EMOTION_TO_MOOD.get(result[0]['label'], 'neutral')
            for result in results
        ]
        
        return moods
        
    except Exception as e:
        print(f"Error in batch emotion detection: {str(e)}")
        return ['neutral'] * len(texts)  # Default to neutral on error 