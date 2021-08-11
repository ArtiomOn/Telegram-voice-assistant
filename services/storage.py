import os
import uuid

from config.settings import STORAGE_ROOT

OGG_ROOT = os.path.join(STORAGE_ROOT, 'ogg')
WAV_ROOT = os.path.join(STORAGE_ROOT, 'wav')

os.makedirs(STORAGE_ROOT, exist_ok=True)
os.makedirs(OGG_ROOT, exist_ok=True)
os.makedirs(WAV_ROOT, exist_ok=True)

MAX_TRIES = 100


def generate_unique_destinations():
    for i in range(MAX_TRIES):
        unique_name = uuid.uuid4()
        ogg_destination = os.path.join(OGG_ROOT, f'{unique_name}.ogg')
        wav_destination = os.path.join(WAV_ROOT, f'{unique_name}.wav')

        if not os.path.isfile(ogg_destination) and not os.path.isfile(wav_destination):
            return ogg_destination, wav_destination

    raise Exception(f'Failed to create unique file names')
