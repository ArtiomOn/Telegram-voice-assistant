import logging
import os
from datetime import datetime
import dotenv
from aiogram import types, Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked
from fuzzywuzzy import fuzz
from sqlalchemy.orm import sessionmaker
from youtubesearchpython import *

from config.models import PullData, database_dsn
from services.converter import convert_ogg_to_wav
from services.recognizer import audio_file_to_text
from services.storage import generate_unique_destinations

logging.basicConfig(level=logging.INFO)

session = sessionmaker(bind=database_dsn)()

dotenv.load_dotenv()

bot = Bot(token=os.getenv('TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        await bot.send_message(message.chat.id, 'Чтобы создать обычный опрос надо произнести ключевые слова - '
                                                'они подмечены жирным шрифтом.\n\n'
                                                '<b>Бот создай опрос</b> [ваш вопрос] <b>вариант</b> '
                                                '[ваш вариант ответа], <b>вариант</b> [ваш вариант ответа]...\n\n'
                                                'Чтобы создать анонимный опрос надо произнести ключевые слова - '
                                                'они подмечены жирным шрифтом.\n\n'
                                                '<b>Бот создай анонимный опрос</b> [ваш вопрос] <b>вариант</b> '
                                                '[ваш вариант ответа], <b>вариант</b> [ваш вариант ответа]...',
                               parse_mode='html')
        await bot.get_chat_member(message.chat.id, bot.id)
    except BotBlocked:
        logging.info(f'Bot was blocked by user {message.from_user.id}')


@dp.message_handler(content_types=types.ContentType.VOICE)
async def assist(message: types.Message):
    if message.voice:
        ogg_destination, wav_destination = generate_unique_destinations()
        await message.voice.download(destination=ogg_destination)
        convert_ogg_to_wav(ogg_destination, wav_destination)
        query = audio_file_to_text(wav_destination)
        try:
            await bot.delete_message(message_id=message.message_id, chat_id=message.chat.id)
        except Exception as e:
            logging.info(f'Error occurs {e} with user {message.from_user.id}')
        else:
            await command_handler(query, message)


async def command_handler(query, message: types.Message):
    if query.find('создай') != -1 or query.find('опрос') != -1:
        await create_poll(query, message)
    elif query.find('найди') != -1 or query.find('видео') != -1:
        await get_video_link(query, message)
    else:
        await bot.send_message(message.chat.id, 'Not found')


async def create_poll(text, message: types.Message):
    pull_choice_data_row = []
    # Get create poll command
    command_create_pull_first_index = text.find('создай')
    command_create_pull_last_index = text.find('опрос')
    command_create_pull_data_row = text[command_create_pull_first_index: command_create_pull_last_index]
    command_create_pull_data = ' '.join(command_create_pull_data_row.partition('создай')[2].split())
    if fuzz.partial_ratio(command_create_pull_data, "анонимный") > 70:
        command_create_pull_data = 'анонимный'
    elif command_create_pull_last_index == -1 or command_create_pull_first_index == -1:
        command_create_pull_data = 'NonType'
    else:
        command_create_pull_data = 'обычный'

    # Get pull question
    question_first_index = text.find('опрос')
    question_last_index = text.find('выбор')
    pull_question_row = text[question_first_index: question_last_index]
    pull_question_data = ' '.join(pull_question_row.partition('опрос')[2].split()).capitalize()

    # Get poll choice
    pull_choice_first_index = text.find('выбор')
    pull_choice_last_index = len(text)
    pull_choice_data_words = text[pull_choice_first_index:pull_choice_last_index]
    for i in range(pull_choice_data_words.count('выбор')):
        pull_choice_data_row.append(
            ''.join(pull_choice_data_words.split()).split('выбор', int(i + 2))[int(i + 1)].capitalize())
    pull_choice_data = [choices for choices in pull_choice_data_row if choices.strip()]
    # Save data in postgres
    query = PullData(user_id=message.from_user.id,
                     pull_question=pull_question_data,
                     pull_choice=pull_choice_data,
                     created_at=datetime.now(),
                     )
    session.add(query)
    session.commit()
    await execute_poll(message, command_create_pull_data, pull_question_data, pull_choice_data)


async def get_video_link(query, message: types.Message):
    command_find_video_name_first_index = query.find('видео')
    command_find_video_name_last_index = len(query)
    command_find_video_data_row = query[command_find_video_name_first_index: command_find_video_name_last_index]
    command_find_video_data = command_find_video_data_row.partition('видео')[2]
    await get_video_handler(message, command_find_video_data)


async def execute_poll(message, command, question, choice):
    if command == 'обычный':
        if len(choice) < 2:
            await bot.send_poll(message.chat.id, question=f'{question.capitalize()}?', options=['Да', 'Нет'],
                                is_anonymous=False)
        else:
            await bot.send_poll(message.chat.id, question=f'{question.capitalize()}?', options=choice,
                                is_anonymous=False)

    elif command == 'анонимный':
        if len(choice) < 2:
            await bot.send_poll(message.chat.id, question=f'{question.capitalize()}?', options=['Да', 'Нет'],
                                is_anonymous=True)
        else:
            await bot.send_poll(message.chat.id, question=f'{question.capitalize()}?', options=choice,
                                is_anonymous=True)
    else:
        await bot.send_message(message.chat.id, 'Не понял вашу команду, повторите еще раз')


async def get_video_handler(message: types.Message, query):
    custom_search = CustomSearch(query=f'{query}', limit=2, searchPreferences='en')

    if custom_search.result()['result']:
        for i in range(2):
            await bot.send_message(message.chat.id, dict(custom_search.result()['result'][i]).get('link'))
    else:
        await bot.send_message(message.chat.id, 'Видео не было найдено')


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False)
