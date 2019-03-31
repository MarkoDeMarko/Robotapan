import sys, asyncio, discord, time, datetime, json, os
from discord.ext import commands
from pprint import pprint
from enum import Enum
from num2words import num2words

config = None
userPerms = None

def load(name):
    global config, userPerms, embeds
    if name == "config":
        fileName = "config.json"
    elif name == "perms":
        fileName = "permissions.json"
    else:
        return False

    with open(os.path.join(os.path.dirname(__file__), fileName), "r") as f:
        new = json.load(f)

    if new:
        if name == "config":
            config = new
        elif name == "perms":
            userPerms = new
        return True
    else:
        return False

def save(name, variable):
    if name == "config":
        fileName = "config.json"
    elif name == "perms":
        fileName = "permissions.json"
    else:
        return False
    with open(os.path.join(os.path.dirname(__file__), fileName), "w") as f:
        json.dump(variable, f, indent=4, separators=(',', ': '))


if not load("config"):
    print("Failed to load configuration")
    sys.exit()

if not load("perms"):
    print("Failed to load permissions")
    sys.exit()

class permLevel(Enum):
    noAccess = -1
    default = 0
    trusted = 1
    operator = 2
    administrator = 3
    superadministrator = 4

def permissionCheck(reqPerm : permLevel):
    def predicate(ctx):
        try:
            if permLevel(userPerms[str(ctx.author.id)]) == permLevel.noAccess:
                #asyncio.get_event_loop().create_task(ctx.send(f"You do not have permission to use any of this bot's commands, {ctx.author.mention}"))
                return False
        except:
            if reqPerm == permLevel.default:#if the try statement catches an error then the author must have the default permLevel (0)
                return True
            else:
                #asyncio.get_event_loop().create_task(ctx.send(f"You do not have sufficient permissions for this action, {ctx.author.mention}"))
                return False
        if userPerms[str(ctx.author.id)] >= reqPerm.value:
            return True
        else:
            #asyncio.get_event_loop().create_task(ctx.send(f"You do not have sufficient permissions for this action, {ctx.author.mention}"))
            return False
    return commands.check(predicate)


class baseBot:
    def __init__(self, bot, token):
        self.bot = bot
        self.token = token
        if token == config["maintoken"]:
            self.name = "Main"
        else:
            for data in config["subbots"]:
                if token == data["token"]:
                    self.name = data["name"]
                    self.bot.command_prefix = commands.when_mentioned_or(data["prefix"])

    def sPrint(self, *args, **kwargs):
        print(self.name+">::", " ".join(map(str,args)), **kwargs)

    async def on_ready(self):
        self.sPrint(f'Logged in as: {self.bot.user.name}')
        self.sPrint(f"ID: {self.bot.user.id}")
        self.sPrint('Servers: ', end='')
        for guild in self.bot.guilds:
            print(str(guild), end=' : ')
        print("\n")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def reloadConfig(self, ctx):
        if load("config"):
            await ctx.send("```Configuration successfully reloaded```")
        else:
            await ctx.send("```Configuration reload unsuccessful```")

        if load("perms"):
            await ctx.send("```Permissions successfully reloaded```")
        else:
            await ctx.send("```Permission reload unsuccessful```")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def test(self, ctx):
        pass

class voiceEntry():
    def __init__(self, requester, name, song):
        self.requester = requester
        self.name = name
        self.song = song

    async def playSong(self):
        pass


class voiceSender(baseBot):
    def __init__(self, parentName, channel, token):
        super().__init__(commands.Bot(command_prefix=commands.when_mentioned_or("?"), description="Audio Player controlled by {}".format(parentName)), token)
        self.bot.add_cog(self)
        self.channel = channel
        self.playlist = asyncio.Queue()
        self.connection = None
        self.current = None

        self.bot.loop.create_task(self.runPlaylist())

    async def on_ready(self):
        await super().on_ready()
        await self.bot.change_presence(status=discord.Status.invisible)

    async def start(self):
        await self.bot.start(self.token)

    async def runPlaylist(self):
        while True:
            entry = await self.playlist.get()
            self.current = entry.name
            #setplayingstatus(self.current)

            if self.connection == None:
                self.connection == await self.channel.connect()

            await entry.song#plays the song

            if self.playlist.qsize() == 0:
                return
                await self.connection.disconnect()
                self.connection = None
                await self.bot.change_presence(status=discord.Status.invisible)

    async def player(self, name, file):
        pass



class mainBot(baseBot):
    def __init__(self):
        super().__init__(
            commands.Bot(command_prefix=commands.when_mentioned_or('!'), description=''),
            config["maintoken"]
            )

        cogs = [
            self,
            permissions(),
            polls(),
            music(self.bot)
        ]
        for cog in cogs:
            self.bot.add_cog(cog)

        self.players = {}
        #self.bot.loop.create_task(self.spawnSubs())


    async def spawnSubs(self):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()

        for data in config["subbots"]:
            channel = self.bot.get_channel(data["channel"])
            sub = voiceSender(self.bot.user.name, channel, data["token"])
            sub.task = self.bot.loop.create_task(sub.start())
            self.players[channel] = sub


    @commands.command()
    @permissionCheck(permLevel.superadministrator)
    async def stop(self, ctx):
        raise KeyboardInterrupt


    @commands.command(hidden=True)
    @permissionCheck(permLevel.superadministrator)
    async def test(self, ctx):
        entries = [
            {"value": "It should be like this", "author": ctx.author},
            {"value": "Nah it should be like this", "author": self.bot.user}
        ]

        description = ""
        for i, entry in enumerate(entries):
            end = ""
            if entry["author"]:
                end = f", {entry['author'].mention}"
            description += f"**{i+1}.** \"{entry['value']}\"{end}\n"

        curTime = datetime.datetime(*[time.gmtime()[i] for i in range(6)])

        embed = discord.Embed(
            title=":bar_chart:** How should this poll look? **:bar_chart:",
            description=description, timestamp=curTime)
        embed.set_footer(text=f"Created by {ctx.author.name}")
        message = await ctx.send(embed=embed)

        for i in range(len(entries)):
            await message.add_reaction(f"{i+1}\u20e3")

