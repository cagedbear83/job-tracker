import jwt
from datetime import datetime, timezone
print('module file', getattr(jwt,'__file__',None))
print('has encode?', hasattr(jwt,'encode'))
print('has JWT?', hasattr(jwt,'JWT'))

payload={'sub':'123','email':'a@b.com','exp':datetime.now(timezone.utc).isoformat()}
secret='s3cr3t'
if hasattr(jwt,'encode'):
    print('pyjwt encode result:', jwt.encode(payload, secret, algorithm='HS256'))
else:
    try:
        JWT = jwt.JWT
        j = JWT()
        token = j.encode({'alg':'HS256'}, payload, secret)
        print('python-jwt encode result:', token)
    except Exception as e:
        print('fallback encode failed:', e)
