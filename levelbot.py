import os
import discord
import math
from discord.ext import tasks, commands
from discord.ext.commands import MissingPermissions
from discord.utils import get
from dotenv import load_dotenv
from discord import app_commands
import mariadb
import logging, sys
from enum import Enum

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
handler = logging.StreamHandler(sys.stdout)

bot = commands.Bot(command_prefix="^", intents=discord.Intents.all())

dbconfig = {"host": "localhost", "user": "PROFOAK", "password": "", "database": "db1"}
pool = mariadb.ConnectionPool(pool_size=5, pool_name="mypool", **dbconfig)
mydb = pool.get_connection()
cur = mydb.cursor()


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    denominator="Set the denominator for the level up formula(default 2)",
    levelmsg="Set a custom level up message for your server",
)
async def setting(
    interaction: discord.Interaction, denominator: int = None, levelmsg: str = None
):
    """set custom variables for your server"""
    guild = interaction.guild
    if denominator != None:
        cur.execute(
            f"INSERT INTO db1.{guild.id}_2(rolepath, role_id) VALUES('denominator','{denominator}') ON DUPLICATE KEY UPDATE role_id = '{denominator}'"
        )
    if levelmsg != None:
        cur.execute(
            f"ALTER TABLE db1.{guild.id}_2 ADD COLUMN IF NOT EXISTS levelmsg varchar(200)"
        )
        cur.execute(
            f"INSERT INTO db1.{guild.id}_2(rolepath, levelmsg) VALUES('levelmsg', '{levelmsg}') ON DUPLICATE KEY UPDATE levelmsg = '{levelmsg}'"
        )
    await interaction.response.send_message(
        "You updated server variables", ephemeral=True
    )


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    user="The user you wish to change the points for",
    points="How many points you want this user to have",
)
async def adjust(interaction: discord.Interaction, user: discord.Member, points: int):
    """Adjust a server members points (admin only)"""
    guildid = interaction.guild.id
    cur.execute(
        f"UPDATE db1.{guildid} SET user_points = '{points}' WHERE user_id = '{user.id}'"
    )
    await interaction.response.send_message(
        f"{user}'s points have been set to {points}, their level will update after they send a message.",
        ephemeral=True,
    )
    mydb.commit()
    mydb.close()


def is_me(interaction: discord.Interaction) -> bool:
    return interaction.user.id == 416738006511124480


@app_commands.command()
@app_commands.check(is_me)
async def update(interaction: discord.Interaction, update: str):
    """Bot owner command to push update notifications"""
    for guild in bot.guilds:
        cur.execute(f"SELECT * FROM db1.{guild.id}_2 WHERE rolepath = 'updates'")
        results = cur.fetchone()
        if results != None:
            channel = bot.get_channel(int(results[1]))
            embed = discord.Embed(title="New Update", description=update)
            await channel.send(embed=embed)
    await interaction.response.send_message("Update sent", ephemeral=True)
    mydb.close()


class helplist(Enum):
    roles = 0
    other = 1


@app_commands.command()
@app_commands.describe(topic="The topic you need help on")
async def help(interaction: discord.Interaction, topic: helplist):
    """Confused on how to set variables or use this bot?"""
    if topic == helplist.roles:
        embed = discord.Embed(
            color=discord.Color.red(),
            title="**__ROLES HELP MENU__**",
            description='This bot has the capability to set different role "paths" for your members to follow. This command is how you set those roles for said "paths" and sometimes this confuses people. I will try to break it down for you here.\n-Rolebase: this role is a temporary role given to someone at level 2 which allows them to interact with the role select menu. something like "Pick A Role" would be fitting.\n-PathXRole1: This is the first of 3 roles assigned when selecting the X role path. The name of this role will also be visible on the role selection buttons.\n-PathXrole2: This is the second of 3 roles assigned when selecting the X role path.\n-PathXrole3: This is the third of 3 roles assigned when selecting the X role path and the final role in said path. It is recommended to assign better priveleges to the role associated with role 3 in each path. \n\nUpon reaching the third role in a path the role selection menu will appear again, prompting the member to select another path to follow until they have achieved the 3rd role in each of the 3 paths.\n\nThe only persistent roles assigned are the final roles in each path, the others will be removed upon reaching the next role\n\nThe levels at which roles are assigned are:\n2-rolebase (until you pick a role)\n10-role 2 in the selected path, role 1 is removed\n17- role 3 in the selected path, role 2 is removed and you get to select another path, subsequently assigning yourself role 1 in the new path\n20- role 2 in the selected path, role 1 is removed.\n24- role 3 in the selected path, role 2 is removed and you get to select another path, subsequently assigning yourself role 1 in the new path\n26- role 2 in the selected path, role 1 is removed\n30- role 3 in the final role path is achieved, role 2 is removed and you now have the highest role in all 3 paths\n\n**YOU NEED TO HAVE ALL 10 ROLES ASSIGNED TO USE THE ROLE MENU FEATURE** otherwise you will get the standard level up messages.',
        )
        await interaction.response.send_message(embed=embed)
    if topic == helplist.other:
        embed = discord.Embed(
            color=discord.Color.red(),
            title="**__HELP MENU__**",
            description="**/setting** is how you set a custom level up message for your server or adjust the difficulty of leveling up via the denominator of the level calculation. denominator default is 2. If you wish to mention the user leveling up in the message use {mention} and if you wish to display the level they made it to, use {level} in your custom message\n**/leaderboard** displays the top 10 users in your server\n**/level** displays your current level and points on this server\n**/adjust** allows server admins to adjust member points\n**/newpath** allows you to select a new role path if your server uses the split tree level system in this bot. This works if you have role 1 or 2 in a path or missed your menu while leveling up.\n**/notifchannel** sets a channel in your server for botspam to be sent to. this channel will also recieve updates in the future when I add to this bot.\n**/ping** check the bots latency.\n**/rank** checks your rank in the server\n**/roles** is how you set up your role tree in your server to use the split tree level system in this bot. That can be complicated so i have a seperate help menu for that command.\n\n**help server** please join this server for more help with this bot - https://discord.gg/Z9RJSn55uC",
        )
        await interaction.response.send_message(embed=embed)


