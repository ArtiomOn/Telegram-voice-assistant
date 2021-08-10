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


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await bot.send_message(message.chat.id, 'Чтобы создать опрос надо произнести ключевые слова - '
                                            'они подмечены жирным шрифтом.\n\n'
                                            '<b>Бот создай опрос</b> [ваш вопрос] <b>вариант</b> [ваш вариант ответа], '
                                            '<b>вариант</b> [ваш вариант ответа]...', parse_mode='html')


@dp.message_handler(content_types=types.ContentType.VOICE)
async def assist(message: types.Message):
    if message.voice:
        ogg_destination, wav_destination = generate_unique_destinations()
        await message.voice.download(destination=ogg_destination)
        convert_ogg_to_wav(ogg_destination, wav_destination)
        query = audio_file_to_text(wav_destination)
        await bot.delete_message(message_id=message.message_id, chat_id=message.chat.id)
        await reformat_text(query, message)


async def reformat_text(text, message: types.Message):
    pull_choice_data = []
    command_create_pull_data = text.partition('бот создай опрос')[1]
    question_first_index = text.find('опрос')
    question_last_index = text.find('выбор')
    pull_question_row = text[question_first_index: question_last_index]
    pull_question_data = ' '.join(pull_question_row.partition('опрос')[2].split()).capitalize()
    pull_choice_first_index = text.find('выбор')
    pull_choice_last_index = len(text)
    pull_choice_data_row = text[pull_choice_first_index:pull_choice_last_index]
    for i in range(pull_choice_data_row.count('выбор')):
        pull_choice_data.append(
            ' '.join(pull_choice_data_row.split()).split('выбор', int(i + 2))[int(i + 1)].capitalize())

    await execute_cmd(message, command_create_pull_data, pull_question_data, pull_choice_data)


async def execute_cmd(message, command, question, choice):
    if fuzz.partial_ratio(command, "бот создай опрос") > 70:
        if len(choice) < 2:
            await bot.send_poll(message.chat.id, question=f'{question.capitalize()}?', options=['Да', 'Нет'],
                                is_anonymous=False)
        else:
            await bot.send_poll(message.chat.id, question=f'{question.capitalize()}?', options=choice,
                                is_anonymous=False)
    else:
        await bot.send_message(message.chat.id, 'Не понял вашу команду, повторите еще раз')


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False)
