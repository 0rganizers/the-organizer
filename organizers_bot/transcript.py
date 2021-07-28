import chat_exporter
from . import config
import logging
import discord
import discord.iterators
import discord.http
import discord_slash
import asyncio
import aiohttp
import backblaze
import os
from urllib import parse
import hashlib
import copy
import json

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

    def get_target_path(self, url: str) -> str:
        discord_parsed = parse.urlparse(url)
        target_path = discord_parsed.path.strip("/")
        target_path = os.path.join("assets", target_path)
        return target_path

    async def save_contents(self, target_path: str, contents: bytes):
        await self.ensure_backblaze()
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
        # no need to download again!
        target_path = self.get_target_path(discord_url._url)
        if target_path in self.existing_assets:
            return target_path
        self.existing_assets.add(target_path)
        
        # self.log.info("Uploading from %s to %s", discord_url, target_path)
        # response = self.session.get(discord_url)
        contents = await discord_url.read()
        await self.save_contents(target_path, contents)
        return target_path

    async def save_url(self, url: str, target_path=None) -> str:
        if target_path is None:
            target_path = self.get_target_path(url)
        if target_path in self.existing_assets:
            return target_path
        self.existing_assets.add(target_path)
        async with self.session.get(url) as resp:
            contents = await resp.content.read()
            log.info("Downloaded contents %s: %d", url, len(contents))
            await self.save_contents(target_path, contents)
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
        #todo save emojis!
        if "sticker_items" in msg:
            for idx, sticker in enumerate(msg["sticker_items"]):
                # log.info("Have sticker: %s, %s", sticker, sticker.image_url_as())
                url = f"https://media.discordapp.net/stickers/{sticker['id']}.png?size=256&passthrough=false"
                new_url = await self.save_url(url)
                msg["sticker_items"][idx]["url"] = new_url
        for idx, attachment in enumerate(message.attachments):
            new_url = await self.save_url(attachment.proxy_url)
            msg["attachments"][idx]["proxy_url"] = new_url
            msg["attachments"][idx]["url"] = new_url
        for idx, embed in enumerate(message.embeds):
            embed: discord.Embed
            provider = embed.provider.name
            log.info("Saving embed %s", embed)
            url_parsed = parse.urlparse(embed.url)
            base_path = os.path.basename(url_parsed.path)
            target_path = os.path.join("assets", "embeds", provider)
            log.info("Target path: %s", target_path)
            log.info("Video: %s. Thumb: %s. Image: %s", embed.video.url, embed.thumbnail.proxy_url, embed.image.proxy_url)
            embed_dict = msg["embeds"][idx]
            if embed.video.url is not discord.Embed.Empty:
                video_path = os.path.join(target_path, "video.mp4")
                new_url = await self.save_url(embed.video.url, video_path)
                embed_dict["video"]["url"] = new_url
            if embed.thumbnail.proxy_url is not discord.Embed.Empty:
                new_url = await self.save_url(embed.thumbnail.proxy_url, os.path.join(target_path, "thumbnail.png"))
                embed_dict["thumbnail"]["url"] = new_url
                embed_dict["thumbnail"]["proxy_url"] = new_url
            if embed.image.proxy_url is not discord.Embed.Empty:
                self.log.info("Embed image: %s", embed.image)
                new_url = await self.save_url(embed.image.proxy_url, os.path.join(target_path, "image.png"))
                embed_dict["image"]["url"] = new_url
                embed_dict["image"]["proxy_url"] = new_url
            msg["embeds"][idx] = embed_dict
        for idx, reaction in enumerate(message.reactions):
            if reaction.custom_emoji:
                new_url = await self.save_asset(reaction.emoji.url_as())
                msg["reactions"][idx]["emoji"]["url"] = new_url
        return msg

    async def save_json(self, data, filepath):
        self.log.info("Saving json to %s", filepath)
        json_data = json.dumps(data).encode("utf8")
        await self.save_contents(filepath, json_data)


class Transcript:
    def __init__(self, mgr: TranscriptManager, category: discord.CategoryChannel, ctx: discord_slash.SlashContext) -> None:
        self.log = log.getChild("maker")
        self.category = category
        self.mgr = mgr
        self.ctx = ctx
        self.status_msg = None
        self.progress = None
        ctx.author.avatar_url
        self.json_folder = os.path.join("archive", "ctf", category.name)

    @property
    def http(self) -> discord.http.HTTPClient:
        return self.mgr.bot.http


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
        channel_folder = os.path.join(self.json_folder, channel.name)
        self.log.info("Building messages for channel %s, %s", channel.name, type(channel._state))
        await self.update_status(f"Exporting {channel.name}")
        message: discord.message.Message
        og_msgs = []
        changed_msgs = []
        channel_meta = os.path.join(channel_folder, "meta.json")
        channel_json = await self.http.get_channel(channel.id)
        await self.mgr.save_json(channel_json, channel_meta)
        async for item in json_history(channel, oldest_first=True):
            message, data = item
            # self.log.info("Retrieved message: %s (%s)", message, data)
            changed = await self.mgr.save_msg_contents(message, copy.deepcopy(data))
            changed_msgs.append(changed)
            og_msgs.append(data)
        import json
        messages_path = os.path.join(channel_folder, "messages.json")
        await self.mgr.save_json(changed_msgs, messages_path)
        orig_path = os.path.join(channel_folder, "messages.orig.json")
        await self.mgr.save_json(og_msgs, orig_path)
        # with open("test.json", "w") as f:
        #     json.dump(changed_msgs, f, indent=4, sort_keys=True)
        # with open("originals.json", "w") as f:
        #     json.dump(og_msgs, f, indent=4, sort_keys=True)

    async def build(self):
        self.log.info("Building Transcript")
        await self.update_status("Building Transcript")
        try:
            category_channel = await self.http.get_channel(self.category.id)
            category_json = os.path.join(self.json_folder, "meta.json")
            await self.mgr.save_json(category_channel, category_json)
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