class permissions:
    @commands.group(invoke_without_command=True)
    async def perms(self, ctx):
        await ctx.send("```No subcommand of perms was passed.\nUsage: !perms set <member> <permLevel> or !perms get [members...]\nFor more information use !help perms <subCommand>```")


    @perms.command(name="set", description=config["help"]["permsSet"].format(prefix="!"))
    @permissionCheck(permLevel.administrator)
    async def perms_set(self, ctx, member: discord.Member, permLevel : int):
        authorPerm = permLevel(userPerms[str(ctx.author.id)])
        try:
            memberPerm = permLevel(userPerms[str(member.id)])
        except:
            memberPerm = permLevel.default

        if not authorPerm.value > permLevel:
            await ctx.send(f"You do not have sufficient permissions for this action, {ctx.author.mention}")
        elif not memberPerm.value < authorPerm.value:
            await ctx.send(f"{member.mention}'s permission level is higher than or equal to {ctx.author.mention}, no change can be made")
        else:
            userPerms[str(member.id)] = permLevel
            await ctx.send(f"{member.mention} now has permission level {permLevel}")
            save_permissions()

    @perms.command(name="get")
    @permissionCheck(permLevel.operator)
    async def perms_get(self, ctx, *members:discord.Member):
        for member in members:
            try:
                memberPerm = permLevel(userPerms[str(member.id)])
            except:
                await ctx.send(f"{member} is a default user")
            else:
                if memberPerm.value == -1:
                    await ctx.send(f"{member} has no access to any commands")
                elif memberPerm.value in [0, 1]:
                    await ctx.send(f"{member} is a {memberPerm.name} user")
                else:
                    await ctx.send(f"{member} has {memberPerm.name} permissions")


class pollInstance:
        def __init__(self, ctx, pollID, name, reqPerm):
            self.name = name
            self.reqPerm = reqPerm
            self.message = None
            self.id = pollID

            self.date = datetime.datetime(*[time.gmtime()[i] for i in range(6)])
            self.entries = []

            self.embed = discord.Embed(
                title=f":bar_chart: **{name}** :bar_chart:",
                timestamp=self.date
                )
            self.embed.set_footer(text=f"Created by {ctx.author.name} • id:{self.id}")

        def createDescription(self):
            description = ""
            for i, entry in enumerate(self.entries):
                end = ""
                if entry["author"]:
                    end = f", {entry['author'].mention}"
                description += f"**{i+1}.** \"{entry['value']}\"{end}\n"
            return description

        def add(self, entry, author):
            self.entries.append({"entry":entry, "author"=author})

        def remove(self, index):
            return self.embed.remove_field(index - 1)

        async def send(self, channel, pin=False):
            if self.message:
                return False


class polls:
    def __init__(self):
        self.current = {}

    def create_ID(self):
        ID = str(len(self.current.keys()))
        if len(ID) == 1:
            ID = "0" + ID
        return ID

    @commands.command()
    @permissionCheck(permLevel.default)
    async def poll(self, ctx, name, *alternatives):
        poll = pollInstance(ctx, name, self.create_ID(), 0)
        for value in alternatives:
            poll.add(value, None)
        poll.createDescription()
        poll.send()

    @commands.group(invoke_without_command=True)
    @permissionCheck(permLevel.default)
    async def activepoll(self, ctx):
        await ctx.send("```No subcommand of activepoll was passed.\nUsage: !activepoll <subcommand> [args...]\nFor more information use !help activepoll <subCommand>```")

    @activepoll.command(name="create")
    @permissionCheck(permLevel.operator)
    async def activepoll_create(self, ctx, name, reqPerm:int=0, *options):
        entries = []
        for value in options:
            entries.append({"value":value, "name": None})
        poll = pollInstance(ctx, name, reqPerm, entries)



    @activepoll.command(name="add")
    @permissionCheck(permLevel.default)
    async def activepoll_add(self, ctx, *, entry):
        if ctx.channel not in self.current.keys():
            await ctx.send(f"There is currently not an Active Poll ongoing in this channel, {ctx.author.mention}")


class music:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @permissionCheck(permLevel.default)
    async def play(self, ctx, *, song : str):
        pass

    @commands.command()
    @permissionCheck(permLevel.default)
    async def pause(self, ctx):
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            if channel in self.players.keys():
                if self.check_permission(ctx.author):
                    pass
            else:
                await ctx.send("{} is not a valid channel, {}".format(channel.name, ctx.author.mention))
        else:
            await ctx.send("You are not in a voice channel, {}".format(ctx.author.mention))

client = mainBot()
client.bot.run(client.token)
