import chat_exporter
from . import config
import logging
import discord
import discord.iterators
import discord_slash
import asyncio
import aiohttp
import backblaze
import os
from urllib import parse
import hashlib

log = logging.getLogger("transcript")

class JSONHistoryIterator(discord.iterators.HistoryIterator):
    async def flatten(self):
        # this is similar to fill_messages except it uses a list instead
        # of a queue to place the messages in.
        result = []
        channel = await self.messageable._get_channel()
        self.channel = channel
        while self._get_retrieve():
            data = await self._retrieve_messages(self.retrieve)
            if len(data) < 100:
                self.limit = 0 # terminate the infinite loop

            if self.reverse:
                data = reversed(data)
            if self._filter:
                data = filter(self._filter, data)

            for element in data:
                result.append((self.state.create_message(channel=channel, data=element), element))
        return result

    async def fill_messages(self):
        if not hasattr(self, 'channel'):
            # do the required set up
            channel = await self.messageable._get_channel()
            self.channel = channel

        if self._get_retrieve():
            data = await self._retrieve_messages(self.retrieve)
            if len(data) < 100:
                self.limit = 0 # terminate the infinite loop

            if self.reverse:
                data = reversed(data)
            if self._filter:
                data = filter(self._filter, data)

            channel = self.channel
            for element in data:
                await self.messages.put((self.state.create_message(channel=channel, data=element), element))

def json_history(mable: discord.abc.Messageable, limit=100, before=None, after=None, around=None, oldest_first=None):
    return JSONHistoryIterator(mable, limit=limit, before=before, after=after, around=around, oldest_first=oldest_first)

class TranscriptManager:
    def __init__(self, bot: discord.Client) -> None:
        self.log = log.getChild("manager")
        self.bot = bot
        self.s3 = backblaze.Awaiting(
            key_id=config.s3.keyID,
            key=config.s3.key
        )
        self.s3_init = False
        self.s3_bucket: backblaze.AwaitingBucket = None
        self.session = aiohttp.ClientSession()
        self.existing_assets = set()

    async def ensure_backblaze(self):
        if not self.s3_init:
            self.s3_init = True
            await self.s3.authorize()
            self.s3_bucket = self.s3.bucket(config.s3.bucket)
            async for data, bucket in self.s3.buckets():
                log.info("Bucket: %s", data.name)
            log.info("Uploading to s3 bucket %s", self.s3_bucket.bucket_id)

    async def create(self, category: discord.CategoryChannel, ctx: discord_slash.SlashContext):
        self.log.info("Creating transcript for %s", category.name)
        trans = Transcript(self, category, ctx)
        await trans.build()

    async def save_asset(self, discord_url: discord.Asset) -> str:
        """Save an asset found at discord_url to assets/path_from_discord_url.
        Returns the URL to access the asset at.

        Parameters
        ----------
        discord_url : str
            [description]
        target_path : str
            [description]

        Returns
        -------
        str
            [description]
        """
        await self.ensure_backblaze()
        # no need to download again!
        discord_parsed = parse.urlparse(discord_url._url)
        target_path = discord_parsed.path.strip("/")
        if target_path in self.existing_assets:
            return
        self.existing_assets.add(target_path)
        target_path = os.path.join("assets", target_path)
        self.log.info("Uploading from %s to %s", discord_url, target_path)
        # response = self.session.get(discord_url)
        contents = await discord_url.read()
        sha1 = hashlib.sha1(contents).hexdigest()
        # delete any pre-existing assets.
        existing_ok = False
        async for existing in self.s3_bucket.file_names(backblaze.settings.FileSettings(None, prefix=target_path)):
            filem, file, _ = existing
            if sha1 != filem.content_sha1:
                await file.delete()
            else:
                return filem.file_name
        filem, file = await self.s3_bucket.upload(backblaze.settings.UploadSettings(target_path), contents)
        self.log.info("Uploaded to %s", file.file_id)
        return target_path

    async def save_msg_contents(self, message: discord.message.Message, msg: dict) -> dict:
        """Saves any contents found in message and changes the url if need be.

        Parameters
        ----------
        msg : dict
            [description]

        Returns
        -------
        dict
            [description]
        """
        author: discord.User = message.author
        await self.save_asset(author.avatar_url_as(static_format="png"))


class Transcript:
    def __init__(self, mgr: TranscriptManager, category: discord.CategoryChannel, ctx: discord_slash.SlashContext) -> None:
        self.log = log.getChild("maker")
        self.category = category
        self.mgr = mgr
        self.ctx = ctx
        self.status_msg = None
        self.progress = None
        ctx.author.avatar_url

    async def update_status(self, status, done=False):
        status_msg = f"""Exporting Category {self.category.name} {config.mgmt.loading_emoji}
{status}
"""
        
        if self.progress is not None:
            status_msg += self.progress.bar()
        if done:
            status_msg = status
        if self.status_msg is None:
            self.status_msg = await self.ctx.send(status_msg)
        else:
            await self.status_msg.edit(content=status_msg)

    async def build_messages(self, channel: discord.TextChannel) -> list:
        """Builds a list of message json objects, that are found inside channel.
        It also downloads any found attachments to s3 and replaces the links to them.

        Parameters
        ----------
        channel : discord.TextChannel
            The channel where to build from.            

        Returns
        -------
        list
            List of message json objects.
        """
        self.log.info("Building messages for channel %s, %s", channel.name, type(channel._state))
        await self.update_status(f"Exporting {channel.name}")
        message: discord.message.Message
        async for item in json_history(channel, oldest_first=True):
            message, data = item
            # self.log.info("Retrieved message: %s (%s)", message, data)
            changed = await self.mgr.save_msg_contents(message, data)

    async def build(self):
        self.log.info("Building Transcript")
        await self.update_status("Building Transcript")
        try:
            channel_waits = []
            for channel in self.category.channels:
                channel_waits.append(self.build_messages(channel))
            await asyncio.gather(*channel_waits)
        except:
            log.exception("Failed to build transcript")
            await self.update_status("Failed to build transcript!", True)
            return
        log.info("Finished with transcript")
        await self.update_status("Finished Building Transcript", True)


