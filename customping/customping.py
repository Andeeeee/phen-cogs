# Remove command logic originally from: https://github.com/mikeshardmind/SinbadCogs/tree/v3/messagebox
# Speed test logic from https://github.com/PhasecoreX/PCXCogs/tree/master/netspeed

import discord
import time
import asyncio
import concurrent
import speedtest

from redbot.core import commands, checks

old_ping = None


class CustomPing(commands.Cog):
    """A more information rich ping message."""

    def __init__(self, bot):
        self.bot = bot

    async def red_delete_data_for_user(self, **kwargs):
        return

    def cog_unload(self):
        global old_ping
        if old_ping:
            try:
                self.bot.remove_command("ping")
            except:
                pass
            self.bot.add_command(old_ping)

    @checks.bot_has_permissions(embed_links=True)
    @commands.cooldown(5, 10, commands.BucketType.user)
    @commands.command()
    async def ping(self, ctx):
        """Ping the bot..."""
        start = time.monotonic()
        message = await ctx.send("Pinging...")
        end = time.monotonic()
        totalPing = round((end - start) * 1000, 2)
        e = discord.Embed(title="Pinging..", description=f"Overall Latency: {totalPing}ms")
        await asyncio.sleep(0.25)
        try:
            await message.edit(content=None, embed=e)
        except discord.NotFound:
            return

        botPing = round(self.bot.latency * 1000, 2)
        e.description = e.description + f"\nDiscord WebSocket Latency: {botPing}ms"
        await asyncio.sleep(0.25)
        try:
            await message.edit(embed=e)
        except discord.NotFound:
            return

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        s = speedtest.Speedtest(secure=True)
        await loop.run_in_executor(executor, s.get_servers)
        await loop.run_in_executor(executor, s.get_best_server)
        result = s.results.dict()
        hostPing = round(result["ping"], 2)

        averagePing = (botPing + totalPing) / 2
        if averagePing >= 1000:
            color = discord.Colour.red()
        elif averagePing >= 200:
            color = discord.Colour.orange()
        else:
            color = discord.Colour.green()

        e.color = color
        e.title = "Pong!"
        e.description = e.description + f"\nHost Latency: {hostPing}ms"
        await asyncio.sleep(0.25)
        try:
            await message.edit(embed=e)
        except discord.NotFound:
            return


def setup(bot):
    ping = CustomPing(bot)
    global old_ping
    old_ping = bot.get_command("ping")
    if old_ping:
        bot.remove_command(old_ping.name)
    bot.add_cog(ping)
