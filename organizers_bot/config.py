import dataclasses
import json
import logging
import pathlib

@dataclasses.dataclass
class BotConfig:
    token: str
    client_id: int
    guild: int

@dataclasses.dataclass
class ManagementConfig:
    categories: list[str]

def load(filename: pathlib.Path):
    global is_loaded, bot, mgmt
    with filename.open("r") as configfile:
        conf = json.load(configfile)
        bot = BotConfig(
                conf['bot']['token'],
                conf['bot']['client_id'],
                conf['bot']['guild'],
                )
        mgmt = ManagementConfig(
                conf['mgmt']['categories'],
                )
    is_loaded = True

logging.basicConfig(level=logging.INFO)
is_loaded: bool = False
bot: BotConfig
mgmt: ManagementConfig
