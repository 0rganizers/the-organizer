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
        await self._fullupdate() # we always update bc we assume players have been creating new tasks
        # If the task was marked as solved, we need to ignore the prefix
        if name.startswith(solved_prefix):
            name = name[len(solved_prefix):]

        return next(filter(lambda x: x.title == name, self.tasks), None)

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
        Retrieve a list of upcoming CTFs
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
            try:
                if "ctftimeUrl" in ctf and ctf["ctftimeUrl"]:
                    present_id = int(ctf["ctftimeUrl"].rsplit("/", 2)[1])
                    if present_id == id:
                        return {'importCtf': "Already present"}
            except ValueError:
                pass

        return await self._importCtf(id)

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

    async def getActiveCtf(self):
        ctfs = await self.getIncomingCtfs()
        now = datetime.now(timezone.utc)
        ctfs = list(filter(lambda ctf: 
            datetime.fromisoformat(ctf["startTime"]) < now and
            datetime.fromisoformat(ctf["endTime"]) > now, ctfs))

        if len(ctfs) > 1: # TODO: select any of the current scheduled ctfs?
            log.warn("Multiple CTFs active, only taking the first one!")
            ctfs = ctfs[:1]

        return CTF(self.client, ctfs[0]) if ctfs else None

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

    if ctfid is not None:
        stored_ctf_id = ctfid
    else:
        botdb = (await extract_botdb(await get_pinned_ctfnote_message(ctx)))
        stored_ctf_id = (botdb or dict()).get('ctfid', None)

    if stored_ctf_id is not None:
        ctfs = await ctfnote.getCtfs()
        ctf_meta = next(filter(lambda ctf: str(ctf['id']) == str(stored_ctf_id), ctfs), None)
        if ctf_meta is None:
            await ctx.send("Invalid ctf id saved in pinned message.")
            return None
        return CTF(ctfnote.client, ctf_meta)
    else:
        # if no ctf id is stored in the pinned message, we assume the first in the list of 
        # currently running CTFs is the right one
        current_ctf = await ctfnote.getActiveCtf()
        if current_ctf is None:
            await ctx.send("No active ctf! Go on ctfnote and fix the dates!")
        return current_ctf

async def update_login_info(ctx: discord_slash.SlashContext, URL_:str, admin_login_:str, admin_pass_:str):
    global URL, admin_pass, admin_login
    URL = URL_
    if not URL.endswith('/'):
        URL = f"{URL}/"
    admin_pass = admin_pass_
    admin_login = admin_login_
    try:
        await login()
        current_ctf = await refresh_ctf(ctx)
    #except gql.transport.aiohttp.client_exceptions.InvalidURL as e:
    # I tried to be specific but it only exists once it crashes...
    except Exception as e:
        await ctx.send("No ctfnote for you. Can't reach the site or something.")
        print(e)
        return

    if current_ctf is not None and ctfnote.token is not None:
        await ctx.send("Success.")

async def update_flag(ctx: discord_slash.SlashContext, flag: str, solved_prefix="✓-"):
    """
        Updates the flag on ctfnote. To unset, simply set `flag` to the empty string.
        Handles the case where the channel name was marked as solved as well.
    """
    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return

    channel_name = ctx.channel.name
    update_flag_response = await current_ctf.getTaskByName(channel_name, solved_prefix=solved_prefix)
    if update_flag_response is not None:
        update_flag_response = await update_flag_response.updateFlag(flag or "")
    return update_flag_response

async def add_task(ctx: discord_slash.SlashContext, created, name: str,
        category: str, flag: str = "", description: str = "", 
        solved_prefix: str = "✓-", ctfid = None):
    """
        Creates a ctfnote task and pins it in the channel.
        Also stores the ctf id of the task in that message.
    """
    current_ctf = await refresh_ctf(ctx, ctfid = ctfid) 
    if current_ctf is None: return
    result = await current_ctf.createTask(name, category, description, flag, solved_prefix = solved_prefix)
    if ctx is not None:
        # discord trick: <URL> does not show link previews, while URL does
        ctfnote_url = "\nctfnote url: " + f"<{URL}#/ctf/{current_ctf.id}-{current_ctf.name}/task/{result.id}-{result.title}>"
        hackmd_url = "\nhackmd (in case the other is broken): " + f"<{URL}{result.url}>"
        # we need to save the ctf id somewhere to distinguish between concurrent ctfs.
        # Note: the pinned message is identified by containing the word "botdb" and "ctfnote url:".
        botdb = json.dumps({
            'ctfid': current_ctf.id,
            })
        bot_data_store = f"\n||botdb:{botdb}||"
        msg = await created.send(ctfnote_url + hackmd_url + bot_data_store)
        await msg.pin()

async def assign_player(ctx: discord_slash.SlashContext, playername):
    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return

    all_users = await ctfnote.getUsers()
    uid = playername.name + '#' + playername.discriminator
    user =  list(filter(lambda x: x['login'] == uid, all_users))
    if len(user) == 0:
        user_id, password = await ctfnote.createMemberAccount(uid)
        await ctx.send(f"Account {playername} was created with password {password}")
    else:
        print("done")
        user_id = user[0]['id']

    task = await current_ctf.getTaskByName(ctx.channel.name)
    if task is None:
        await ctx.send("This challenge does not exist on ctfnote.")
        return
    for person in task.people['nodes']:
        pid = person['profileId']
        await task.unassignUser(pid)
    #print(task.people)
    await task.assignUser(user_id)
    await ctx.send(f"Player {playername.mention} was assigned to challenge {task.title}")

async def whos_leader_of_this_shit(ctx: discord_slash.SlashContext):
    hide = True # reply will only be visible to *this* user.
    await ctx.defer(hidden=hide)
                           # We defer here just in case the refresh ctf could take a while.
                           # might not be needed.
    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return


    task = await current_ctf.getTaskByName(ctx.channel.name)
    if task is None:
        await ctx.send("This challenge does not exist on ctfnote.", hidden=hide)
        return

    people = task.people['nodes']
    if len(people) > 0:
        user = people[0]['profile']['username']
        await ctx.send(f"{user} is this challenge lead. People are wondering how many ctf minutes until flag.", hidden=hide)
    else:
        await ctx.send("No one is working on this challenge :(", hidden=hide)

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
