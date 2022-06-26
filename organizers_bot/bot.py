from . import config
from . import transcript
from . import ctfnote

import asyncio
import functools
import hashlib
import io
import logging
import typing
import os

import discord                                                                  # type: ignore
import discord_slash                                                            # type: ignore
from discord_slash.utils.manage_commands import create_option, create_choice    # type: ignore
from discord_slash.model import SlashCommandOptionType                          # type: ignore


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

    intents = discord.Intents.default()
    intents.members = True
    bot = discord.Client(intents=intents)
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
        await ctfnote.add_task(ctx, created, challenge, category)

    @slash.slash(name="solved",
                 description="The challenge was solved",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="flag",
                                   description="The flag that was obtained",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=True)
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

    @slash.slash(name="nuke",
                 description="Remove all channels in a given category, destructive. Use /export first!",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="category",
                                   description="Which category to nuke.",
                                   option_type=SlashCommandOptionType.CHANNEL,
                                   required=True),
                     create_option(name="confirm",
                                   description="Are you really sure? Did you /export it?",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=False)
                     ])
    @require_role(config.mgmt.admin_role)
    async def nuke(ctx: discord_slash.SlashContext, category: discord.abc.GuildChannel, confirm: str = None):
        if not isinstance(category, discord.CategoryChannel):
            await ctx.send("That's not a category, buddy...", hidden=True)
            return
        reference = hashlib.sha256((category.name + str(category.position)).encode()).hexdigest()
        if reference != confirm:
            await ctx.send(f"Are you ***REALLY*** sure you performed the /export for {category.name}?? If so, use this as confirmation code: {reference}", hidden=True)
            return
        await ctx.defer()
        for chan in category.channels:
            await chan.delete(reason=f"Nuked by {ctx.author.name} with #{category.name}")
        await category.delete(reason=f"Nuked by {ctx.author.name}")
        await ctx.send(f"Category {category.name} was nuked on request of {ctx.author.name}", hidden=False)



    @slash.slash(name="ctfnote_update_auth",
                 description="Update url and auth login info for the ctfnote integration",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="url",
                                   description="The url ctfnote is hosted at",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=True),
                     create_option(name="adminlogin",
                                   description="Admin login password",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=True),
                     create_option(name="adminpass",
                                   description="Admin login password",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=True)
                     ])
    @require_role(config.mgmt.player_role)
    async def ctfnote_update_auth(ctx: discord_slash.SlashContext, url:str, adminlogin:str, adminpass:str):
        await ctfnote.update_login_info(ctx, url, adminlogin, adminpass)

    @slash.slash(name="ctfnote_assign_player",
                 description="Assign given player as challenge lead for this channel",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="playername",
                                   description="The player that becomes leader",
                                   option_type=SlashCommandOptionType.USER,
                                   required=True),
                 ])
    @require_role(config.mgmt.player_role)
    async def ctfnote_update_auth(ctx: discord_slash.SlashContext, playername: discord.member.Member):
        await ctfnote.assign_player(ctx, playername)

    @slash.slash(name="ctfnote_who_leads",
                 description="Ping who's the current leader of this challenge",
                 guild_ids=[config.bot.guild])
    @require_role(config.mgmt.player_role)
    async def ctfnote_leader(ctx: discord_slash.SlashContext):
        await ctfnote.whos_leader_of_this_shit(ctx)

    ## Keep this last :)
    return bot

def run(loop: asyncio.AbstractEventLoop):
    bot = setup()
    bot.loop = loop
    loop.create_task(bot.start(config.bot.token))
