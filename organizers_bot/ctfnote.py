from gql import Client, gql
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
import discord_slash                                                            # type: ignore

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
        query = gql(queries.update_task)
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
        query = gql(queries.delete_task)
        result = await self.client.execute_async(query, variable_values={
            "id": self.id
        })
        await self.parent._fullupdate()

    async def startWorkingOn(self):
        """
        Mark this challenge as being worked on by this client
        """
        query = gql(queries.start_working_on)
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
        query = gql(queries.stop_working_on)
        try:
            result = await self.client.execute_async(query, variable_values={
                "taskId": self.id
            })
        except TransportQueryError:
            pass

    async def assignUser(self, userid: int):
        query = gql(queries.assign_user)
        result = await self.client.execute_async(query,variable_values={
            "taskId": self.id,
            "userId": userid
        })

    async def unassignUser(self, userid: int):
        query = gql(queries.unassign_user)
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
        query = gql(queries.get_full_ctf)
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

        return next(filter(lambda x: x.title == name, self.tasks))

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

        query = gql(queries.create_task)

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
            query = gql(queries.register_with_token)
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

            login = gql(queries.login_query)
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
        query = gql(queries.get_me)
        result = await self.client.execute_async(query)
        return result["me"]


    async def getTeam(self):
        """
        Retrieve the team you're in right now
        """
        query = gql(queries.get_team)
        result = await self.client.execute_async(query)
        return result["profiles"]["nodes"]

    async def getPastCtfs(self,first=20,offset=0):
        """
        Retrieve a list of past CTFs

        :ivar int first: Limit the results to the first few results
        :ivar int offset: Start search after the first offset many results
        """
        query = gql(queries.get_past_ctfs)
        result = await self.client.execute_async(query,variable_values={
            "first":first,
            "offset":offset
        })
        return result["pastCtf"]["nodes"]

    async def getIncomingCtfs(self):
        """
        Retrieve a list of upcoming CTFs
        """
        query = gql(queries.get_incoming_ctfs)
        result = await self.client.execute_async(query)
        return result["incomingCtf"]["nodes"]

    async def getCtfs(self):
        """
        Retrieve a list of all CTFs
        """
        query = gql(queries.get_ctfs)
        result = await self.client.execute_async(query)
        return result["ctfs"]["nodes"]

    async def _importCtf(self, id: int):
        """
        Imports the CTF given by the CTFTime id
        Creates a CTF even if the event with that CTFTime id already exists

        Thus don't use this method, use the checked one (importCTF without an
        underscore)
        """
        query = gql(queries.import_ctf)
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
        query = gql(queries.create_ctf)
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
        query = gql(queries.get_full_ctf)
            
        result = await self.client.execute_async(query, variable_values={
            "id": id
        })
        ctf = CTF(self.client, result["ctf"])
        return ctf
    
    async def createMemberAccount(self, user):
        """
        Creates a guest account invitation link
        """
        query = gql(queries.create_account)
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
        query = gql(queries.new_token)
        result = await self.client.execute_async(query)
        return result["newToken"]

    async def getUsers(self):
        query = gql(queries.get_users)
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

            async for event in ws_client.subscribe_async(gql(subscription)):
                print(name, event)

        loop.create_task(start_listening(queries.subscribe_flags, "flag"))
        loop.create_task(start_listening(queries.subscribe_to_ctf_created, "ctf_created"))
        loop.create_task(start_listening(queries.subscribe_to_ctf_deleted, "ctf_deleted"))
        loop.create_task(start_listening(queries.subscribe_to_ctf, "ctf_event"))
        loop.create_task(start_listening(queries.subscribe_to_task, "task_event"))


# These credentials can be changed with a bot command
URL = "http://cyanpencil.xyz:8099"
admin_login = "a"
admin_pass = "a"
ctfnote: CTFNote = CTFNote("")

async def login():
    global ctfnote
    ctfnote = CTFNote(URL + "/graphql")
    await ctfnote.login(admin_login, admin_pass)

async def refresh_ctf(ctx: discord_slash.SlashContext):
    global ctfnote
    if ctfnote is None or ctfnote.token is None: await login()
    current_ctf = await ctfnote.getActiveCtf()
    if current_ctf is None:
        await ctx.send("No active ctf! Go on ctfnote and fix the dates!")
    return current_ctf

async def update_login_info(ctx: discord_slash.SlashContext, URL_:str, admin_login_:str, admin_pass_:str):
    global URL, admin_pass, admin_login
    URL = URL_
    admin_pass = admin_pass_
    admin_login = admin_login_
    await login()
    await refresh_ctf(ctx)

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

async def add_task(ctx: discord_slash.SlashContext, created, name: str, category: str, flag: str = "", description: str = "", solved_prefix: str = "✓-"):
    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return
    result = await current_ctf.createTask(name, category, description, flag, solved_prefix = solved_prefix)
    if ctx is not None:
        # discord trick: <URL> does not show link previews, while URL does
        hackmd_url = "\nhackmd (in case the other is broken): " + f"<{URL}{result.url}>"
        ctfnote_url = "\nctfnote url: " + f"<{URL}/#/ctf/{current_ctf.id}-{current_ctf.name}/task/{result.id}-{result.title}>"
        msg = await created.send(ctfnote_url + hackmd_url)
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
    for person in task.people['nodes']:
        pid = person['profileId']
        await task.unassignUser(pid)
    print(task.people)
    await task.assignUser(user_id)
    await ctx.send(f"Player {playername.mention} was assigned to challenge {task.title}")

async def whos_leader_of_this_shit(ctx: discord_slash.SlashContext):
    current_ctf = await refresh_ctf(ctx) 
    if current_ctf is None: return


    task = await current_ctf.getTaskByName(ctx.channel.name)
    people = task.people['nodes']
    if len(people) > 0:
        user = people[0]['profile']['username']
        await ctx.send(f"{user} is this challenge lead. People are wondering how many ctf minutes until flag.")
    else:
        await ctx.send("No one is working on this challenge :(")



# print(await ctfnote.getUsers())
# print(asyncio.run(assign_player(None, "Lucidc#384")))

#
#

# print(asyncio.run(assign_player(None, "Lucidc#384")))
# print(asyncio.run(ctfnote.login("porco", "dio", "7c414386-d9c1-4341-8773-5d11a3e66885")))
