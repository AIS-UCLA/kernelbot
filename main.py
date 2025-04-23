import asyncio, discord, logging
from discord.ext import commands

from config import DISCORD_TOKEN
from cogs.submit import SubmitCog

def get_logger():
  formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%b %d %H:%M:%S")
  handler = logging.StreamHandler()
  handler.setFormatter(formatter)
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.INFO)
  logger.addHandler(handler)
  return logger, formatter

logger, formatter = get_logger()

class KernelBot(commands.Bot):
  def __init__(self):
    intents = discord.Intents.default()
    intents.message_content = True
    super().__init__(intents=intents, command_prefix="!")

  async def setup_hook(self):
    logger.info(f"Syncing commands")
    await self.add_cog(SubmitCog(self))

  async def on_ready(self):
    logger.info(f"Logged in as {self.user}")
    for guild in self.guilds:
      await guild.me.edit(nick="Kernel Bot")
      self.tree.copy_global_to(guild=guild)
      await self.tree.sync(guild=guild)


if __name__ == "__main__":
  bot = KernelBot()
  bot.run(DISCORD_TOKEN, log_formatter=formatter)
