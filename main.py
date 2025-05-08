import discord
from discord.ext import commands

from config import DISCORD_TOKEN
from utils import logger, formatter
from cogs import ShowCog, SubmitCog, CreateCog

class KernelBot(commands.Bot):
  def __init__(self):
    intents = discord.Intents.default()
    intents.message_content = True
    super().__init__(intents=intents, command_prefix="!")

  async def setup_hook(self):
    logger.info(f"Syncing commands")
    await self.add_cog(SubmitCog(self))
    await self.add_cog(CreateCog(self))
    await self.add_cog(ShowCog(self))

  async def on_ready(self):
    logger.info(f"Logged in as {self.user}")
    for guild in self.guilds:
      await guild.me.edit(nick="Kernel Bot")
      self.tree.copy_global_to(guild=guild)
      await self.tree.sync(guild=guild)

  @commands.is_owner()
  @commands.command()
  async def sync(self, ctx):
      """Sync the application commands"""
      await self.tree.sync()
      await ctx.send("Commands synced globally!")

if __name__ == "__main__": KernelBot().run(DISCORD_TOKEN, log_formatter=formatter)
