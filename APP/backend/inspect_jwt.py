import jwt
import inspect
print('jwt module:', jwt)
print('file:', getattr(jwt, '__file__', None))
print('attrs:', [a for a in dir(jwt) if not a.startswith('_')])
try:
    import importlib
    m = importlib.import_module('jwt')
    print('importlib module file:', getattr(m, '__file__', None))
except Exception as e:
    print('import error', e)
