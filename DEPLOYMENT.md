# Deployment Guide for AI Therapist

This guide will help you deploy the AI Therapist application on either Render or Replit.

## Deploying on Render

Render is a cloud platform that makes it easy to deploy web services.

### Prerequisites

- A GitHub account
- Your code pushed to a GitHub repository
- A Render account (sign up at [render.com](https://render.com))

### Step-by-Step Deployment

1. **Push your code to GitHub**
   - Make sure all the files are committed and pushed to your repository
   - Ensure the repository includes `requirements.txt`, `gunicorn.conf.py`, and `render.yaml`

2. **Sign up for Render**
   - Go to [render.com](https://render.com) and sign up using your GitHub account
   - Authorize Render to access your repositories

3. **Create a New Web Service**
   - From your Render dashboard, click "New" and select "Web Service"
   - Find and select your GitHub repository
   - If prompted, select the option to use the `render.yaml` configuration

4. **Configure Your Web Service**
   - Name: `ai-therapist` (or any name you prefer)
   - Environment: `Python 3`
   - Region: Choose the one closest to your target audience
   - Branch: `main` (or whichever branch has your code)
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Plan: Free

5. **Set Environment Variables**
   - Scroll down to the "Environment" section
   - Add a new environment variable:
     - Key: `GEMINI_API_KEY`
     - Value: Your Gemini API key (`AIzaSyDFgqb56dp44rR5oM7CKxxuwJIEN-bfHs8`)

6. **Deploy Your Application**
   - Click "Create Web Service"
   - Render will automatically build and deploy your application
   - Once deployed, you can access your app at the provided URL (e.g., `https://ai-therapist.onrender.com`)

### Troubleshooting Render Deployment

- If deployment fails, check the logs in the Render dashboard
- Ensure all dependencies are listed in `requirements.txt`
- Verify that the port configuration in your app matches what Render expects

## Deploying on Replit

Replit is a collaborative browser-based IDE that makes it easy to code and deploy applications.

### Prerequisites

- A Replit account (sign up at [replit.com](https://replit.com))

### Step-by-Step Deployment

1. **Create a New Repl**
   - Sign in to Replit and click "Create Repl"
   - Select "Python" as the template
   - Name your Repl (e.g., "AI-Therapist")
   - Click "Create Repl"

2. **Upload Your Files**
   - You can either upload all your files manually or use Git to clone your repository
   - Ensure you include all necessary files: `app.py`, `requirements.txt`, `.replit`, `replit.nix`, and the templates and static folders

3. **Set Up Environment Variables**
   - In the left sidebar, click on the "Secrets" (lock icon)
   - Add a new secret:
     - Key: `GEMINI_API_KEY`
     - Value: Your Gemini API key (`AIzaSyDFgqb56dp44rR5oM7CKxxuwJIEN-bfHs8`)
   - Click "Add new secret"

4. **Install Dependencies**
   - Open the Shell tab and run:
     ```
     pip install -r requirements.txt
     ```

5. **Run Your Application**
   - Click on the "Run" button at the top
   - Replit will execute the command specified in your `.replit` file and start your Flask application
   - Once running, your app will be available at the URL shown in the output (usually something like `https://ai-therapist.yourusername.repl.co`)

6. **Make Your Repl Always On (Optional)**
   - For free accounts, Repls shut down after inactivity
   - If you want your app to be always available, you can upgrade to Replit's paid plan

### Troubleshooting Replit Deployment

- If your app doesn't start, check the console for error messages
- Make sure your `.replit` file has the correct run command
- Verify that all dependencies are installed properly
- If you see CORS errors when testing, you may need to add CORS headers to your Flask app

## Maintaining Your Deployment

### Updating Your Application

#### On Render:
- Push changes to your GitHub repository
- Render will automatically rebuild and redeploy your application

#### On Replit:
- Make changes directly in the Replit editor
- Click the "Run" button to restart your application with the changes

### Monitoring

#### On Render:
- Render provides logs and metrics in the dashboard
- You can set up alerts for when your service goes down

#### On Replit:
- You can view logs in the console output
- Replit also provides usage metrics for your application

## Security Considerations

1. **API Key Protection**
   - Never commit your API key directly in your code
   - Always use environment variables for sensitive data
   
2. **HTTPS**
   - Both Render and Replit provide HTTPS by default, ensuring secure communication

3. **Rate Limiting**
   - Consider implementing rate limiting to prevent abuse of your API
   - This is especially important for free-tier deployments with limited resources

4. **Error Handling**
   - Ensure proper error handling to prevent exposing sensitive information in stack traces

## Cost Considerations

### Render
- Free tier includes:
  - 750 hours of runtime per month
  - Automatic HTTPS
  - Sleep after inactivity (service restarts when accessed)
- Paid tiers start at $7/month for services that don't sleep

### Replit
- Free tier includes:
  - Basic hosting with sleep after inactivity
  - Limited compute resources
- Paid tiers start at around $7/month for improved resources and always-on capability 