@app_commands.command()
@app_commands.describe(member="The user you want to see server rank for")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    """Display your rank or another users rank in the server"""
    guild = interaction.guild.id
    if member == None:
        userid = interaction.user.id
        icon = interaction.user.display_avatar
        dname = interaction.user.display_name
    else:
        userid = member.id
        icon = member.display_avatar
        dname = member.display_name
    name = interaction.user.name
    cur.execute(f"CREATE TEMPORARY TABLE db1.temp LIKE db1.tempex;")
    cur.execute(
        f"INSERT INTO db1.temp (user_id, user_name, user_level, user_points) SELECT * FROM db1.{guild} ORDER BY user_points DESC;"
    )
    cur.execute(f"SELECT * FROM db1.temp WHERE user_id = '{userid}'")
    results = cur.fetchone()
    embed = discord.Embed(
        color=discord.Color.blue(),
    )
    embed.set_author(
        name=dname, url=f"https://discord.com/users/{userid}", icon_url=icon
    )
    if results == None:
        await interaction.response.send_message(
            "Theres a time and place for everything, but not now."
        )
        mydb.close()
    else:
        embed.add_field(name="Rank:", value=results[4], inline=True)
        await interaction.response.send_message(embed=embed)
        mydb.close()
    print(f"{name} used the /rank command")
    mydb.close()


@app_commands.command()
@app_commands.describe(member="The user you want to see server level for")
async def level(interaction: discord.Interaction, member: discord.Member = None):
    """Display your level on this server."""
    if member == None:
        userid = interaction.user.id
        icon = interaction.user.display_avatar
        dname = interaction.user.display_name
    else:
        userid = member.id
        icon = member.display_avatar
        dname = member.display_name
    guild = interaction.guild.id
    name = interaction.user.name
    cur.execute(f"SELECT * FROM db1.{guild} WHERE user_id = {userid}")
    results = cur.fetchone()
    embed = discord.Embed(
        color=discord.Color.teal(),
    )
    embed.set_author(
        name=dname, url=f"https://discord.com/users/{userid}", icon_url=icon
    )
    if results == None:
        await interaction.response.send_message(
            "Theres a time and place for everything, but not now."
        )
    else:
        embed.add_field(name="Points:", value=results[3], inline=False)
        embed.add_field(name="Level:", value=results[2], inline=False)
        await interaction.response.send_message(embed=embed)
    print(f"{name} used the /level command")
    mydb.close()


@bot.event
async def on_guild_remove(guild):
    cur.execute(f"DROP TABLE db1.{guild.id}")
    cur.execute(f"DROP TABLE db1.{guild.id}_2")
    print(f"left guild {guild.id}")
    mydb.commit()
    mydb.close()


