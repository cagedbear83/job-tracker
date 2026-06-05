from pymongo import MongoClient
import os

uri = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'ides_tracker_db')
print('Connecting to', uri, 'db', db_name)

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
try:
    client.admin.command('ping')
except Exception as e:
    print('Mongo connection error:', e)
    raise SystemExit(1)

db = client[db_name]
users = list(db.users.find({}, {'_id': 0, 'email': 1, 'password_hash': 1, 'role': 1}).limit(50))
print('Found', len(users), 'users')
for u in users:
    print(u)
