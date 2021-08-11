import logging
import os
from datetime import datetime

import dotenv
from aiogram import types, Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from sqlalchemy.orm import sessionmaker
from fuzzywuzzy import fuzz

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
    await bot.send_message(message.chat.id, 'Чтобы создать обычный опрос надо произнести ключевые слова - '
                                            'они подмечены жирным шрифтом.\n\n'
                                            '<b>Бот создай опрос</b> [ваш вопрос] <b>вариант</b> [ваш вариант ответа], '
                                            '<b>вариант</b> [ваш вариант ответа]...\n\n'
                                            'Чтобы создать анонимный опрос надо произнести ключевые слова - '
                                            'они подмечены жирным шрифтом.\n\n'
                                            '<b>Бот создай анонимный опрос</b> [ваш вопрос] <b>вариант</b> '
                                            '[ваш вариант ответа], <b>вариант</b> [ваш вариант ответа]...',
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
            await reformat_text(query, message)


async def reformat_text(text, message: types.Message):
    pull_choice_data_row = []
    # Get create poll command
    command_create_pull_first_index = text.find('создай')
    command_create_pull_last_index = text.find('опрос')
    command_create_pull_data_row = text[command_create_pull_first_index: command_create_pull_last_index]
    command_create_pull_data = ' '.join(command_create_pull_data_row.partition('создай')[2].split())
    if fuzz.partial_ratio(command_create_pull_data, "анонимный") > 70:
        command_create_pull_data = 'анонимный'
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
    await execute_cmd(message, command_create_pull_data, pull_question_data, pull_choice_data)


async def execute_cmd(message, command, question, choice):
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


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False)
