# Firebase Database Setup Guide

This guide will help you set up Firebase for your AI Therapist application. Follow these steps to get your database connected.

## Step 1: Create a Firebase Project (if you haven't already)

1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" and follow the setup wizard
3. Give your project a name (e.g., "AI Therapist")
4. Enable Google Analytics if desired (optional)
5. Create the project

## Step 2: Set Up Firebase Authentication

1. In your Firebase project, navigate to "Authentication" in the left sidebar
2. Click "Get started"
3. Enable the authentication methods you want to use:
   - Email/Password (required for basic authentication)
   - Google (recommended for easier sign-in)
   - Other providers as needed
4. Configure each provider according to Firebase's instructions

## Step 3: Create a Firestore Database

1. In your Firebase project, navigate to "Firestore Database" in the left sidebar
2. Click "Create database"
3. Choose either "Start in production mode" or "Start in test mode"
   - For development, you can start in test mode
   - For production, start in production mode and set up security rules later
4. Select a location for your database (choose one closest to your users)
5. Click "Enable"

## Step 4: Get Your Firebase Admin SDK Credentials

1. In the Firebase Console, go to Project Settings > Service Accounts
2. Click "Generate new private key"
3. Download the JSON file
4. Store this file securely - DO NOT commit it to your repository

## Step 5: Provide Credentials to the AI Therapist App

You have two options to provide your Firebase credentials to the application:

### Option 1: Use a credentials file (recommended for local development)

1. Save your downloaded Firebase service account JSON file to a secure location
2. Set the following environment variable in your `.env` file:

```
FIREBASE_CREDENTIALS_PATH=/path/to/your-firebase-credentials.json
```

### Option 2: Use environment variable with JSON content

1. Open the downloaded service account JSON file
2. Copy the entire JSON content
3. Set it as an environment variable in your `.env` file:

```
FIREBASE_CREDENTIALS='{"type":"service_account","project_id":"your-project-id","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}'
```

Note: Be careful with quotes and special characters when setting this variable.

## Step 6: Update Frontend Configuration

1. In the Firebase Console, go to Project Overview > Project Settings
2. In the "Your apps" section, find or create a web app
3. Copy the Firebase configuration object
4. Update this configuration in the following files:
   - `templates/sign-in.html`
   - `templates/sign-up.html`
   - `templates/index.html`

Replace the existing configuration with your own:

```javascript
const firebaseConfig = {
    apiKey: "YOUR_FIREBASE_API_KEY",
    authDomain: "YOUR_FIREBASE_AUTH_DOMAIN",
    projectId: "YOUR_FIREBASE_PROJECT_ID",
    storageBucket: "YOUR_FIREBASE_STORAGE_BUCKET",
    messagingSenderId: "YOUR_FIREBASE_MESSAGING_SENDER_ID",
    appId: "YOUR_FIREBASE_APP_ID"
};
```

## Step 7: Testing Your Setup

1. Start your Flask application
2. Sign up for a new account
3. Login should now use Firebase authentication
4. Add some chat messages to test that Firestore is storing your data
5. Check the Firebase Console to ensure data is being saved correctly

## Troubleshooting

- If you get authentication errors, check that your credentials file is correctly formatted and the path is correct
- If data isn't being saved, verify that your Firestore rules allow write access
- Check the application logs for specific error messages related to Firebase

## Security Considerations

- Never expose your Firebase service account key in client-side code
- Use Firebase Security Rules to protect your Firestore data
- For production, set up proper authentication rules in Firestore 