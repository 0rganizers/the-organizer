import gql
from gql import Client
from gql.transport.exceptions import TransportQueryError
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport
import logging
from gql.transport.aiohttp import log as aio_logger
aio_logger.setLevel(logging.WARNING)
from gql.transport.websockets import log as websockets_logger
websockets_logger.setLevel(logging.WARNING)

from string import ascii_letters, digits
from random import choice, randrange
from datetime import datetime
from dataclasses import dataclass
import dateutil # parser, tz
import logging
import asyncio
from . import queries
import discord
import discord_slash                                                            # type: ignore
import json

log = logging.getLogger("Raffle")

@dataclass
class Raffle:
    prize: str
    participants: dict[int, float]

    def add_participant(self, participant_id):
        self.participants[participant_id] = 1.0

    def draw(self):
        return random.choices(self.participants.keys(), self.participants.values())


    
