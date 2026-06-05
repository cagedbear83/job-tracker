from pymongo import MongoClient
import os
import bcrypt

uri = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'ides_tracker_db')
client = MongoClient(uri)
db = client[db_name]
email = 'admin@illinoistracker.app'
user = db.users.find_one({'email': email})
if not user:
    print('User not found')
    raise SystemExit(1)
hash = user['password_hash']
print('Hash:', hash)
for pwd in ['Demo1234!', 'demo1234!', 'Demo1234', 'Demo1234!\n']:
    ok = bcrypt.checkpw(pwd.encode(), hash.encode())
    print(pwd, '->', ok)
