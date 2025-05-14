import os
from dotenv import load_dotenv

def test_env_variables():
    # Load environment variables
    load_dotenv()
    
    # Check for Google Maps API key
    google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY')
    google_places_key = os.getenv('GOOGLE_PLACES_API_KEY')
    
    print(f"Google Maps API Key: {'✓ Found' if google_maps_key else '✗ Missing'}")
    if google_maps_key:
        print(f"Key length: {len(google_maps_key)} characters")
        # Print first and last 4 characters for verification
        print(f"Key prefix: {google_maps_key[:4]}...")
        print(f"Key suffix: ...{google_maps_key[-4:]}")
    
    print(f"Google Places API Key: {'✓ Found' if google_places_key else '✗ Missing'}")
    if google_places_key:
        print(f"Key length: {len(google_places_key)} characters")
        print(f"Key prefix: {google_places_key[:4]}...")
        print(f"Key suffix: ...{google_places_key[-4:]}")
    
    # Check for other required API keys
    firebase_key = os.getenv('FIREBASE_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    
    print(f"Firebase API Key: {'✓ Found' if firebase_key else '✗ Missing'}")
    print(f"Gemini API Key: {'✓ Found' if gemini_key else '✗ Missing'}")
    
    # Check for direct environment variable access (not via python-dotenv)
    google_maps_env = os.environ.get('GOOGLE_MAPS_API_KEY')
    print(f"Google Maps API Key via os.environ: {'✓ Found' if google_maps_env else '✗ Missing'}")
    
    # Suggest solutions based on findings
    if not google_maps_key:
        print("\nPossible solutions:")
        print("1. Create a .env file in the project root with GOOGLE_MAPS_API_KEY=your_api_key")
        print("2. Set the environment variable directly: export GOOGLE_MAPS_API_KEY=your_api_key")
        print("3. Hardcode the API key in app.py for testing (remove before production)")

if __name__ == "__main__":
    test_env_variables() 