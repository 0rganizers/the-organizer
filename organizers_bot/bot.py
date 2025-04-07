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

import traceback


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

    # the warning about using commands.Bot instead of discord.Client is explained here:
    # https://stackoverflow.com/a/51235308/2550406
    # It is mostly about convenience: commands.Bot subclasses discord.Client and offers some features.
    # I am not changing this now, since I see no urgent reason to do so.
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
                                      required=True),
                        create_option(name="ctfid",
                                      description="The int id of the ctf in ctfnote. Can be found in the URL.",
                                      option_type=SlashCommandOptionType.INTEGER,
                                      required=False)
                     ])
    @require_role(config.mgmt.player_role)
    async def create_challenge_channel(ctx: discord_slash.SlashContext, 
            category: str, challenge: str, ctfid = None):
        cat = discord.utils.find(lambda c: c.name == category, ctx.guild.categories)
        created = await ctx.guild.create_text_channel(challenge, position=0, category=cat)
        await ctx.send(f"The channel for <#{created.id}> ({category}) was created")
        await ctfnote.add_task(ctx, created, challenge, category, solved_prefix = "✓-", ctfid = ctfid)

    @slash.slash(name="optout",
                description="Opt-out of CTF participation.",
                guild_ids=[config.bot.guild])
    @require_role(config.mgmt.player_role)
    async def opt_out(ctx: discord_slash.SlashContext):
        member = ctx.author
        guild = ctx.guild

        optout_role = discord.utils.get(guild.roles, id=config.mgmt.optout_player_role)
        player_role = discord.utils.get(guild.roles, id=config.mgmt.player_role)

        if not optout_role or not player_role:
            await ctx.send("Error: roles are not configured correctly. Please contact an admin.", hidden=True)
            return

        if optout_role in member.roles:
            await ctx.send("You are already opted out.", hidden=True)
            return

        await member.add_roles(optout_role, reason=f"User opted out via /optout command")
        await member.remove_roles(player_role, reason=f"User opted out via /optout command")

        await ctx.send(f"You have successfully opted out.")


    @slash.slash(name="optin",
                description="Opt-in to CTF participation.",
                guild_ids=[config.bot.guild])
    @require_role(config.mgmt.optout_player_role)
    async def opt_in(ctx: discord_slash.SlashContext):
        member = ctx.author
        guild = ctx.guild

        optout_role = discord.utils.get(guild.roles, id=config.mgmt.optout_player_role)
        player_role = discord.utils.get(guild.roles, id=config.mgmt.player_role)

        if not optout_role or not player_role:
            await ctx.send("Error: roles are not configured correctly. Please contact an admin.", hidden=True)
            return

        if player_role not in member.roles:
            await member.add_roles(player_role, reason=f"User opted in via /optout command")

        await member.remove_roles(optout_role, reason=f"User opted in via /optout command")

        await ctx.send(f"Welcome back!")

    @slash.slash(name="ctfnote_fixup_channel",
                 description="Use this if you need to set/change the ctfnote id of the current channel after the channel creation.",
                 guild_ids=[config.bot.guild],
                 options=[
                        create_option(name="ctfid",
                                      description="The int id of the ctf in ctfnote. Can be found in the URL.",
                                      option_type=SlashCommandOptionType.INTEGER,
                                      required=False)
                     ])
    @require_role(config.mgmt.player_role)
    async def ctfnote_fixup_channel(ctx: discord_slash.SlashContext, ctfid = None):
        await ctfnote.fixup_task(ctx, solved_prefix = "✓-", ctfid = ctfid)

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
    @require_role(config.mgmt.player_role)
    async def mark_solved(ctx: discord_slash.SlashContext, flag: typing.Optional[str] = None):
        await ctx.defer()
        if not ctx.channel.name.startswith("✓"):
            await ctx.channel.edit(name=f"✓-{ctx.channel.name}", position=999)

        ctfnote_res = await ctfnote.update_flag(ctx, flag)

        if flag is not None:
            msg = await ctx.send(f"The flag: `{flag}`")
            await msg.pin()
        else:
            await ctx.send("removed flag.")

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
    @require_role(config.mgmt.player_role)
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
    @require_role(config.mgmt.player_role)
    async def export(ctx: discord_slash.SlashContext, category: discord.abc.GuildChannel):
        # hacky but idc
        # lucid: It seems this can be fixed by updating discordpy and discord_slash.
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

    @slash.slash(name="ctfnote_assign_lead",
                 description="Assign given player as challenge lead for this channel",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="playername",
                                   description="The player that becomes leader",
                                   option_type=SlashCommandOptionType.USER,
                                   required=True),
                 ])
    @require_role(config.mgmt.player_role)
    async def ctfnote_update_assigned_player(ctx: discord_slash.SlashContext, playername: discord.member.Member):
        await ctfnote.assign_player(ctx, playername)

    @slash.slash(name="ctfnote_register_myself",
                 description="Register yourself a ctfnote account",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="password",
                                   description="Autogenerated if unspecified",
                                   option_type=SlashCommandOptionType.STRING,
                                   required=False),
                 ])
    @require_role(config.mgmt.player_role)
    async def ctfnote_register_myself(ctx: discord_slash.SlashContext, password: str = None):
        await ctfnote.register_themselves(ctx, password or None)

    @slash.slash(name="ctfnote_who_leads",
                 description="Ping who's the current leader of this challenge",
                 guild_ids=[config.bot.guild])
    @require_role(config.mgmt.player_role)
    async def ctfnote_leader(ctx: discord_slash.SlashContext):
        await ctfnote.whos_leader_of_this_shit(ctx)

    @slash.slash(name="ctfnote_import",
                 description="Create a new CTF in ctfnote by providing a ctftime event link or id.",
                 guild_ids=[config.bot.guild],
                 options=[
                     create_option(name="link",
                         description="Link or event id on ctftime",
                         option_type=SlashCommandOptionType.STRING,
                         required=True),
                     ])
    @require_role(config.mgmt.player_role)
    async def ctfnote_import_from_ctftime(ctx: discord_slash.SlashContext, link: str):
        await ctfnote.import_ctf_from_ctftime(ctx, link)

    @slash.slash(name="stats",
                 description="Display some useful stats about the server, such as number of channels",
                 guild_ids=[config.bot.guild])
    async def stats(ctx: discord_slash.SlashContext):
        log.info("Running Stats command")
        num_channels = len(ctx.guild.channels)
        num_cats = 0
        for chan in ctx.guild.channels:
            log.debug("Channel: %s", chan.name)
            chan: discord.abc.GuildChannel
            if isinstance(chan, discord.CategoryChannel):
                num_cats += 1
        
        await ctx.send(f"Channels: {num_channels}/500, {500 - num_channels} left\nCategories: {num_cats}")

    ## Keep this last :)
    return bot

def run(loop: asyncio.AbstractEventLoop):
    bot = setup()
    bot.loop = loop
    loop.create_task(bot.start(config.bot.token))
