import logging
import os
import requests
import shutil
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
OWM_KEY = os.getenv('OWM_KEY')
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


@dp.message_handler(commands=['start'])
async def command_start(message: types.Message):
    try:
        await bot.send_message(message.chat.id, 'Чтобы увидеть инструкцию напишите - /help')
    except BotBlocked:
        logging.info(f'Bot was blocked by user {message.from_user.id}')


@dp.message_handler(commands=['help'])
async def command_help(message: types.Message):
    await bot.send_message(message.chat.id, '--{опциональный ответ пользователя}\n'
                                            '--[обязательный ответ пользователя]\n\n'
                                            'Чтобы создать опрос надо произнести ключевые слова - '
                                            'они подмечены жирным шрифтом.\n'
                                            '<b>*Бот создай {анонимный} опрос</b> [ваш вопрос] <b>выбор</b> '
                                            '[ваш вариант ответа], <b>выбор</b> [ваш вариант ответа]...\n\n'
                                            'Чтобы найти видео в ютубе надо произнести ключевые слова -\n'
                                            '<b>*Бот найди видео</b> [название видео]\n\n'
                                            'Чтобы посмотреть актуальную на данный момент погоду надо произнести '
                                            'ключевые слова -\n'
                                            '<b>*Бот какая сейчас погода в стране</b> [страна] '
                                            'P.S пример МолдовА, РоссиЯ',
                           parse_mode='html')


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
    elif query.find('погода') != -1:
        await get_weather(query, message)
    else:
        await bot.send_message(message.chat.id, 'Не распознал вашу команду - для информации напишите /start')


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
    await poll_handler(message, command_create_pull_data, pull_question_data, pull_choice_data)


async def get_video_link(query, message: types.Message):
    command_find_video_name_first_index = query.find('видео')
    command_find_video_name_last_index = len(query)
    command_find_video_data_row = query[command_find_video_name_first_index: command_find_video_name_last_index]
    command_find_video_data = command_find_video_data_row.partition('видео')[2]
    await get_video_handler(message, command_find_video_data)


async def get_weather(query, message: types.Message):
    command_find_weather_first_index = query.find('погода')
    command_find_weather_last_index = len(query)
    command_find_weather_data_row = query[command_find_weather_first_index:command_find_weather_last_index]
    if command_find_weather_data_row.find('городе') > -1:
        command_find_weather_data = command_find_weather_data_row.partition('городе')[2]
        await get_weather_handler(message, command_find_weather_data.strip())
    elif command_find_weather_data_row.find('стране') > -1:
        command_find_weather_data = command_find_weather_data_row.partition('стране')[2]
        await get_weather_handler(message, command_find_weather_data.strip())


async def poll_handler(message, command, question, choice):
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


async def get_weather_handler(message: types.Message, city):
    response = requests.get(
        url=f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OWM_KEY}&units=metric')
    if response.status_code == 200:
        country_name = response.json().get('name')
        weather_main = response.json().get('main')
        weather_data = response.json().get('weather')
        wind_data = response.json().get('wind')

        weather_tamp = weather_main['temp']
        weather_description = weather_data[0]['description']
        weather_humidity = weather_main['humidity']
        wind_speed = wind_data['speed']

        if weather_description.find('clouds') > -1:
            sti = open('../static/clouds.tgs', 'rb')
            await bot.send_sticker(sticker=sti, chat_id=message.chat.id)
        elif weather_description.find('clear') > -1:
            sti = open('../static/sunny.tgs', 'rb')
            await bot.send_sticker(sticker=sti, chat_id=message.chat.id)
        elif weather_description.find('rain') > -1:
            sti = open('../static/rain.tgs', 'rb')
            await bot.send_sticker(sticker=sti, chat_id=message.chat.id)
        await bot.send_message(message.chat.id, f'Местность - {country_name}\n'
                                                f'Небо - {weather_description}\n'
                                                f'Скорость ветра - {wind_speed} m/h\n'
                                                f'Температура - {str(weather_tamp)[:2]}°C\n'
                                                f'Влажность - {weather_humidity}%')
    else:
        await bot.send_message(message.chat.id, 'Я не нашел странну, пример ввода страны - МолдовА, РоссиЯ...')


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False, timeout=120)
    shutil.rmtree(r'C:\Users\artio\PycharmProjects\pull_bot\storage')
