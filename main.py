import discord
from discord.ext import commands

from config import DISCORD_TOKEN
from utils import logger, formatter
from cogs import ShowCog, SubmitCog, CreateCog, DeleteCog, ShowDBCog, ShowSubmissionsCog

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
    await self.add_cog(DeleteCog(self))
    await self.add_cog(ShowDBCog(self))
    await self.add_cog(ShowSubmissionsCog(self))

  async def on_ready(self):
    logger.info(f"Logged in as {self.user}")
    for guild in self.guilds:
      await guild.me.edit(nick="Kernel Bot")
      
      await self.set_command_permissions(guild)
      
      self.tree.copy_global_to(guild=guild)
      await self.tree.sync(guild=guild)

  async def set_command_permissions(self, guild):
      """Set command permissions based on the required roles"""
      cuda_coda_role = discord.utils.get(guild.roles, name="CUDA Coda")
      admin_role = discord.utils.get(guild.roles, name="kernelbot admin")
      
      logger.info(f"Available roles in {guild.name}: {[role.name for role in guild.roles]}")
      
      if not cuda_coda_role:
          logger.warning(f"Could not find CUDA Coda role in guild {guild.name}")
      
      if not admin_role:
          logger.warning(f"Could not find kernelbot admin role in guild {guild.name}")
      
      if not cuda_coda_role or not admin_role:
          return
        
      commands = self.tree.get_commands()
      
      for command in commands:
        if hasattr(command, "_check_user_perms"):
          perms = command._check_user_perms
          
          permissions = []
          
          # Admin-only commands
          if Perm.ADMIN in perms and Perm.USER not in perms:
            permissions.append(discord.app_commands.CommandPermission(
              id=admin_role.id, 
              type=discord.app_commands.CommandPermissionType.role, 
              permission=True
            ))
            # Hide from everyone else
            permissions.append(discord.app_commands.CommandPermission(
              id=guild.default_role.id,
              type=discord.app_commands.CommandPermissionType.role,
              permission=False
            ))
          
          # Apply permissions if we have any
          if permissions:
            try:
              await self.tree.set_permissions(guild=guild, command=command, permissions=permissions)
              logger.info(f"Set permissions for command {command.name}")
            except Exception as e:
              logger.error(f"Failed to set permissions for command {command.name}: {e}")

if __name__ == "__main__": KernelBot().run(DISCORD_TOKEN, log_formatter=formatter)
