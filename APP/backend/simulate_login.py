from pymongo import MongoClient
import os
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta

uri = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'ides_tracker_db')
JWT_SECRET = os.environ.get('JWT_SECRET')
print('JWT_SECRET present:', bool(JWT_SECRET))

client = MongoClient(uri)
db = client[db_name]
email = 'admin@illinoistracker.app'
user = db.users.find_one({'email': email})
print('Found user:', bool(user))
if not user:
    raise SystemExit(1)

pw = 'Demo1234!'
ok = bcrypt.checkpw(pw.encode(), user['password_hash'].encode())
print('bcrypt check:', ok)

payload = {
    'sub': user['id'],
    'email': user['email'],
    'exp': datetime.now(timezone.utc) + timedelta(days=7),
    'iat': datetime.now(timezone.utc),
}
try:
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    print('Token:', token)
except Exception as e:
    print('JWT.encode error:', type(e), e)
    raise
