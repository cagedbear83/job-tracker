import asyncio
import traceback
import os

# Ensure .env loaded same as server
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import server
from server import LoginIn

async def run():
    try:
        body = LoginIn(email='admin@illinoistracker.app', password='Demo1234!')
        res = await server.login(body)
        print('Login result:', res)
    except Exception as e:
        print('Exception during login:')
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(run())
