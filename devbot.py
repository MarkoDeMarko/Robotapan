import sys, asyncio, discord, time, json, os
from discord.ext import commands
from pprint import pprint
from enum import Enum

config = None
userPerms = None
embeds = None

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

class permLevels(Enum):
    noAccess = -1
    default = 0
    trusted = 1
    operator = 2
    administrator = 3
    superadministrator = 4

def permissionCheck(reqPerm:int):
    def predicate(ctx):
        try:
            if userPerms[str(ctx.author.id)] == -1:
                #asyncio.get_event_loop().create_task(ctx.send(f"You do not have permission to use any of this bot's commands, {ctx.author.mention}"))
                return False
        except:
            if reqPerm == 0:#if the try statement catches an error then the author must have the default permLevel (0)
                return True
            else:
                #asyncio.get_event_loop().create_task(ctx.send(f"You do not have sufficient permissions for this action, {ctx.author.mention}"))
                return False
        if userPerms[str(ctx.author.id)] >= reqPerm:
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
        self.bot.loop.create_task(self.spawnSubs())

    
    async def spawnSubs(self):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()
            
        for data in config["subbots"]:
            channel = self.bot.get_channel(data["channel"])
            sub = voiceSender(self.bot.user.name, channel, data["token"])
            sub.task = self.bot.loop.create_task(sub.start())
            self.players[channel] = sub


    @commands.command()
    @permissionCheck(4)
    async def quit(self, ctx):
        raise KeyboardInterrupt


    @commands.command(hidden=True)
    @permissionCheck(4)
    async def test(self, ctx):
        pass
    
            
class permissions:
    @commands.group(invoke_without_command=True)
    async def perms(self, ctx):
        await ctx.send("```No subcommand of perms was passed.\nUsage: !perms set <member> <permLevel> or !perms get [members...]\nFor more information use !help perms <subCommand>```")


    @perms.command(name="set", description=config["help"]["permsSet"].format(prefix="!"))
    @permissionCheck(3)
    async def perms_set(self, ctx, member: discord.Member, permLevel : int):
        authorPerm = permLevels(userPerms[str(ctx.author.id)])
        try:
            memberPerm = permLevels(userPerms[str(member.id)])
        except:
            memberPerm = permLevels(0)

        if not authorPerm.value > permLevel:
            await ctx.send(f"You do not have sufficient permissions for this action, {ctx.author.mention}")
        elif not memberPerm.value < authorPerm.value:
            await ctx.send(f"{member.mention}'s permission level is higher than or equal to {ctx.author.mention}, no change can be made")
        else:
            userPerms[str(member.id)] = permLevel
            await ctx.send(f"{member.mention} now has permission level {permLevel}")
            save_permissions()

    @perms.command(name="get")
    @permissionCheck(2)
    async def perms_get(self, ctx, *members:discord.Member):
        for member in members:
            try:
                memberPerm = permLevels(userPerms[str(member.id)])
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
        def __init__(self, name, description, reqPerm, maxPerUser):
            self.name = name
            self.reqPerm = reqPerm
            self.maxPerUser = maxPerUser
            self.message = None
            self.embed = discord.Embed()

        def add(self, entry, author):
            self.embed.add_field(name=entry, value=f"Added by {author}")

        def remove(self, index):
            return self.entries.pop(index - 1)

        async def send(self, pin=False):
            if self.message:
                return False
            embed 


class polls:
    def __init__(self):
        self.current = []

    @commands.command()
    @permissionCheck(0)
    async def poll(self, ctx, *args):
        pass

    @commands.group(invoke_without_command=True)
    @permissionCheck(0)
    async def activepoll(self, ctx):
        await ctx.send("```No subcommand of activepoll was passed.\nUsage: !activepoll <subcommand> [args...]\nFor more information use !help activepoll <subCommand>```")

    @activepoll.command(name="create")
    @permissionCheck(3)
    async def activepoll_create(self, ctx, name, reqPerm:int, maxPerUser:int, ):
        pass

    @activepoll.command(name="add")
    @permissionCheck(0)
    async def activepoll_add(self, ctx):
        pass


class music:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @permissionCheck(0)
    async def play(self, ctx, *, song : str):
        pass

    @commands.command()
    @permissionCheck(0)
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
