# Gunicorn configuration file for Render deployment
import os

# Bind directly to port 3000 for Render deployment
bind = "0.0.0.0:3000"

workers = 4
threads = 2
timeout = 120 