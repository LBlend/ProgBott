# Discord Packages
import discord
from discord.ext import commands

# Bot Utilities
from cogs.utils.db import DB
from cogs.utils.db_tools import get_user
from cogs.utils.defaults import easy_embed
from cogs.utils.server import Server

import operator
import os
import random
import string
import threading

import requests


class Github(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        database = DB(data_dir=self.bot.data_dir)
        database.populate_tables()

    def id_generator(self, size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @commands.guild_only()
    @commands.group(name="github", aliases=["gh"])
    async def ghGroup(self, ctx):
        """
        Gruppe for Github kommandoer
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @ghGroup.command(name="auth", aliases=["add", "verify", "verifiser", "koble"])
    async def auth(self, ctx):
        """
        Kommando for å koble din Github- til din Discord-bruker
        """
        random_string = self.id_generator()
        is_user_registered = self.is_user_registered(ctx.author.id, random_string)

        if is_user_registered:
            return await ctx.send(ctx.author.mention + " du er allerede registrert!")

        try:
            embed = easy_embed(self, ctx)
            discord_id_and_key = "{}:{}".format(ctx.author.id, random_string)
            registration_link = "https://github.com/login/oauth/authorize" \
                                "?client_id={}&redirect_uri={}?params={}".format(
                                    self.bot.settings.github["client_id"],
                                    self.bot.settings.github["callback_uri"], discord_id_and_key
                                )
            embed.title = "Hei! For å verifisere GitHub kontoen din, følg lenken under"
            embed.description = f"[Verifiser med GitHub]({registration_link})"
            await ctx.author.send(embed=embed)
        except Exception as E:
            self.bot.logger.warn('Error when verifying Github user:\n%s', E)

        return await ctx.send(ctx.author.mention + " sender ny registreringslenke på DM!")

    @ghGroup.command(name="remove", aliases=["fjern"])
    async def remove(self, ctx):
        """
        Kommando for å fjerne kobling mellom Github- og Discord-bruker
        """
        conn = DB(data_dir=self.bot.data_dir).connection

        cursor = conn.cursor()

        cursor.execute("DELETE FROM github_users WHERE discord_id={}".format(ctx.author.id))

        conn.commit()

        return await ctx.send(ctx.author.mention + "fjernet Githuben din.")

    @ghGroup.command(name="repos", aliases=["stars", "stjerner"])
    async def show_repos(self, ctx, user: discord.Member = None):
        """
        Viser mest stjernede repoene til brukeren. maks  5
        """
        is_self = False
        if not user:
            user = ctx.author
            is_self = True
        gh_user = get_user(self, user.id)

        if gh_user is None:
            usr = user.name
            if is_self:
                usr = "Du"
            return await ctx.send(f"{usr} har ikke registrert en bruker enda.")

        embed = easy_embed(self, ctx)
        (_id, discord_id, auth_token, github_username) = gh_user

        gh_repos = requests.get(f"https://api.github.com/users/{github_username}/repos", headers={
            'Authorization': "token " + auth_token,
            'Accept': 'application/json'
        }).json()

        if len(gh_repos) == 0:
            return await ctx.send("Denne brukeren har ingen repos")

        stars = {}
        new_obj = {}

        for gh_repo in gh_repos:
            if gh_repo['private']:
                print(gh_repo['name'])
                continue
            stars[gh_repo['id']] = gh_repo['stargazers_count']
            new_obj[gh_repo['id']] = gh_repo

        stars = dict(sorted(stars.items(), key=operator.itemgetter(1), reverse=True))
        stop = 5 if (len(stars) >= 5) else len(stars)
        idrr = list(stars.items())
        embed.title = f"{stop} mest stjernede repoer"

        for n in range(0, stop):
            repo_id, *overflow = idrr[n]
            repo = new_obj[repo_id]
            title = f"{repo['name']} - ⭐:{repo['stargazers_count']}"
            desc = repo['description']
            if not repo['description']:
                desc = "Ingen beskrivelse oppgitt"
            desc += f"\n[Link]({repo['html_url']})"
            embed.add_field(name=title, value=desc, inline=False)

        await ctx.send(embed=embed)

    @ ghGroup.command(name="user", aliases=["meg", "bruker"])
    async def show_user(self, ctx, user: discord.Member = None):
        """
        Kommando som vier et sammendrag fra github brukeren
        """
        is_self = False
        if not user:
            user = ctx.author
            is_self = True
        gh_user = get_user(self, user.id)

        if gh_user is None:
            usr = user.name
            if is_self:
                usr = "Du"
            return await ctx.send(f"{usr} har ikke registrert en bruker enda.")

        (_id, discord_id, auth_token, github_username) = gh_user

        gh_user = requests.get("https://api.github.com/user", headers={
            'Authorization': "token " + auth_token,
            'Accept': 'application/json'
        }).json()

        embed = easy_embed(self, ctx)

        embed.title = gh_user["login"]
        embed.description = gh_user["html_url"]

        embed.set_thumbnail(url=gh_user["avatar_url"])

        embed.add_field(name="Følgere / Følger",
                        value="{} / {}".format(gh_user["followers"], gh_user["following"]), inline=False)
        embed.add_field(name="Biografi", value=gh_user["bio"], inline=False)
        embed.add_field(name="Offentlige repos", value=gh_user["public_repos"], inline=False)

        return await ctx.send(embed=embed)

    def is_user_registered(self, discord_id, random_string):
        conn = DB(data_dir=self.bot.data_dir).connection

        if conn is None:
            return False

        cursor = conn.cursor()

        cursor.execute("SELECT * FROM github_users WHERE discord_id={}".format(discord_id))

        rows = cursor.fetchone()

        if rows is not None:
            conn.close()
            return True

        cursor.execute("SELECT * FROM pending_users WHERE discord_id={}".format(discord_id))

        row = cursor.fetchone()

        if row is not None:
            cursor.execute("DELETE FROM pending_users WHERE discord_id={}".format(discord_id))

        cursor.execute("INSERT INTO pending_users(discord_id, verification) VALUES(?, ?);", (discord_id, random_string))

        conn.commit()
        conn.close()
        return False


def check_folder(data_dir):
    f = f'{data_dir}/db'
    if not os.path.exists(f):
        os.makedirs(f)


def start_server(bot):
    server = threading.Thread(target=Server, kwargs={'data_dir': bot.data_dir, 'settings': bot.settings.github})
    server.start()


def setup(bot):
    check_folder(bot.data_dir)
    start_server(bot)
    bot.add_cog(Github(bot))
