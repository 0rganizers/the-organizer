from . import config
from . import transcript

import asyncio
import functools
import logging
import typing

import discord                                                                  # type: ignore
import discord_slash                                                            # type: ignore
from discord_slash.utils.manage_commands import create_option, create_choice    # type: ignore
from discord_slash.model import SlashCommandOptionType                          # type: ignore

import chat_exporter
import io
import os

def require_role(minreq=None):
    if minreq is None:
        minreq = config.mgmt.player_role

    def decorator(f):
        @functools.wraps(f)
        async def wrapper(ctx: discord_slash.SlashContext, *args, **kw):
            if minreq not in [r.id for r in ctx.author.roles]:
                await ctx.send("Get lost!")
            else:
                return await f(ctx, *args, **kw)
        return wrapper
    return decorator

def setup():
    assert config.is_loaded

    bot = discord.Client(intents=discord.Intents.default())
    slash = discord_slash.SlashCommand(bot, sync_commands=True)
    log = logging.getLogger("bot")
    trans_mgr = transcript.TranscriptManager(bot)

    @bot.event
    async def on_ready():
        guild = bot.get_guild(config.bot.guild)

        log.info(discord.utils.oauth_url(
            config.bot.client_id,
            guild=guild,
            scopes=["bot", "applications.commands"]
            ))

    @slash.slash(name="ping", description="Just a test, sleeps for 5 seconds then replies with 'pong'", guild_ids=[config.bot.guild])
    async def ping(ctx: discord_slash.SlashContext):
        await ctx.defer()
        await asyncio.sleep(5)
        await ctx.send("Pong!")

    @slash.slash(name="chal",
                 description="Create a new challenge channel",
                 guild_ids=[config.bot.guild],
                 options=[
                        create_option(name="category",
                                      description="Which category does the channel belong to",
                                      option_type=SlashCommandOptionType.STRING,
                                      required=True,
                                      choices=dict(zip(*[config.mgmt.categories]*2))
                                      ),
                        create_option(name="challenge",
                                      description="Challenge name",
                                      option_type=SlashCommandOptionType.STRING,
                                      required=True)
                     ])
    @require_role()
    async def create_challenge_channel(ctx: discord_slash.SlashContext, category: str, challenge: str):
        cat = discord.utils.find(lambda c: c.name == category, ctx.guild.categories)
        created = await ctx.guild.create_text_channel(challenge, position=0, category=cat)
        await ctx.send(f"The channel for <#{created.id}> ({category}) was created")

    @slash.slash(name="solved",
                 description="The challenge was solved",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="flag",
                                   description="The flag that was obtained",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=False)
                     ]
                 )
    @require_role()
    async def mark_solved(ctx: discord_slash.SlashContext, flag: typing.Optional[str] = None):
        await ctx.defer()
        if not ctx.channel.name.startswith("✓"):
            await ctx.channel.edit(name=f"✓-{ctx.channel.name}", position=999)
        if flag is not None:
            msg = await ctx.send(f"The flag: `{flag}`")
            await msg.pin()
        await ctx.send("done", hidden=True)

    @slash.slash(name="archive",
                 description="Move all current challenges to a new archive",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="name",
                                   description="The name for the archive",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=True)
                     ]
                 )
    @require_role()
    async def archive(ctx: discord_slash.SlashContext, name: str):
        if ctx.guild is None:
            return
        await ctx.defer()
        new_cat = await ctx.guild.create_category(f"Archive-{name}", position=999)
        for cat in ctx.guild.categories:
            if cat.name not in config.mgmt.categories:
                continue
            for chan in cat.text_channels:
                await chan.edit(category=new_cat)
        await ctx.send(f"Archived {name}")

    @slash.slash(name="export",
                 description="Move the specified category to a nice new upstate farm.",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="category",
                                   description="Which category to move.",
                                   option_type=SlashCommandOptionType.CHANNEL,
                                   required=True)
                 ])
    @require_role()
    async def export(ctx: discord_slash.SlashContext, category: discord.abc.GuildChannel):
        # hacky but idc
        if ctx.deferred or ctx.responded:
            log.info("not sure why but handler called twice, ignoring")
            return
        if not isinstance(category, discord.CategoryChannel):
            log.info("Tried exporting non category channel %s", category.name)
            await ctx.send("Can only export categories, not normal channels!")
            return
        log.info("Exporting %s", category.name, exc_info=True)
        await ctx.defer()
        await trans_mgr.create(category, ctx)
        # # TODO: Support specifying timezone?
        # if ctx.guild is None:
        #     return
        # log.info("Exporting %s", ctx.channel.name)
        # transcript = await chat_exporter.export(ctx.channel, limit)

        # if transcript is None:
        #     log.error("Failed to create transcript!")
        #     await ctx.send("Failed to export channel!")
        #     return
        # filename = f"transcript_{ctx.channel.name}.html"
        # transcript_file = discord.File(io.BytesIO(transcript.encode()),
        #                                 filename=filename)
        # transcript_channel: discord.TextChannel = bot.get_channel(config.mgmt.transcript_channel)
        # msg = await transcript_channel.send(f"Transcript for {ctx.channel.name}", file=transcript_file)
        # await ctx.send(f"Transcript created [here]({msg.jump_url})")
    return bot


        

def run(loop: asyncio.AbstractEventLoop):
    bot = setup()
    bot.loop = loop
    loop.create_task(bot.start(config.bot.token))
