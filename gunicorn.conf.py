# Gunicorn configuration file for Render deployment
import os

# Use PORT environment variable with fallback to 10000
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

workers = 4
threads = 2
timeout = 120 