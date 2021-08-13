import os

import dotenv

dotenv.load_dotenv()

TOKEN = os.getenv('TOKEN')

BASE_ROOT = os.path.dirname(os.path.abspath(__file__))

STORAGE_ROOT = os.path.join(os.path.dirname(BASE_ROOT), 'storage')