@bot.event
async def on_guild_join(guild):
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS db1.{guild.id} (user_id varchar(19) NOT NULL, user_name varchar(32) DEFAULT NULL, user_level bigint(20) DEFAULT NULL, user_points bigint(20) DEFAULT NULL, PRIMARY KEY (user_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    print(f"Compiled main table for new guild: {guild.name}, {guild.id}")
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS db1.{guild.id}_2 (rolepath varchar(19) NOT NULL, role_id varchar(19) DEFAULT NULL, role_name varchar(100) DEFAULT NULL, PRIMARY KEY (rolepath))"
    )
    print(f"Compiled role table for new guild: {guild.name}, {guild.id}")
    cur.execute(f"SELECT * FROM db1.{guild.id}_2")
    results = cur.fetchall()
    cur.execute(
        f"INSERT IGNORE INTO db1.{guild.id}_2 (rolepath) VALUES ('rolebase'), ('path1role1'), ('path1role2'), ('path1role3'), ('path2role1'), ('path2role2'), ('path2role3'), ('path3role1'), ('path3role2'), ('path3role3'), ('botchannel')"
    )
    print(f"Compiled role table values for new guild: {guild.name}, {guild.id}")
    mydb.commit()
    mydb.close()


class Altroles(discord.ui.View):
    def __init__(self, original_inter: discord.Interaction) -> None:
        super().__init__()
        guildid = original_inter.guild.id
        cur.execute(
            f"SELECT * FROM db1.{guildid}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path2role1' OR rolepath = 'path3role1'"
        )
        results = cur.fetchall()
        res1 = results[0]
        res11 = res1[1]
        roleid1 = int(res11)
        res2 = results[1]
        res22 = res2[1]
        roleid2 = int(res22)
        res3 = results[2]
        res33 = res3[1]
        roleid3 = int(res33)
        btn1 = get(original_inter.guild.roles, id=roleid1)
        btn2 = get(original_inter.guild.roles, id=roleid2)
        btn3 = get(original_inter.guild.roles, id=roleid3)
        self.btn1.label = f"{btn1}"
        self.btn2.label = f"{btn2}"
        self.btn3.label = f"{btn3}"
        self.inter = original_inter
        self.user = original_inter.user
        self.channel = original_inter.channel

    async def interaction_check(self, interaction):
        if interaction.user != self.user:
            await interaction.channel.send(
                f"Whoa there Team Rocket Grunt <@{interaction.user.id}>, you can't steal other people's role menu!"
            )
        else:
            return True

    async def on_timeout(self) -> None:
        print("menu has timed out")
        self.btn1.disabled = True
        self.btn2.disabled = True
        self.btn3.disabled = True
        await self.inter.edit_original_response(view=self)
        await self.channel.send(f"<@{self.user.id}> your role menu has timed out")

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def btn1(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildid = interaction.guild.id
        cur.execute(
            f"SELECT * FROM db1.{guildid}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path1role2' OR rolepath = 'path2role1' OR rolepath = 'path2role2' OR rolepath = 'path3role1' OR rolepath = 'path3role2' OR rolepath = 'rolebase'"
        )
        results = cur.fetchall()
        res0 = results[0]
        res11 = res0[1]
        roleid11 = int(res11)
        res1 = results[1]
        res12 = res1[1]
        roleid12 = int(res12)
        res2 = results[2]
        res21 = res2[1]
        roleid21 = int(res21)
        res3 = results[3]
        res22 = res3[1]
        roleid22 = int(res22)
        res4 = results[4]
        res31 = res4[1]
        roleid31 = int(res31)
        res5 = results[5]
        res32 = res5[1]
        roleid32 = int(res32)
        res6 = results[6]
        resrb = res6[1]
        rolebase = int(resrb)
        p1r1 = get(interaction.guild.roles, id=roleid11)
        p1r2 = get(interaction.guild.roles, id=roleid12)
        p2r1 = get(interaction.guild.roles, id=roleid21)
        p2r2 = get(interaction.guild.roles, id=roleid22)
        p3r1 = get(interaction.guild.roles, id=roleid31)
        p3r2 = get(interaction.guild.roles, id=roleid32)
        rb = get(interaction.guild.roles, id=rolebase)
        if rb in interaction.user.roles:
            await interaction.user.remove_roles(rb)
            await interaction.user.add_roles(p1r1)
            await interaction.response.send_message(f"You've selected {p1r1}!")
            self.btn1.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p1r1 in interaction.user.roles:
            await interaction.response.send_message(
                "You've already selected this role path!"
            )
        elif p1r2 in interaction.user.roles:
            await interaction.response.send_message(
                "You've already selected this role path!"
            )
        elif p2r1 in interaction.user.roles:
            await interaction.user.remove_roles(p2r1)
            await interaction.user.add_roles(p1r1)
            await interaction.response.send_message(
                f"You've switched from {p2r1} to {p1r1}!"
            )
            self.btn1.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p2r2 in interaction.user.roles:
            await interaction.user.remove_roles(p2r2)
            await interaction.user.add_roles(p1r2)
            await interaction.response.send_message(
                f"You've switched from {p2r2} to {p1r2}!"
            )
            self.btn1.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p3r1 in interaction.user.roles:
            await interaction.user.remove_roles(p3r1)
            await interaction.user.add_roles(p1r1)
            await interaction.response.send_message(
                f"You've switched from {p3r1} to {p1r1}!"
            )
            self.btn1.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p3r2 in interaction.user.roles:
            await interaction.user.remove_roles(p3r2)
            await interaction.user.add_roles(p1r2)
            await interaction.response.send_message(
                f"You've swtiched from {p3r2} to {p1r2}!"
            )
            self.btn1.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        else:
            await interaction.response.send_message(
                f"You need one of the following roles to interact with this menu:\n {rb}\n {p1r1}\n {p1r2}\n {p2r1}\n {p2r2}\n {p3r1}\n {p3r2}"
            )
            self.btn1.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()

    @discord.ui.button(style=discord.ButtonStyle.blurple, row=2)
    async def btn2(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildid = interaction.guild.id
        cur.execute(
            f"SELECT * FROM db1.{guildid}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path1role2' OR rolepath = 'path2role1' OR rolepath = 'path2role2' OR rolepath = 'path3role1' OR rolepath = 'path3role2' OR rolepath = 'rolebase'"
        )
        results = cur.fetchall()
        res0 = results[0]
        res11 = res0[1]
        roleid11 = int(res11)
        res1 = results[1]
        res12 = res1[1]
        roleid12 = int(res12)
        res2 = results[2]
        res21 = res2[1]
        roleid21 = int(res21)
        res3 = results[3]
        res22 = res3[1]
        roleid22 = int(res22)
        res4 = results[4]
        res31 = res4[1]
        roleid31 = int(res31)
        res5 = results[5]
        res32 = res5[1]
        roleid32 = int(res32)
        res6 = results[6]
        resrb = res6[1]
        rolebase = int(resrb)
        p1r1 = get(interaction.guild.roles, id=roleid11)
        p1r2 = get(interaction.guild.roles, id=roleid12)
        p2r1 = get(interaction.guild.roles, id=roleid21)
        p2r2 = get(interaction.guild.roles, id=roleid22)
        p3r1 = get(interaction.guild.roles, id=roleid31)
        p3r2 = get(interaction.guild.roles, id=roleid32)
        rb = get(interaction.guild.roles, id=rolebase)
        if rb in interaction.user.roles:
            await interaction.user.remove_roles(rb)
            await interaction.user.add_roles(p2r1)
            await interaction.response.send_message(f"You've selected {p2r1}!")
            self.btn2.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p1r1 in interaction.user.roles:
            await interaction.user.remove_roles(p1r1)
            await interaction.user.add_roles(p2r1)
            await interaction.response.send_message(
                f"You've switched from {p1r1} to {p2r1}!"
            )
            self.btn2.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p1r2 in interaction.user.roles:
            await interaction.user.remove_roles(p1r2)
            await interaction.user.add_roles(p2r2)
            await interaction.response.send_message(
                f"You've switched from {p1r2} to {p2r2}!"
            )
            self.btn2.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p2r1 in interaction.user.roles:
            await interaction.response.send_message(
                "You've already selected this role path!"
            )
        elif p2r2 in interaction.user.roles:
            await interaction.response.send_message(
                "You've already selected this role path!"
            )
        elif p3r1 in interaction.user.roles:
            await interaction.user.remove_roles(p3r1)
            await interaction.user.add_roles(p2r1)
            await interaction.response.send_message(
                f"You've switched from {p3r1} to {p2r1}!"
            )
            self.btn2.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p3r2 in interaction.user.roles:
            await interaction.user.remove_roles(p3r2)
            await interaction.user.add_roles(p2r2)
            await interaction.response.send_message(
                f"You've swtiched from {p3r2} to {p2r2}!"
            )
            self.btn2.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        else:
            await interaction.response.send_message(
                f"You need one of the following roles to interact with this menu:\n {rb}\n {p1r1}\n {p1r2}\n {p2r1}\n {p2r2}\n {p3r1}\n {p3r2}"
            )
            self.btn2.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()

    @discord.ui.button(style=discord.ButtonStyle.green, row=3)
    async def btn3(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildid = interaction.guild.id
        cur.execute(
            f"SELECT * FROM db1.{guildid}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path1role2' OR rolepath = 'path2role1' OR rolepath = 'path2role2' OR rolepath = 'path3role1' OR rolepath = 'path3role2' OR rolepath = 'rolebase'"
        )
        results = cur.fetchall()
        res0 = results[0]
        res11 = res0[1]
        roleid11 = int(res11)
        res1 = results[1]
        res12 = res1[1]
        roleid12 = int(res12)
        res2 = results[2]
        res21 = res2[1]
        roleid21 = int(res21)
        res3 = results[3]
        res22 = res3[1]
        roleid22 = int(res22)
        res4 = results[4]
        res31 = res4[1]
        roleid31 = int(res31)
        res5 = results[5]
        res32 = res5[1]
        roleid32 = int(res32)
        res6 = results[6]
        resrb = res6[1]
        rolebase = int(resrb)
        p1r1 = get(interaction.guild.roles, id=roleid11)
        p1r2 = get(interaction.guild.roles, id=roleid12)
        p2r1 = get(interaction.guild.roles, id=roleid21)
        p2r2 = get(interaction.guild.roles, id=roleid22)
        p3r1 = get(interaction.guild.roles, id=roleid31)
        p3r2 = get(interaction.guild.roles, id=roleid32)
        rb = get(interaction.guild.roles, id=rolebase)
        if rb in interaction.user.roles:
            await interaction.user.remove_roles(rb)
            await interaction.user.add_roles(p3r1)
            await interaction.response.send_message(f"You've selected {p3r1}!")
            self.btn3.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p1r1 in interaction.user.roles:
            await interaction.user.remove_roles(p1r1)
            await interaction.user.add_roles(p3r1)
            await interaction.response.send_message(
                f"You've switched from {p1r1} to {p3r1}!"
            )
            self.btn3.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p1r2 in interaction.user.roles:
            await interaction.user.remove_roles(p1r2)
            await interaction.user.add_roles(p3r2)
            await interaction.response.send_message(
                f"You've switched from {p1r2} to {p3r2}!"
            )
            self.btn3.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p2r1 in interaction.user.roles:
            await interaction.user.remove_roles(p2r1)
            await interaction.user.add_roles(p3r1)
            await interaction.response.send_message(
                f"You've swtiched from {p2r1} to {p3r1}!"
            )
            self.btn3.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p2r2 in interaction.user.roles:
            await interaction.user.remove_roles(p2r2)
            await interaction.user.add_roles(p3r2)
            await interaction.response.send_message(
                f"You've swtiched from {p2r2} to {p3r2}!"
            )
            self.btn3.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()
        elif p3r1 in interaction.user.roles:
            await interaction.response.send_message(
                "You've already selected this role path!"
            )
        elif p3r2 in interaction.user.roles:
            await interaction.response.send_message(
                "You've already selected this role path!"
            )
        else:
            await interaction.response.send_message(
                f"You need one of the following roles to interact with this menu:\n {rb}\n {p1r1}\n {p1r2}\n {p2r1}\n {p2r2}\n {p3r1}\n {p3r2}"
            )
            self.btn3.disabled = True
            await self.inter.edit_original_response(view=self)
            self.stop()


@app_commands.command()
async def newpath(interaction: discord.Interaction) -> None:
    """Select a new role path"""
    guildid = interaction.guild.id
    cur.execute(
        f"SELECT * FROM db1.{guildid}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path2role1' OR rolepath = 'path3role1'"
    )
    results = cur.fetchall()
    res1 = results[0]
    res2 = results[1]
    res3 = results[2]
    print(f"{interaction.user.name} used /newpath")
    if res1[1] == None or res2[1] == None or res3[1] == None:
        await interaction.response.send_message(
            "This server does not have rolepaths set up!"
        )
    elif res1[1] == "" or res2[1] == "" or res3[1] == "":
        await interaction.response.send_message(
            "This server does not have rolepaths set up!"
        )
    else:
        await interaction.response.send_message(
            "Please select a new role path to follow", view=Altroles(interaction)
        )


class Roles(discord.ui.View):
    def __init__(self, original_inter: discord.Interaction) -> None:
        super().__init__(timeout=600)
        guildid = original_inter.guild.id
        self.guild = original_inter.guild
        cur.execute(
            f"SELECT * FROM db1.{guildid}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path2role1' OR rolepath = 'path3role1'"
        )
        results = cur.fetchall()
        res1 = results[0]
        res11 = res1[1]
        roleid1 = int(res11)
        res2 = results[1]
        res22 = res2[1]
        roleid2 = int(res22)
        res3 = results[2]
        res33 = res3[1]
        roleid3 = int(res33)
        btn1 = get(original_inter.guild.roles, id=roleid1)
        btn2 = get(original_inter.guild.roles, id=roleid2)
        btn3 = get(original_inter.guild.roles, id=roleid3)
        self.btn1.label = f"{btn1}"
        self.btn2.label = f"{btn2}"
        self.btn3.label = f"{btn3}"
        self.inter = original_inter
        self.author = original_inter.author
        self.channel = original_inter.channel

    async def interaction_check(self, interaction):
        if interaction.user != self.author:
            await interaction.channel.send(
                f"Whoa there Team Rocket Grunt <@{interaction.user.id}>, you can't steal other people's role menu!"
            )
        else:
            return True

    async def on_timeout(self) -> None:
        print("menu has timed out")
        await self.channel.send(
            f"<@{self.author.id}> your role menu has timed out! you can select a new role path later with </newpath:1033762182330060880>"
        )
        for item in self.children:
            item.disabled = True
        #        await self.inter.edit_original_response(view=self)
        #        await self.inter.edit(view=self)
        cur.execute(f"SELECT * FROM db1.{self.guild.id}_2 WHERE rolepath = 'rolebase'")
        results = cur.fetchone()
        roleid = int(results[1])
        await self.author.add_roles(discord.Object(id=roleid))
        mydb.close()

    @discord.ui.button(style=discord.ButtonStyle.red, row=1)
    async def btn1(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild.id
        cur.execute(
            f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'rolebase' OR rolepath = 'path1role3' OR rolepath = 'path2role3' OR rolepath = 'path3role3' OR rolepath = 'path1role1'"
        )
        res = cur.fetchall()
        rb = res[4]
        p1 = res[1]
        p2 = res[2]
        p3 = res[3]
        r1 = res[0]
        roleb = int(rb[1])
        rolebase = get(interaction.guild.roles, id=roleb)
        p1r = int(p1[1])
        p1r3 = get(interaction.guild.roles, id=p1r)
        p2r = int(p2[1])
        p2r3 = get(interaction.guild.roles, id=p2r)
        p3r = int(p3[1])
        p3r3 = get(interaction.guild.roles, id=p3r)
        roleid = int(r1[1])
        rolename = get(interaction.guild.roles, id=roleid)
        if rolebase in interaction.user.roles:
            await interaction.user.add_roles(rolename)
            await interaction.user.remove_roles(rolebase)
            await interaction.response.send_message(
                content=f"You selected {rolename}", ephemeral=True
            )
            self.btn1.disabled = True
            await interaction.followup.edit_message(
                message_id=interaction.message.id, view=self
            )
            self.stop()
        elif p1r3 in interaction.user.roles:
            await interaction.response.send_message(
                content=f"You've already completed this role path, please make another selection.",
                ephemeral=True,
            )
        elif p2r3 in interaction.user.roles:
            if p1r3 in interaction.user.roles:
                await interaction.response.send_message(
                    content=f"You've already completed this role path, please make another selection.",
                    ephemeral=True,
                )
            else:
                await interaction.user.add_roles(rolename)
                await interaction.response.send_message(
                    content=f"You selected {rolename}", ephemeral=True
                )
                self.btn1.disabled = True
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
                self.stop()
        elif p3r3 in interaction.user.roles:
            if p1r3 in interaction.user.roles:
                await interaction.response.send_message(
                    content=f"You've already completed this role path, please make another selection.",
                    ephemeral=True,
                )
            else:
                await interaction.user.add_roles(rolename)
                await interaction.response.send_message(
                    content=f"You selected {rolename}", ephemeral=True
                )
                self.btn1.disabled = True
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
                self.stop()
        else:
            await interaction.response.send_message(
                content=f"Theres a time and place for everything, but not now.",
                ephemeral=True,
            )
        print(f"{interaction.user.name} selected btn1")
        mydb.close()

    @discord.ui.button(style=discord.ButtonStyle.blurple, row=2)
    async def btn2(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild.id
        cur.execute(
            f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'rolebase' OR rolepath = 'path1role3' OR rolepath = 'path2role3' OR rolepath = 'path3role3' OR rolepath = 'path2role1'"
        )
        res = cur.fetchall()
        rb = res[4]
        p1 = res[0]
        p2 = res[2]
        p3 = res[3]
        r2 = res[1]
        roleb = int(rb[1])
        rolebase = get(interaction.guild.roles, id=roleb)
        p1r = int(p1[1])
        p1r3 = get(interaction.guild.roles, id=p1r)
        p2r = int(p2[1])
        p2r3 = get(interaction.guild.roles, id=p2r)
        p3r = int(p3[1])
        p3r3 = get(interaction.guild.roles, id=p3r)
        roleid = int(r2[1])
        rolename = get(interaction.guild.roles, id=roleid)
        if rolebase in interaction.user.roles:
            await interaction.user.add_roles(rolename)
            await interaction.user.remove_roles(rolebase)
            await interaction.response.send_message(
                content=f"You selected {rolename}", ephemeral=True
            )
            self.btn2.disabled = True
            await interaction.followup.edit_message(
                message_id=interaction.message.id, view=self
            )
            self.stop()
        elif p1r3 in interaction.user.roles:
            if p2r3 in interaction.user.roles:
                await interaction.response.send_message(
                    content=f"You've already completed this role path, please make another selection.",
                    ephemeral=True,
                )
            else:
                await interaction.user.add_roles(rolename)
                await interaction.response.send_message(
                    content=f"You selected {rolename}", ephemeral=True
                )
                self.btn2.disabled = True
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
                self.stop()
        elif p2r3 in interaction.user.roles:
            await interaction.response.send_message(
                content=f"You've already completed this role path, please make another selection.",
                ephemeral=True,
            )
        elif p3r3 in interaction.user.roles:
            if p2r3 in interaction.user.roles:
                await interaction.response.send_message(
                    content=f"You've already completed this role path, please make another selection.",
                    ephemeral=True,
                )
            else:
                await interaction.user.add_roles(rolename)
                await interaction.response.send_message(
                    content=f"You selected {rolename}", ephemeral=True
                )
                self.btn2.disabled = True
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
                self.stop()
        else:
            await interaction.response.send_message(
                content=f"There's a time and place for everything, but not now.",
                ephemeral=True,
            )
        print(f"{interaction.user.name} selected btn2")
        mydb.close()

    @discord.ui.button(style=discord.ButtonStyle.green, row=3)
    async def btn3(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild.id
        cur.execute(
            f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'rolebase' OR rolepath = 'path1role3' OR rolepath = 'path2role3' OR rolepath = 'path3role3' OR rolepath = 'path3role1'"
        )
        res = cur.fetchall()
        rb = res[4]
        p1 = res[0]
        p2 = res[1]
        p3 = res[3]
        r3 = res[2]
        roleb = int(rb[1])
        rolebase = get(interaction.guild.roles, id=roleb)
        p1r = int(p1[1])
        p1r3 = get(interaction.guild.roles, id=p1r)
        p2r = int(p2[1])
        p2r3 = get(interaction.guild.roles, id=p2r)
        p3r = int(p3[1])
        p3r3 = get(interaction.guild.roles, id=p3r)
        roleid = int(r3[1])
        rolename = get(interaction.guild.roles, id=roleid)
        if rolebase in interaction.user.roles:
            await interaction.user.add_roles(rolename)
            await interaction.user.remove_roles(rolebase)
            await interaction.response.send_message(
                content=f"You selected {rolename}", ephemeral=True
            )
            self.btn3.disabled = True
            await interaction.followup.edit_message(
                message_id=interaction.message.id, view=self
            )
            self.stop()
        elif p1r3 in interaction.user.roles:
            if p3r3 in interaction.user.roles:
                await interaction.response.send_message(
                    content=f"You've already completed this role path, please make another selection.",
                    ephemeral=True,
                )
            else:
                await interaction.user.add_roles(rolename)
                await interaction.response.send_message(
                    content=f"You selected {rolename}", ephemeral=True
                )
                self.btn3.disabled = True
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
                self.stop()
        elif p2r3 in interaction.user.roles:
            if p3r3 in interaction.user.roles:
                await interaction.response.send_message(
                    content=f"You've already completed this role path, please make another selection.",
                    ephemeral=True,
                )
            else:
                await interaction.user.add_roles(rolename)
                await interaction.response.send_message(
                    content=f"You selected {rolename}", ephemeral=True
                )
                self.btn3.disabled = True
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
                self.stop()
        elif p3r3 in interaction.user.roles:
            await interaction.response.send_message(
                content=f"You've already completed this role path, please make another selection.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                content=f"There's a time and place for everything, but not now.",
                ephemeral=True,
            )
        print(f"{interaction.user.name} selected btn3")
        mydb.close()


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    lvlchannel="The channel you want notifications for members leveling up",
    updates="The channel you want bot update message to be sent to",
)
async def notifchannel(
    interaction: discord.Interaction,
    lvlchannel: discord.TextChannel = None,
    updates: discord.TextChannel = None,
):
    """Set the Notification channels for level up or bot updates."""
    guild = interaction.guild.id
    if lvlchannel != None:
        cur.execute(
            f"UPDATE db1.{guild}_2 SET role_id = {lvlchannel.id}, role_name='{lvlchannel.name}' WHERE rolepath = 'botchannel'"
        )
        await interaction.response.send_message(
            "Your server's botchannel has been updated", ephemeral=True
        )
    if updates != None:
        cur.execute(
            f"INSERT INTO db1.{guild}_2 (rolepath, role_id, role_name) VALUES ('updates', '{updates.id}', '{updates.name}') ON DUPLICATE KEY UPDATE role_id = '{updates.id}', role_name = '{updates.name}'"
        )
        await interaction.response.send_message(
            "Your server's update channel has been updated", ephemeral=True
        )
    mydb.commit()
    mydb.close()
    print(f"{interaction.user.name} updated botchannel")


@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    rolebase="The base role for using the Path command",
    path1role1="path1role1",
    path1role2="path1role2",
    path1role3="path1role3",
    path2role1="path2role1",
    path2role2="path2role2",
    path2role3="path2role3",
    path3role1="path3role1",
    path3role2="path3role2",
    path3role3="path3role3",
)
async def roles(
    interaction: discord.Interaction,
    rolebase: discord.Role = None,
    path1role1: discord.Role = None,
    path1role2: discord.Role = None,
    path1role3: discord.Role = None,
    path2role1: discord.Role = None,
    path2role2: discord.Role = None,
    path2role3: discord.Role = None,
    path3role1: discord.Role = None,
    path3role2: discord.Role = None,
    path3role3: discord.Role = None,
):
    """Insert role IDs for the bot to award during leveling"""
    guild = interaction.guild.id
    if not any(
        {
            rolebase,
            path1role1,
            path1role2,
            path1role3,
            path2role1,
            path2role2,
            path2role3,
            path3role1,
            path3role2,
            path3role3,
        }
    ):
        await interaction.response.send_message(
            "Please provide arguments for role assignments", ephemeral=True
        )
        print(f"{interaction.user.name} used /roles with no arguments")
    else:
        await interaction.response.send_message("Your rolepaths are being updated...")
        if rolebase != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {rolebase.id}, role_name='{rolebase.name}' WHERE rolepath = 'rolebase'"
            )
            await interaction.channel.send("rolebase has been updated")
        if path1role1 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path1role1.id}, role_name='{path1role1.name}' WHERE rolepath = 'path1role1'"
            )
            await interaction.channel.send("path1role1 has been updated")
        if path1role2 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path1role2.id}, role_name='{path1role2.name}' WHERE rolepath = 'path1role2'"
            )
            await interaction.channel.send("path1role2 has been updated")
        if path1role3 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path1role3.id}, role_name='{path1role3.name}' WHERE rolepath = 'path1role3'"
            )
            await interaction.channel.send("path1role3 has been updated")
        if path2role1 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path2role1.id}, role_name='{path2role1.name}' WHERE rolepath = 'path2role1'"
            )
            await interaction.channel.send("path2role1 has been updated")
        if path2role2 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path2role2.id}, role_name='{path2role2.name}' WHERE rolepath = 'path2role2'"
            )
            await interaction.channel.send("path2role2 has been updated")
        if path2role3 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path2role3.id}, role_name='{path2role3.name}' WHERE rolepath = 'path2role3'"
            )
            await interaction.channel.send("path2role3 has been updated")
        if path3role1 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path3role1.id}, role_name='{path3role1.name}' WHERE rolepath = 'path3role1'"
            )
            await interaction.channel.send("path3role1 has been updated")
        if path3role2 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path3role2.id}, role_name='{path3role2.name}' WHERE rolepath = 'path3role2'"
            )
            await interaction.channel.send("path3role2 has been updated")
        if path3role3 != None:
            cur.execute(
                f"UPDATE db1.{guild}_2 SET role_id = {path3role3.id}, role_name='{path3role3.name}' WHERE rolepath = 'path3role3'"
            )
            await interaction.channel.send("path3role3 has been updated")
        mydb.commit()
        mydb.close()
        await interaction.channel.send("Your rolepaths have been updated successfully")
        print(f"{interaction.user.name} updated role options with /roles")


