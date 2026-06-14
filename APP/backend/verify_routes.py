import os
from pathlib import Path

import server
from dotenv import load_dotenv

load_dotenv(Path(".env"))
app = server.app

print("ROUTES", len(app.routes))
for r in app.routes:
    methods = getattr(r, "methods", None)
    if methods:
        print(sorted(methods), r.path)

print("\nENV VARS")
needed = [
    "MONGO_URL",
    "DB_NAME",
    "JWT_SECRET",
    "FRONTEND_URL",
    "MAILGUN_API_KEY",
    "MAILGUN_DOMAIN",
    "MAILGUN_FROM",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "GEMINI_API_KEY",
    "CORS_ORIGINS",
]
for k in needed:
    v = os.environ.get(k)
    print(k, "SET" if v else "MISSING", repr(v)[:80])
