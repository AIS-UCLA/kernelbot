from ast import literal_eval
import discord
from discord import app_commands
from discord.ext import commands

import run

ktypes = ["CUDA", "PTX", "torch"]

class SubmitCog(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  async def ktype_ac(self, interaction, curr):
    return [app_commands.Choice(name=kt, value=kt) for kt in ktypes if curr.lower() in kt.lower()]

  @app_commands.command()
  @app_commands.autocomplete(ktype=ktype_ac)
  async def submit(self, interaction: discord.Interaction,
                   ktype:str, name:str, global_size:str, local_size:str,
                   kernel:discord.Attachment):
    await interaction.response.send_message("downloading...")
    src = (await kernel.read()).decode("utf-8")
    await interaction.edit_original_response(content="compiling...")
    try: prog = run.cc(src, ktype, name)
    except Exception as e:
      await interaction.edit_original_response(content=f"error: {e}")
      return
    await interaction.edit_original_response(content="running...")
    tm = run.run(prog, literal_eval(global_size), literal_eval(local_size))
    await interaction.edit_original_response(content=f"{tm*1e6:9.2f} us")

