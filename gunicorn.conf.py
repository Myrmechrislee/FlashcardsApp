# Gunicorn configuration file
import multiprocessing

max_requests = 1000
max_requests_jitter = 50
certfile = '/etc/letsencrypt/live/flash-cards.clintonalee.com/fullchain.pem'
keyfile = '/etc/letsencrypt/live/flash-cards.clintonalee.com/privkey.pem'

log_file = "-"

bind = "0.0.0.0:443"

workers = (multiprocessing.cpu_count() * 2) + 1
threads = workers

timeout = 120