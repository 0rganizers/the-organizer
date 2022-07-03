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
from datetime import datetime, timezone
import logging
import asyncio
from . import queries
import discord
import discord_slash                                                            # type: ignore
import json

log = logging.getLogger("CTFNote")

class Task:
    def __init__(self, parent, client, meta):
        self.client = client
        self.parent = parent
        self.id = meta["id"]
        self.url = meta["padUrl"]
        self.desc = meta["description"]
        self.title = meta["title"]
        self.category = meta["category"]
        self.solved = meta["solved"]
        self.flag = meta["flag"]
        self.people = meta["workOnTasks"]

    def __repr__(self):
        return f"Task: {self.title} ({self.category}) @ {self.url}"

    async def _update(self):
        """
        Send the update of category, desc, flag, title
        """
        query = gql.gql(queries.update_task)
        result = await self.client.execute_async(query, variable_values={
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.desc,
            "flag": self.flag,
        })
        await self.parent._fullupdate()

    async def updateTitle(self, newtitle: str):
        """
        Update the title of the challenge
        """
        
        self.title = newtitle
        await self._update()

    async def updateFlag(self, newflag: str):
        """
        Update the title of the challenge
        """
        
        self.flag = newflag
        await self._update()

    async def delete(self):
        """
        Delete this Task from the tasklist
        """
        query = gql.gql(queries.delete_task)
        result = await self.client.execute_async(query, variable_values={
            "id": self.id
        })
        await self.parent._fullupdate()

    async def startWorkingOn(self):
        """
        Mark this challenge as being worked on by this client
        """
        query = gql.gql(queries.start_working_on)
        try:
            result = await self.client.execute_async(query, variable_values={
                "taskId": self.id
            })
        except TransportQueryError:
            pass

    async def stopWorkingOn(self):
        """
        Mark this challenge as no longer being worked on by this client
        """
        query = gql.gql(queries.stop_working_on)
        try:
            result = await self.client.execute_async(query, variable_values={
                "taskId": self.id
            })
        except TransportQueryError:
            pass

    async def assignUser(self, userid: int):
        query = gql.gql(queries.assign_user)
        result = await self.client.execute_async(query,variable_values={
            "taskId": self.id,
            "userId": userid
        })

    async def unassignUser(self, userid: int):
        query = gql.gql(queries.unassign_user)
        result = await self.client.execute_async(query,variable_values={
            "taskId": self.id,
            "userId": userid
        })
        


class CTF:
    """
    Represents a single CTF
    """
    def __init__(self, client, meta):
        self.client = client
        self._update(meta)

    def __repr__(self):
        return f"{self.url}"

    def _update(self, meta):
        self.id = meta["id"]
        self.url = meta["ctfUrl"]
        self.name = meta["title"]
        if "tasks" in meta:
            tasks = meta["tasks"]["nodes"]
            self.tasks = [Task(self, self.client, task) for task in tasks]
        else:
            self.tasks = []

    async def _fullupdate(self):
        query = gql.gql(queries.get_full_ctf)
        result = await self.client.execute_async(query, variable_values={
            "id": self.id
        })
        self._update(result["ctf"])

    async def getTask(self, id: int):
        if not self.tasks:
            await self._fullupdate()
        return next(filter(lambda x: x.id == id, self.tasks))

    async def getTaskByName(self, name: str, solved_prefix: str ="✓-"):
        """
            Problematic when there are spaces in the task title (but not the channel name).
            Problematic if two tasks have the same name.
            Prefer using getTaskByChannelPin where possible.
        """
        await self._fullupdate() # we always update bc we assume players have been creating new tasks
        # If the task was marked as solved, we need to ignore the prefix
        if name.startswith(solved_prefix):
            name = name[len(solved_prefix):]

        return next(filter(lambda x: x.title == name, self.tasks), None)

    async def getTaskByChannelPin(self, ctx: discord_slash.SlashContext):
        """
            Get task id from pinned message in current channel,
            find it in the ctfnote response, return it.
        """
        botdb = (await extract_botdb(await get_pinned_ctfnote_message(ctx)))
        stored_challenge_id = (botdb or dict()).get('chalid', None)
        await self._fullupdate()
        return next(filter(lambda x: x.id == stored_challenge_id, self.tasks), None)


    async def createTask(self, name, category, description="", flag="", solved_prefix: str = "✓-"):
        """
        Create a new task for this CTF
        """
        if name.startswith(solved_prefix):
            name = name[len(solved_prefix):]

        present_task = list(filter(lambda t: t.title == name and 
                t.category == category, self.tasks))
        if present_task:
            return present_task[0]

        query = gql.gql(queries.create_task)

        result = await self.client.execute_async(query, variable_values={
            "ctfId": self.id,
            "category": category,
            "title": name,
            "description": description,
            "flag": flag,
        })


        if not result["createTask"]:
            await self._fullupdate()

            present_task = list(filter(lambda t: t.title == name and 
                    t.category == category, self.tasks))
            return present_task[0]

        return result

