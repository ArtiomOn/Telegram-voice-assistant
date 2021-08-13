import logging
import os

import dotenv
import requests
from aiogram import types, Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked
from youtubesearchpython import *

from services.converter import convert_ogg_to_wav
from services.recognizer import audio_file_to_text
from services.storage import generate_unique_destinations

logging.basicConfig(level=logging.INFO)

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
                                            '<b>*Бот создай {анонимный} опрос</b> [ваш вопрос] <b>вариант</b> '
                                            '[ваш вариант ответа], <b>вариант</b> [ваш вариант ответа]...\n\n'
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
            await command_handler(message, query)


async def command_handler(message: types.Message, query):
    if (query.find('создай') or query.find('опрос')) != -1:
        await create_poll(message, query)
    elif (query.find('найди') or query.find('видео')) != -1:
        await get_video_link(message, query)
    elif query.find('погода') != -1:
        await get_weather(message, query)
    else:
        await bot.send_message(message.chat.id, 'Не распознал вашу команду - для информации напишите /help')


async def create_poll(message: types.Message, text):
    pull_choice_data_row = []
    # Get poll command
    if text.find('анонимный') != -1:
        command_create_pull_data = 'анонимный'
    else:
        command_create_pull_data = 'обычный'

    # Get pull question
    question_first_index = text.find('опрос')
    if text.find('вариант') != -1:
        question_last_index = text.find('вариант')
    else:
        question_last_index = len(text)
    pull_question_row = text[question_first_index: question_last_index]
    pull_question_data = ' '.join(pull_question_row.partition('опрос')[2].split()).capitalize()

    # Get poll choice
    pull_choice_first_index = text.find('вариант')
    pull_choice_last_index = len(text)
    pull_choice_data_words = text[pull_choice_first_index:pull_choice_last_index]
    for i in range(pull_choice_data_words.count('вариант')):
        pull_choice_data_row.append(
            ''.join(pull_choice_data_words.split()).split('вариант', int(i + 2))[int(i + 1)].capitalize())
    pull_choice_data = [choices for choices in pull_choice_data_row if choices.strip()]
    await poll_handler(message, command_create_pull_data, pull_question_data, pull_choice_data)


async def get_video_link(message: types.Message, query):
    command_find_video_name_first_index = query.find('видео')
    command_find_video_name_last_index = len(query)
    command_find_video_data_row = query[command_find_video_name_first_index: command_find_video_name_last_index]
    command_find_video_data = command_find_video_data_row.partition('видео')[2]
    await get_video_handler(message, command_find_video_data)


async def get_weather(message: types.Message, query):
    command_find_weather_first_index = query.find('погода')
    command_find_weather_last_index = len(query)
    command_find_weather_data_row = query[command_find_weather_first_index:command_find_weather_last_index]
    if command_find_weather_data_row.find('городе') > -1:
        command_find_weather_data = command_find_weather_data_row.partition('городе')[2]
        await get_weather_handler(message, command_find_weather_data.strip())
    elif command_find_weather_data_row.find('стране') > -1:
        command_find_weather_data = command_find_weather_data_row.partition('стране')[2]
        await get_weather_handler(message, command_find_weather_data.strip())
    else:
        await bot.send_message(message.chat.id, 'Не распознал страну, попробуйте еще раз.')


async def poll_handler(message: types.Message, command, question, choice):
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
        await bot.send_message(message.chat.id, 'Не понял вашу команду, попробуйте еще раз')


async def get_video_handler(message: types.Message, query):
    custom_search = CustomSearch(query=str(query), limit=1, searchPreferences='en')

    if custom_search.result()['result']:
        for i in range(custom_search.limit):
            await bot.send_message(message.chat.id, dict(custom_search.result()['result'][i]).get('link'))
    else:
        await bot.send_message(message.chat.id, 'Видео не было найдено, попробуйте еще раз.')


async def get_weather_handler(message: types.Message, city):
    walking_status = []
    response = requests.get(
        url=f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OWM_KEY}&units=metric')
    if response.status_code == 200:
        country_name = response.json().get('name')
        weather_main = response.json().get('main')
        weather_data = response.json().get('weather')
        wind_data = response.json().get('wind')

        weather_temp = weather_main['temp']
        weather_description = weather_data[0]['description']
        weather_humidity = weather_main['humidity']
        wind_speed = wind_data['speed']

        if weather_description.find('clouds') > -1:
            sticker = open('../static/clouds.tgs', 'rb')
            await bot.send_sticker(sticker=sticker, chat_id=message.chat.id)
        elif weather_description.find('clear') > -1:
            sticker = open('../static/sunny.tgs', 'rb')
            await bot.send_sticker(sticker=sticker, chat_id=message.chat.id)
        elif weather_description.find('rain') > -1:
            sticker = open('../static/rain.tgs', 'rb')
            await bot.send_sticker(sticker=sticker, chat_id=message.chat.id)

        if weather_description.find('clear') != -1 and 35 > int(str(weather_temp)[:2]) > 15:
            walking_status.append('Хорошо')
        elif weather_description.find('rain') != -1 and 35 > int(str(weather_temp)[:2]) > 25:
            walking_status.append('Можно, но лучше повременить')
        elif weather_description.find('clouds') != -1 and 35 > int(str(weather_temp)[:2]) > 18:
            walking_status.append('Хорошо, но остерегайтесь дождя')
        else:
            walking_status.append('Плохо')

        await bot.send_message(message.chat.id, f'Местность - {country_name}\n'
                                                f'Небо - {weather_description}\n'
                                                f'Скорость ветра - {wind_speed} km/h\n'
                                                f'Температура - {str(weather_temp)[:2]}°C\n'
                                                f'Влажность - {weather_humidity}%\n'
                                                f'Пробежка - {"".join(walking_status)}')
    else:
        await bot.send_message(message.chat.id, 'Я не нашел страну, пример ввода страны - МолдовА, РоссиЯ..')


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False, timeout=120)
