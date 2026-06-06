import jwt
from datetime import datetime, timezone
print('module file', getattr(jwt,'__file__',None))
print('has encode?', hasattr(jwt,'encode'))
print('has JWT?', hasattr(jwt,'JWT'))

payload={'sub':'123','email':'a@b.com','exp':int(datetime.now(timezone.utc).timestamp())}
secret='s3cr3t'
try:
    jwk = jwt.jwk_from_bytes(secret.encode())
    j = jwt.JWT()
    token = j.encode({'alg':'HS256'}, payload, jwk)
    print('token len', len(token))
except Exception as e:
    print('error', e)
    raise
