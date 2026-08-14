from pymongo import MongoClient
import os
import bcrypt

uri = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'ides_tracker_db')
email = 'admin@illinoistracker.app'
new_password = 'Demo1234!'

client = MongoClient(uri)
db = client[db_name]
user = db.users.find_one({'email': email})
if not user:
    print('User not found:', email)
    raise SystemExit(1)

new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
res = db.users.update_one({'email': email}, {'$set': {'password_hash': new_hash}})
print('Matched:', res.matched_count, 'Modified:', res.modified_count)
# verify
ok = bcrypt.checkpw(new_password.encode(), db.users.find_one({'email': email})['password_hash'].encode())
print('Verify new password:', ok)
