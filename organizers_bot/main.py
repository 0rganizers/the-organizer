from . import config
from . import bot

import asyncio
import pathlib

# TODO: proper CLI parsing (click?)
def main():
    config.load(pathlib.Path("config.json"))
    loop = asyncio.get_event_loop()
    bot.run(loop)
    loop.run_forever()
