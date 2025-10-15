import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("GUNICORN_WORKERS"))
forwarded_allow_ips = "*"
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}
accesslog = "-"
access_log_format = "%({x-forwarded-for}i)s %(l)s %(u)s %(t)s '%(r)s' %(s)s %(b)s '%(f)s' '%(a)s'"

# Si la memoria crece mucho
# max_requests = 1000
# max_requests_jitter = 60