class CTFNote:
    """
    Represents the CTFNote instance
    """
    def __init__(self, url):
        self.url = url
        self.token = None

    async def login(self, username, password, token=None):
        """
        Log into the CTFNote instance using Username and password or register a
        new account with username and password and the required token
        """
        transport = AIOHTTPTransport(url=self.url)
        client = Client(transport=transport, fetch_schema_from_transport=False)
        self.users = []

        if token:
            query = gql.gql(queries.register_with_token)
            result = await client.execute_async(query, variable_values={
                "login": username,
                "password": password,
                "token": token
            })

            self.token = result["registerWithToken"]["jwt"]
            self.transport = AIOHTTPTransport(
                    url=self.url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
            self.client = Client(
                    transport=self.transport, 
                    fetch_schema_from_transport=False
                )
        else:

            login = gql.gql(queries.login_query)
            result = await client.execute_async(login, variable_values={
                "login": username,
                "password": password
                })

            self.token = result["login"]["jwt"]
            self.transport = AIOHTTPTransport(
                    url=self.url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
            self.client = Client(
                    transport=self.transport, 
                    fetch_schema_from_transport=False
                )

    async def getMe(self):
        """
        Retrieve the current logged in account
        """
        query = gql.gql(queries.get_me)
        result = await self.client.execute_async(query)
        return result["me"]


    async def getTeam(self):
        """
        Retrieve the team you're in right now
        """
        query = gql.gql(queries.get_team)
        result = await self.client.execute_async(query)
        return result["profiles"]["nodes"]

    async def getPastCtfs(self,first=20,offset=0):
        """
        Retrieve a list of past CTFs

        :ivar int first: Limit the results to the first few results
        :ivar int offset: Start search after the first offset many results
        """
        query = gql.gql(queries.get_past_ctfs)
        result = await self.client.execute_async(query,variable_values={
            "first":first,
            "offset":offset
        })
        return result["pastCtf"]["nodes"]

    async def getIncomingCtfs(self):
        """
        Retrieve a list of upcoming CTFs. Seems to also contain currently ongoing CTFs.
        """
        query = gql.gql(queries.get_incoming_ctfs)
        result = await self.client.execute_async(query)
        return result["incomingCtf"]["nodes"]

    async def getCtfs(self):
        """
        Retrieve a list of all CTFs
        """
        query = gql.gql(queries.get_ctfs)
        result = await self.client.execute_async(query)
        return result["ctfs"]["nodes"]

    async def _importCtf(self, id: int):
        """
        Imports the CTF given by the CTFTime id
        Creates a CTF even if the event with that CTFTime id already exists

        Thus don't use this method, use the checked one (importCTF without an
        underscore)
        """
        query = gql.gql(queries.import_ctf)
        return await self.client.execute_async(query,variable_values={"id":id})

    async def importCtf(self, id: int):
        """
        imports a CTF with given CTFTime id, checks if the ctf is already
        present and doesn't add it if it is
        """
        for ctf in await self.getCtfs():
            if "ctftimeUrl" in ctf and ctf["ctftimeUrl"]:
                if not(ctf["ctftimeUrl"].endswith("/")):
                    ctf["ctftimeUrl"] += "/"
                try:
                    present_id = int(ctf["ctftimeUrl"].rsplit("/", 2)[1])
                except ValueError:
                    # parsing as an int failed
                    pass
                if present_id == id:
                    return {'importCtf': "Already present"}

        return await self._importCtf(id)

    async def importCtfFromCtftimeLinkOrId(self, link_or_id: str):
        """
        Extracts the ctftime id from the provided link if it is a ctftime link. 
        If it is already an ID, that will be used instead.

        raises ValueError if it seems to be neither an integer nor a valid ctftime event link
        """
        link_or_id = link_or_id.strip()
        # If all characters in the string are digits and it is not empty then we can immediately
        # call importCtf, otherwise need to get the id out of the link string first.
        if not(link_or_id.isdigit()):
            # If it is a link, we first strip off the begin that might vary, and then
            # check for the content
            if link_or_id.startswith('https://'):
                link_or_id = link_or_id[len('https://'):]

            if link_or_id.startswith('http://'):
                link_or_id = link_or_id[len('http://'):]

            ctftime_org_event = 'ctftime.org/event/'
            if not(link_or_id.startswith(ctftime_org_event)):
                # that does not seem like a reasonable ctftime ctf link.
                raise ValueError(f"Link does not start with {ctftime_org_event}")

            link_or_id = link_or_id[len(ctftime_org_event):]
            # Get rid of potential further slashes
            link_or_id = link_or_id.replace("/", "")

        return await self.importCtf(int(link_or_id))

    async def createCtf(self, name: str, start, end):
        """
        Create a new CTF with given name and start/end dates
        """
        query = gql.gql(queries.create_ctf)
        result = await self.client.execute_async(query, variable_values={
            "title": name,
            "startTime": str(start).split(".")[0].split("+")[0]+"Z",
            "endTime": str(end).split(".")[0].split("+")[0]+"Z",
            "description": "--",
            "logoUrl": None,
            "ctfUrl": None,
            "ctftimeUrl": None,
            "weight": 0,
        })

        return CTF(self.client, result["createCtf"]["ctf"])

    async def getFullCtf(self, id: int):
        """
        Get the full representation of the CTF with a given id
        """
        query = gql.gql(queries.get_full_ctf)
            
        result = await self.client.execute_async(query, variable_values={
            "id": id
        })
        ctf = CTF(self.client, result["ctf"])
        return ctf
    
    async def createMemberAccount(self, user):
        """
        Creates a guest account invitation link
        """
        query = gql.gql(queries.create_account)
        result = await self.client.execute_async(query, variable_values={
            "role": "USER_MEMBER"
        })
        token = result["createInvitationLink"]["invitationLinkResponse"]["token"]

        # password = "".join([choice(ascii_letters+digits) for _ in range(16)])
        password = "organizerssostrong" + str(randrange(1000, 9999))
        tmp = CTFNote(self.url)
        await tmp.login(user, password, token)
        new_acc = await tmp.getMe()

        return new_acc['id'], password

    async def newToken(self):
        query = gql.gql(queries.new_token)
        result = await self.client.execute_async(query)
        return result["newToken"]

    async def getUsers(self):
        query = gql.gql(queries.get_users)
        result = await self.client.execute_async(query)
        return result["users"]["nodes"]

    def getUserIdOf(self, username: str):
        if not self.users:
            self.users = self.getUsers()
        for user in self.users:
            if user["login"].lower() == username.lower():
                return user["id"]
        return 0

    async def getActiveCtfs(self):
        ctfs = await self.getIncomingCtfs()
        now = datetime.now(timezone.utc)
        ctfs = list(filter(lambda ctf: 
            datetime.fromisoformat(ctf["startTime"]) < now and
            datetime.fromisoformat(ctf["endTime"]) > now, ctfs))

        # This is a list. Use an element like this:
        # return CTF(self.client, ctfs[0]) if ctfs else None
        return ctfs

    async def subscribe_to_events(self):
        loop = asyncio.get_event_loop()
        token = await self.newToken()
        async def start_listening(subscription, name):
            url = "wss://"+self.url.split("://", 1)[1]
            transport = WebsocketsTransport(
                    url=url,
                    init_payload={"Authorization": f"Bearer {token}"}
                    )
            ws_client = Client(transport=transport)

            async for event in ws_client.subscribe_async(gql.gql(subscription)):
                print(name, event)

        loop.create_task(start_listening(queries.subscribe_flags, "flag"))
        loop.create_task(start_listening(queries.subscribe_to_ctf_created, "ctf_created"))
        loop.create_task(start_listening(queries.subscribe_to_ctf_deleted, "ctf_deleted"))
        loop.create_task(start_listening(queries.subscribe_to_ctf, "ctf_event"))
        loop.create_task(start_listening(queries.subscribe_to_task, "task_event"))


# These credentials can be changed with a bot command
# URL _must_ end with a slash
URL = "https://cyanpencil.xyz/note/"
admin_login = "a"
admin_pass = "b"
ctfnote: CTFNote = CTFNote("")
enabled: bool = False

async def login():
    global ctfnote
    ctfnote = CTFNote(URL + "graphql")
    await ctfnote.login(admin_login, admin_pass)

async def refresh_ctf(ctx: discord_slash.SlashContext, ctfid: int = None):
    """
        returns the current ctf object. It is determined based on the info in the pinned message
        of the channel with the given context, and if that is not specified then uses the first of
        the currently active CTFs.

        The argument `ctfid` overrides this ctf-selection behaviour.
    """
    global ctfnote
    # make sure ctfnote exists, we can connect to it, are logged in
    if ctfnote is None or ctfnote.token is None: 
        try:
            await login()
        except TransportQueryError:
            await ctx.send("Query failed. Check ctfnote credentials.")
            return None

    failure_msg = ""
    if ctfid is not None:
        stored_ctf_id = ctfid
        failure_msg = "Invalid ctf provided as argument."
    else:
        botdb = (await extract_botdb(await get_pinned_ctfnote_message(ctx)))
        stored_ctf_id = (botdb or dict()).get('ctfid', None)
        failure_msg = "Invalid ctf id saved in pinned message"

    if stored_ctf_id is not None:
        ctfs = await ctfnote.getCtfs()
        ctf_meta = next(filter(lambda ctf: str(ctf['id']) == str(stored_ctf_id), ctfs), None)
        if ctf_meta is None:
            await ctx.send(failure_msg)
            return None
        return CTF(ctfnote.client, ctf_meta)
    else:
        # if no ctf id is stored in the pinned message, we assume the first in the list of 
        # currently running CTFs is the right one
        current_ctfs = await ctfnote.getActiveCtfs()
        if current_ctfs is None or len(current_ctfs == 0):
            await ctx.send("No active ctf! Go on ctfnote and fix the dates!")
            return None
        if len(current_ctfs) > 1:
            await ctx.send("Multiple CTFs are currently ongoing. I was unable to infer the correct one from optional arguments and pinned messages.")
            return None
        # Just one current ctf is happening.
        return CTF(ctfnote.client, current_ctfs[0])

async def update_login_info(ctx: discord_slash.SlashContext, URL_:str, admin_login_:str, admin_pass_:str):
    global URL, admin_pass, admin_login, enabled
    URL = URL_
    
    # option to completely disable ctfnote interactions until login infos are updated again.
    if 'disable' == URL.lower() or 'disabled' == URL.lower() or '' == URL.lower():
        enabled = False
        await ctx.send("Disabled CTFNote integration.", hidden=False)
        return
    await ctx.defer(hidden=True)

    if not URL.endswith('/'):
        URL = f"{URL}/"
    admin_pass = admin_pass_
    admin_login = admin_login_
    try:
        await login()
    #except gql.transport.aiohttp.client_exceptions.InvalidURL as e:
    # I tried to be specific but it only exists once it crashes...
    except Exception as e:
        await ctx.send("No ctfnote for you. Can't reach the site or something.", hidden=True)
        enabled = False
        print(e)
        return

    # Test whether it worked
    current_ctfs = await ctfnote.getActiveCtfs()
    if current_ctfs is not None and ctfnote.token is not None:
        enabled = True
        await ctx.send("Success.", hidden=True)

async def update_flag(ctx: discord_slash.SlashContext, flag: str):
    """
        Updates the flag on ctfnote. To unset, simply set `flag` to the empty string.
        Handles the case where the channel name was marked as solved as well.
    """
    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return

    channel_name = ctx.channel.name
    update_flag_response = await current_ctf.getTaskByChannelPin(ctx)
    if update_flag_response is not None:
        update_flag_response = await update_flag_response.updateFlag(flag or "")
    return update_flag_response

def slugify(name:str):
    """
        turns an input string into something that is used in the ctftime urls for ctfs and tasks.
        For now, this is not completely equivalent to what they actually use. Ctfnote uses an
        npm package called slugify. We just do a best-effort approach here. If link generation fails
        in the bot, players should just use the web interface.
    """
    name = name.replace(" ", "-")
    return name

async def add_task(ctx: discord_slash.SlashContext, created, name: str,
        category: str, flag: str = "", description: str = "", 
        solved_prefix: str = "✓-", ctfid = None):
    """
        Creates a ctfnote task and pins it in the channel.
        Also stores the ctf id of the task in that message.
    """
    if not enabled:
        # no reaction from the ctfnote stuff please, they only wanted to create a channel
        return

    current_ctf = await refresh_ctf(ctx, ctfid = ctfid) 
    if current_ctf is None: return
    result = await current_ctf.createTask(name, category, description, flag, solved_prefix = solved_prefix)
    if ctx is not None:
        # discord trick: <URL> does not show link previews, while URL does
        ctfnote_url = "\nctfnote url: " + \
            f"<{URL}#/ctf/{current_ctf.id}-{slugify(current_ctf.name)}/task/{result.id}-{slugify(result.title)}>"
        hackmd_url = "\nhackmd (in case the other is broken): " + f"<{URL}{result.url}>"
        # we need to save the ctf id somewhere to distinguish between concurrent ctfs.
        # Note: the pinned message is identified by containing the word "botdb" and "ctfnote url:".
        botdb = json.dumps({
            'ctfid': current_ctf.id,
            'chalid': result.id,
            })
        bot_data_store = f"\n||botdb:{botdb}||"
        msg = await created.send(ctfnote_url + hackmd_url + bot_data_store)
        await msg.pin()

async def assign_player(ctx: discord_slash.SlashContext, playername):
    if not enabled:
        await ctx.send("CTFNote integration is currently not in use. Ignoring your request.", hidden=True)
        return

    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return

    all_users = await ctfnote.getUsers()
    uid = playername.name + '#' + playername.discriminator
    user =  list(filter(lambda x: x['login'] == uid, all_users))
    if len(user) == 0:
        user_id, password = await ctfnote.createMemberAccount(uid)
        await ctx.send(f"Account {playername} was created with password {password}")
    else:
        user_id = user[0]['id']

    task = await current_ctf.getTaskByChannelPin(ctx)
    if task is None:
        await ctx.send("This challenge does not exist on ctfnote.")
        return
    for person in task.people['nodes']:
        pid = person['profileId']
        await task.unassignUser(pid)
    #print(task.people)
    await task.assignUser(user_id)
    await ctx.send(f"Player {playername.mention} was assigned to challenge {task.title}")


async def fixup_task(ctx: discord_slash.SlashContext,
        ctfid: int, flag: str = "", description: str = "", 
        solved_prefix: str = "✓-"):
    """
    Finds, wipes, and recreates the pinned message.
    Useful if the channel was created without a ctf - or with a wrong ctf id.
    To be run with a context *in that channel*.
    """
    await ctx.defer(hidden=True)
    if not enabled:
        await ctx.send("Please enable ctfnote integration first. By specifying valid admin credentials with /ctfnote_update_auth.")
        return
    prev_pinned_msg = await get_pinned_ctfnote_message(ctx)
    reply_text = "Done."
    if prev_pinned_msg is not None:
        # remove the pinned message if it exists
        # TODO: also move the tasks around on ctfnote? Is probably easier to have them persist and let the players handle it themselves though. Usually the fixup will be called with a channel without any not yet anyway.
        await prev_pinned_msg.delete()
        reply_text += " Any previously used ctfnote md for this channel needs to be manually pasted over. It was not removed automatically."

    # Add task, with the correct ctfid
    task_name = ctx.channel.name[len(solved_prefix):] if ctx.channel.name.startswith(solved_prefix) else ctx.channel.name
    task_category = ctx.channel.category.name
    await add_task(ctx, created = ctx.channel, name = task_name, category = task_category,
            description = description, solved_prefix = solved_prefix, ctfid = ctfid)

    reply_text += " The new ctfid is " + str(ctfid) +"."

    await ctx.send(reply_text, hidden=True)


async def whos_leader_of_this_shit(ctx: discord_slash.SlashContext):
    if not enabled:
        await ctx.send("CTFNote integration is currently not in use. Ignoring your request. Set up the auth first.", hidden=True)
        return

    hide = True # reply will only be visible to *this* user.
    await ctx.defer(hidden=hide)
                           # We defer here just in case the refresh ctf could take a while.
                           # might not be needed.
    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return


    task = await current_ctf.getTaskByChannelPin(ctx)
    if task is None:
        await ctx.send("This challenge does not exist on ctfnote.", hidden=hide)
        return

    people = task.people['nodes']
    if len(people) > 0:
        user = people[0]['profile']['username']
        await ctx.send(f"{user} is this challenge lead. People are wondering how many ctf minutes until flag.", hidden=hide)
    else:
        await ctx.send("No one is working on this challenge :(", hidden=hide)

async def import_ctf_from_ctftime(ctx: discord_slash.SlashContext, ctftime_link_or_id: str):
    if not enabled:
        await ctx.send("CTFNote integration is currently not in use. Ignoring your request. Set up the auth first.", hidden=True)
        return


    hide = True
    await ctx.defer(hidden=hide)
    # For importing a CTF we need a logged in ctfnote object but not necessarily a current ctf.
    # Running refresh_ctf would complain if there is no currently active CTF. So we don't call that here.
    global ctfnote
    # make sure ctfnote exists, we can connect to it, are logged in
    if ctfnote is None or ctfnote.token is None: 
        try:
            await login()
        except TransportQueryError:
            await ctx.send("Query failed. Check ctfnote credentials.", hidden=hide)
            return None

    response = None
    try:
        response = await ctfnote.importCtfFromCtftimeLinkOrId(ctftime_link_or_id)
    except ValueError:
        await ctx.send("That link (or ctftime event id) did not work...", hidden=hide)
        return None

    if response.get('importCtf',False) == "Already present":
        await ctx.send(f"That ctf already exists. Check it in the dashboard(<{URL}>).", hidden=hide)
        return

    # TODO: it would be nice to receive the details of the ctf that was just imported. 
    #       Especially the ctfnote CTF id for use as optional argument of the /chal command.
    #       But that would require the server to actually return it... or to loop over all (incoming?) ctfs.

    #await ctx.send(f"Imported {response['title']} with weight {response['weight']} successfully. It has now id {response['id']}", hidden=hide)
    await ctx.send(f"Successfully imported. It should show up in the dashboard(<{URL}>) after a page reload.", hidden=hide)

async def get_pinned_ctfnote_message(ctx: discord_slash.SlashContext):
    """
        returns the first pinned message that looks like it matches the message the bot
        pins on channel creation.
        Returns None if no matching message found.
    """
    pins = await ctx.channel.pins() # this is a list of Message objects
    # https://discordpy.readthedocs.io/en/stable/api.html#discord.Message.content
    msg = next(filter(lambda pin: 
            'botdb:' in pin.content and
            'ctfnote url:' in pin.content
        , pins), None)

    return msg

async def extract_botdb(msg: discord.Message):
    """
        returns the botdb dict that was stored in the pinned message in the botdb: line.
        Can return None on failure.
    """
    if msg is None:
        return None
    # find the line with the botdb
    botdb_line = next(filter(lambda line: line.startswith('||botdb:'), msg.content.split('\n')), None)
    if botdb_line is None:
        return None
    # parse the data
    botdb_strs = botdb_line.split('||')
    assert len(botdb_strs) == 3
    botdb_str = botdb_strs[1][len('botdb:'):]
    try:
        botdb = json.loads(botdb_str)
    except ValueError:
        return None
    return botdb



# print(await ctfnote.getUsers())
# print(asyncio.run(assign_player(None, "Lucidc#384")))

#
#

# print(asyncio.run(assign_player(None, "Lucidc#384")))
# print(asyncio.run(ctfnote.login("porco", "dio", "7c414386-d9c1-4341-8773-5d11a3e66885")))
