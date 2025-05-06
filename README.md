# AI Therapist Application

A Flask-based AI therapy application using Google's Gemini API for natural language conversations and Firebase for authentication and data storage.

## Features

- 🧠 AI-powered therapeutic conversations with mood detection
- 🔒 Firebase authentication (email/password and Google sign-in)
- 💬 Chat history stored in Firebase Firestore
- 📝 Inspirational quotes collection
- 🆘 Emergency resources for crisis situations
- 📱 Responsive design for mobile and desktop

## Prerequisites

- Python 3.8+
- Firebase project with authentication and Firestore database
- Google Gemini API key

## Installation

1. Clone the repository
2. Install dependencies
   ```
   pip install -r requirements.txt
   ```
3. Set up Firebase (see [Firebase Setup Guide](firebase_setup.md))
4. Create a `.env` file with the following variables:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   SECRET_KEY=your_flask_secret_key
   PORT=3001
   
   # Choose one of these methods for Firebase credentials:
   FIREBASE_CREDENTIALS_PATH=/path/to/your-firebase-credentials.json
   # or
   FIREBASE_CREDENTIALS={"type":"service_account","project_id":"your-project-id",...}
   ```

## Running the Application

Run the Flask application:
```
python app.py
```

The application will be available at `http://localhost:3001`

## Development Mode

If you don't have Firebase credentials available, the application will automatically use an in-memory database for development purposes. This allows you to test the application without setting up Firebase.

## Project Structure

- `app.py` - Main Flask application
- `templates/` - HTML templates for the web interface
  - `index.html` - Main application interface
  - `sign-in.html` - User sign-in page
  - `sign-up.html` - User registration page
- `static/` - Static files (CSS, JS, images)
- `firebase_setup.md` - Guide for setting up Firebase

## Firebase Integration

The application uses Firebase for:
1. User authentication
2. Storing chat history
3. Saving inspirational quotes

For detailed setup instructions, see the [Firebase Setup Guide](firebase_setup.md).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 