@roles.error
async def admin_error(error, MissingPermissions):
    if MissingPermissions:
        await error.response.send_message(
            "You dont have permissions to do that!", ephemeral=True
        )
        print(f"{error.user.name} tried using /roles without proper permissions")


@app_commands.command()
async def leaderboard(interaction: discord.Interaction):
    """Display the server top 10"""
    guild = interaction.guild.id
    cur.execute(f"SELECT * FROM db1.{guild} ORDER BY user_points DESC LIMIT 10")
    results = cur.fetchall()
    embed = discord.Embed(
        title="**__Leaderboard__**",
        color=discord.Color.red(),
    )
    for i, result in enumerate(results):
        embed.add_field(
            name=f"{i+1}) {result[1]}",
            value=f"Level: {result[2]} Points: {result[3]}",
            inline=False,
        )
    await interaction.response.send_message(embed=embed)
    mydb.close()


@bot.event
async def on_connect():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=" {} servers.".format(len(bot.guilds)),
        )
    )
    print("updated bot presence")


@app_commands.command()
async def ping(interaction: discord.Interaction):
    """Check the bots latency"""
    latency = "%.5s" % (bot.latency * 1000)
    await interaction.response.send_message(f"Bot latency is {latency} ms")
    print(f"{bot.user.name} latency is {latency} ms")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user.name} has connected to Discord!")


