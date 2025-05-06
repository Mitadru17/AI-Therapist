# Gunicorn configuration file for Render deployment
bind = "0.0.0.0:10000"  # Using port 10000 as per Render documentation
workers = 4
threads = 2
timeout = 120 