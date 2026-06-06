import requests
import os

url = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8001')
login = {'email': 'admin@illinoistracker.app', 'password': 'Demo1234!'}
print('POST', url + '/api/auth/login', login)
try:
    r = requests.post(url + '/api/auth/login', json=login, timeout=10)
    print('STATUS', r.status_code)
    print('TEXT', r.text)
    try:
        print('JSON', r.json())
    except Exception:
        pass
except Exception as e:
    print('ERR', e)