message_cooldown = commands.CooldownMapping.from_cooldown(
    1.0, 5.0, commands.BucketType.user
)


@bot.event
async def on_message(message):
    bucket = message_cooldown.get_bucket(message)
    retry_after = bucket.update_rate_limit()
    if retry_after:
        return
    #    await bot.process_commands(message)
    user = message.author
    userid = message.author.id
    if message.guild != None:
        guild = message.guild.id
    name = message.author.name
    if message.author.bot == True:
        return
    else:
        cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'denominator'")
        de = cur.fetchone()
        if de != None:
            denom = int(de[1])
        else:
            denom = 2
        cur.execute(f"SELECT * FROM db1.{guild} WHERE user_id = {userid}")
        results = cur.fetchone()
        if results == None:
            newpts = 1
        else:
            newpts = results[3] + 1
        newlvl = math.floor(math.sqrt(newpts) / denom)
        cur.execute(
            f'INSERT INTO db1.{guild}(user_id,user_name,user_level,user_points) VALUES("{userid}","{name}","{newlvl}","{newpts}") ON DUPLICATE KEY UPDATE user_points = {newpts}, user_level = {newlvl}'
        )
        print(
            f"{name} updated to {newpts} points and level {newlvl} with their message in {message.channel.name}"
        )
        mydb.commit()
        cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'botchannel'")
        res = cur.fetchone()
        if res[1] == None:
            botchannel = message.channel
        else:
            botchannel = bot.get_channel(int(res[1]))
        cur.execute(
            f" SELECT * FROM db1.{guild}_2 WHERE role_id != ' ' EXCEPT SELECT * FROM db1.{guild}_2 WHERE rolepath = 'botchannel'"
        )
        rests = cur.fetchall()
        cnt = len(rests)
        if cnt < 10:
            if results == None:
                return
            elif results[2] == None:
                return
            elif newlvl == results[2]:
                return
            else:
                cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
                result = cur.fetchone()
                if result != None:
                    custommsg = result[3]
                    await botchannel.send(
                        custommsg.format(mention=user.mention, level=newlvl)
                    )
                else:
                    await botchannel.send(
                        f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                    )
        elif newpts == 16:
            cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'rolebase'")
            rolebase = cur.fetchone()
            rb = int(rolebase[1])
            await message.author.add_roles(discord.Object(id=rb))
            lvlmsg = await botchannel.send(
                f"<@{userid}>, Congratulations on advancing to level **{newlvl}**! Please pick a role from the role menu",
                view=Roles(message),
            )
        elif newpts == 400:
            cur.execute(
                f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path2role1' OR rolepath = 'path3role1'"
            )
            res = cur.fetchall()
            path1 = res[0]
            path2 = res[1]
            path3 = res[2]
            path1id = int(path1[1])
            path2id = int(path2[1])
            path3id = int(path3[1])
            path1role1 = get(message.guild.roles, id=path1id)
            path2role1 = get(message.guild.roles, id=path2id)
            path3role1 = get(message.guild.roles, id=path3id)
            if path1role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role2'"
                )
                rsts = cur.fetchone()
                p1r2id = int(rsts[1])
                p1r2 = get(message.guild.roles, id=p1r2id)
                await message.author.add_roles(p1r2)
                await message.author.remove_roles(path1role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p1r2}**!"
                )
            elif path2role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path2role2'"
                )
                rsts = cur.fetchone()
                p2r2id = int(rsts[1])
                p2r2 = get(message.guild.roles, id=p2r2id)
                await message.author.add_roles(p2r2)
                await message.author.remove_roles(path2role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p2r2}**!"
                )
            elif path3role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path3role2'"
                )
                rsts = cur.fetchone()
                p3r2id = int(rsts[1])
                p3r2 = get(message.guild.roles, id=p3r2id)
                await message.author.add_roles(p3r2)
                await message.author.remove_roles(path3role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p3r2}**!"
                )
            else:
                cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
                result = cur.fetchone()
                if result != None:
                    custommsg = result[3]
                    lvlmsg = await botchannel.send(
                        custommsg.format(mention=user.mention, level=newlvl)
                    )
                else:
                    lvlmsg = await botchannel.send(
                        f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                    )
        #                lvlmsg = await botchannel.send(f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!")
        elif newpts == 1156:
            cur.execute(
                f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role2' OR rolepath = 'path2role2' OR rolepath = 'path3role2'"
            )
            res = cur.fetchall()
            path1 = res[0]
            path2 = res[1]
            path3 = res[2]
            path1id = int(path1[1])
            path2id = int(path2[1])
            path3id = int(path3[1])
            path1role2 = get(message.guild.roles, id=path1id)
            path2role2 = get(message.guild.roles, id=path2id)
            path3role2 = get(message.guild.roles, id=path3id)
            if path1role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role3'"
                )
                rsts = cur.fetchone()
                p1r3id = int(rsts[1])
                p1r3 = get(message.guild.roles, id=p1r3id)
                await message.author.add_roles(p1r3)
                await message.author.remove_roles(path1role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p1r3}**! Please pick another path to follow",
                    view=Roles(message),
                )
            elif path2role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path2role3'"
                )
                rsts = cur.fetchone()
                p2r3id = int(rsts[1])
                p2r3 = get(message.guild.roles, id=p2r3id)
                await message.author.add_roles(p2r3)
                await message.author.remove_roles(path2role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p2r3}**! Please pick another path to follow",
                    view=Roles(message),
                )
            elif path3role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path3role3'"
                )
                rsts = cur.fetchone()
                p3r3id = int(rsts[1])
                p3r3 = get(message.guild.roles, id=p3r3id)
                await message.author.add_roles(p3r3)
                await message.author.remove_roles(path3role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p3r3}**! Please pick another path to follow",
                    view=Roles(message),
                )
            else:
                cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
                result = cur.fetchone()
                if result != None:
                    custommsg = result[3]
                    lvlmsg = await botchannel.send(
                        custommsg.format(mention=user.mention, level=newlvl)
                    )
                else:
                    lvlmsg = await botchannel.send(
                        f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                    )
        #                lvlmsg = await botchannel.send(f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!")
        elif newpts == 1600:
            cur.execute(
                f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path2role1' OR rolepath = 'path3role1'"
            )
            res = cur.fetchall()
            path1 = res[0]
            path2 = res[1]
            path3 = res[2]
            path1id = int(path1[1])
            path2id = int(path2[1])
            path3id = int(path3[1])
            path1role1 = get(message.guild.roles, id=path1id)
            path2role1 = get(message.guild.roles, id=path2id)
            path3role1 = get(message.guild.roles, id=path3id)
            if path1role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role2'"
                )
                rsts = cur.fetchone()
                p1r2id = int(rsts[1])
                p1r2 = get(message.guild.roles, id=p1r2id)
                await message.author.add_roles(p1r2)
                await message.author.remove_roles(path1role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p1r2}**!"
                )
            elif path2role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path2role2'"
                )
                rsts = cur.fetchone()
                p2r2id = int(rsts[1])
                p2r2 = get(message.guild.roles, id=p2r2id)
                await message.author.add_roles(p2r2)
                await message.author.remove_roles(path2role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p2r2}**!"
                )
            elif path3role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path3role2'"
                )
                rsts = cur.fetchone()
                p3r2id = int(rsts[1])
                p3r2 = get(message.guild.roles, id=p3r2id)
                await message.author.add_roles(p3r2)
                await message.author.remove_roles(path3role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p3r2}**!"
                )
            else:
                cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
                result = cur.fetchone()
                if result != None:
                    custommsg = result[3]
                    lvlmsg = await botchannel.send(
                        custommsg.format(mention=user.mention, level=newlvl)
                    )
                else:
                    lvlmsg = await botchannel.send(
                        f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                    )
        #                lvlmsg = await botchannel.send(f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!")
        elif newpts == 2304:
            cur.execute(
                f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role2' OR rolepath = 'path2role2' OR rolepath = 'path3role2'"
            )
            res = cur.fetchall()
            path1 = res[0]
            path2 = res[1]
            path3 = res[2]
            path1id = int(path1[1])
            path2id = int(path2[1])
            path3id = int(path3[1])
            path1role2 = get(message.guild.roles, id=path1id)
            path2role2 = get(message.guild.roles, id=path2id)
            path3role2 = get(message.guild.roles, id=path3id)
            if path1role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role3'"
                )
                rsts = cur.fetchone()
                p1r3id = int(rsts[1])
                p1r3 = get(message.guild.roles, id=p1r3id)
                await message.author.add_roles(p1r3)
                await message.author.remove_roles(path1role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p1r3}**! Please pick another path to follow",
                    view=Roles(message),
                )
            elif path2role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path2role3'"
                )
                rsts = cur.fetchone()
                p2r3id = int(rsts[1])
                p2r3 = get(message.guild.roles, id=p2r3id)
                await message.author.add_roles(p2r3)
                await message.author.remove_roles(path2role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p2r3}**! Please pick another path to follow",
                    view=Roles(message),
                )
            elif path3role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path3role3'"
                )
                rsts = cur.fetchone()
                p3r3id = int(rsts[1])
                p3r3 = get(message.guild.roles, id=p3r3id)
                await message.author.add_roles(p3r3)
                await message.author.remove_roles(path3role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p3r3}**! Please pick another path to follow",
                    view=Roles(message),
                )
            else:
                cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
                result = cur.fetchone()
                if result != None:
                    custommsg = result[3]
                    lvlmsg = await botchannel.send(
                        custommsg.format(mention=user.mention, level=newlvl)
                    )
                else:
                    lvlmsg = await botchannel.send(
                        f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                    )
        #                lvlmsg = await botchannel.send(f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!")
        elif newpts == 2704:
            cur.execute(
                f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role1' OR rolepath = 'path2role1' OR rolepath = 'path3role1'"
            )
            res = cur.fetchall()
            path1 = res[0]
            path2 = res[1]
            path3 = res[2]
            path1id = int(path1[1])
            path2id = int(path2[1])
            path3id = int(path3[1])
            path1role1 = get(message.guild.roles, id=path1id)
            path2role1 = get(message.guild.roles, id=path2id)
            path3role1 = get(message.guild.roles, id=path3id)
            if path1role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role2'"
                )
                rsts = cur.fetchone()
                p1r2id = int(rsts[1])
                p1r2 = get(message.guild.roles, id=p1r2id)
                await message.author.add_roles(p1r2)
                await message.author.remove_roles(path1role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p1r2}**!"
                )
            elif path2role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path2role2'"
                )
                rsts = cur.fetchone()
                p2r2id = int(rsts[1])
                p2r2 = get(message.guild.roles, id=p2r2id)
                await message.author.add_roles(p2r2)
                await message.author.remove_roles(path2role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p2r2}**!"
                )
            elif path3role1 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path3role2'"
                )
                rsts = cur.fetchone()
                p3r2id = int(rsts[1])
                p3r2 = get(message.guild.roles, id=p3r2id)
                await message.author.add_roles(p3r2)
                await message.author.remove_roles(path3role1)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the role of **{p3r2}**!"
                )
            else:
                cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
                result = cur.fetchone()
                if result != None:
                    custommsg = result[3]
                    lvlmsg = await botchannel.send(
                        custommsg.format(mention=user.mention, level=newlvl)
                    )
                else:
                    lvlmsg = await botchannel.send(
                        f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                    )
        #                lvlmsg = await botchannel.send(f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!")
        elif newpts == 3600:
            cur.execute(
                f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role2' OR rolepath = 'path2role2' OR rolepath = 'path3role2'"
            )
            res = cur.fetchall()
            path1 = res[0]
            path2 = res[1]
            path3 = res[2]
            path1id = int(path1[1])
            path2id = int(path2[1])
            path3id = int(path3[1])
            path1role2 = get(message.guild.roles, id=path1id)
            path2role2 = get(message.guild.roles, id=path2id)
            path3role2 = get(message.guild.roles, id=path3id)
            if path1role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path1role3'"
                )
                rsts = cur.fetchone()
                p1r3id = int(rsts[1])
                p1r3 = get(message.guild.roles, id=p1r3id)
                await message.author.add_roles(p1r3)
                await message.author.remove_roles(path1role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the final role of **{p1r3}** in the server, feel free to continue to level up!"
                )
            elif path2role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path2role3'"
                )
                rsts = cur.fetchone()
                p2r3id = int(rsts[1])
                p2r3 = get(message.guild.roles, id=p2r3id)
                await message.author.add_roles(p2r3)
                await message.author.remove_roles(path2role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the final role of **{p2r3}** in the server, feel free to continue to level up!"
                )
            elif path3role2 in message.author.roles:
                cur.execute(
                    f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'path3role3'"
                )
                rsts = cur.fetchone()
                p3r3id = int(rsts[1])
                p3r3 = get(message.guild.roles, id=p3r3id)
                await message.author.add_roles(p3r3)
                await message.author.remove_roles(path3role2)
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}** and earning the final role of **{p3r3}** in the server, feel free to continue to level up!"
                )
            else:
                cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
                result = cur.fetchone()
                if result != None:
                    custommsg = result[3]
                    lvlmsg = await botchannel.send(
                        custommsg.format(mention=user.mention, level=newlvl)
                    )
                else:
                    lvlmsg = await botchannel.send(
                        f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                    )
        #                lvlmsg = await botchannel.send(f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!")
        elif results == None:
            return
        elif results[2] == newlvl:
            return
        else:
            cur.execute(f"SELECT * FROM db1.{guild}_2 WHERE rolepath = 'levelmsg'")
            result = cur.fetchone()
            if result != None:
                custommsg = result[3]
                lvlmsg = await botchannel.send(
                    custommsg.format(mention=user.mention, level=newlvl)
                )
            else:
                lvlmsg = await botchannel.send(
                    f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!"
                )
            #                lvlmsg = await botchannel.send(f"<@{userid}>, Congratulations on advancing to level **{newlvl}**!")
            lvlmsg
        mydb.close()


bot.tree.add_command(setting)
bot.tree.add_command(adjust)
bot.tree.add_command(update)
bot.tree.add_command(help)
bot.tree.add_command(ping)
bot.tree.add_command(newpath)
bot.tree.add_command(rank)
bot.tree.add_command(notifchannel)
bot.tree.add_command(level)
bot.tree.add_command(roles)
bot.tree.add_command(leaderboard)
bot.run(TOKEN, reconnect=True, log_handler=None)
