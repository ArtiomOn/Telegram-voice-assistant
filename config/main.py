import logging
import os

import dotenv
from aiogram import types, Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from fuzzywuzzy import fuzz

from services.converter import convert_ogg_to_wav
from services.recognizer import audio_file_to_text
from services.storage import generate_unique_destinations

logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()

bot = Bot(token=os.getenv('TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

opts = {
    'tbr': ('создай', 'сделай', 'сгенерируй'),
    'cmds': {
        'pull': ('опрос', 'пулл', 'pull')
    }
}


@dp.message_handler(content_types=types.ContentType.VOICE)
async def assist(message: types.Message):
    if message.voice:
        ogg_destination, wav_destination = generate_unique_destinations()
        await message.voice.download(destination=ogg_destination)
        convert_ogg_to_wav(ogg_destination, wav_destination)
        query = audio_file_to_text(wav_destination)
        await message.delete()
        await bot.send_message(message.chat.id, query)
        return query


async def recognize_cmd(cmd):
    rec = {'cmd': '', 'percent': 0}
    for c, v in opts['cmds'].items():
        for x in v:
            vrt = fuzz.ratio(cmd, x)
            if vrt > rec['percent']:
                rec['cmd'] = c
                rec['percent'] = vrt

    return rec


async def execute_cmd(cmd, message: types.Message):
    if cmd == 'pull':
        await bot.send_message(message.chat.id, 'Testing')
    else:
        await bot.send_message(message.chat.id, 'Sorry, not found')


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False)
