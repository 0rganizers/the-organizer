from . import config

import pathlib

# TODO: proper CLI parsing (click?)
def main():
    config.load(pathlib.Path("config.json"))
