import discord
from discord.app_commands import autocomplete, command, describe
from discord.ext.commands import Cog

from run import cc, run_tests, ktypes, ktype_ac
from utils import check_user, convert_literals, challenge_ac, make_leaderboard, format_submission_result, get_submission_position
from utils import get_ordinal, format_time
from db import db, Perm

class SubmitCog(Cog):

  @command()
  @check_user(Perm.USER, Perm.ADMIN)
  @autocomplete(challenge=challenge_ac, ktype=ktype_ac)
  @convert_literals
  async def submit(self, interaction: discord.Interaction, challenge:str, ktype:str, name:str, 
                  global_size:tuple[int,int,int], local_size:tuple[int,int,int], 
                   kernel:discord.Attachment, transpose_a:bool=False, transpose_b:bool=False):
    """Submit a kernel for a challenge"""
    await interaction.response.send_message("checking...", ephemeral=True)
    if ktype not in ktypes: return await interaction.response.send_message("invalid ktype", ephemeral=True)
    chal, tensors = db.execute("SELECT id, tests FROM challenges as c WHERE c.name = ?", (challenge,)).fetchone()
    if chal is None: return await interaction.response.send_message(f"could not find challenge {challenge}", ephemeral=True)
    
    # Skip transpose options for non-matmul challenges
    if challenge.lower() != "matmul" and (transpose_a or transpose_b):
        await interaction.edit_original_response(content="Transpose options are only available for matmul challenge")
        return
        
    await interaction.edit_original_response(content="downloading...")
    src = (await kernel.read()).decode("utf-8")
    await interaction.edit_original_response(content="compiling...")

    try: 
      prog = cc(src, ktype, name)
    except Exception as e: 
      # Capture detailed error message with code snippet
      error_msg = str(e)
      formatted_error = f"```\n{error_msg}\n```"
      return await interaction.edit_original_response(content=f"Failed to compile:\n{formatted_error}")
    
    await interaction.edit_original_response(content="running...")
    try: 
      tm = run_tests(prog, global_size, local_size, tensors, challenge, transpose_a, transpose_b)
    except Exception as e: 
      error_msg = str(e)
      formatted_error = f"```\n{error_msg}\n```"
      return await interaction.edit_original_response(content=f"Error while running tests:\n{formatted_error}")
    
    db.execute("INSERT INTO submissions (name, type, source, comp_id, user_id, timing) VALUES (?, ?, ?, ?, ?, ?);",
              (name, ktype, src, chal, interaction.user.id, tm))
    db.commit()
    make_leaderboard.cache_clear()
    
    result = format_submission_result(challenge, str(interaction.user.id), name, ktype, tm)
    await interaction.edit_original_response(content=f"{result}")
    
    # Check if this is the user's BEST submission for this challenge
    is_personal_best = db.execute("""
        SELECT MIN(timing) = ? 
        FROM submissions 
        WHERE comp_id = ? AND user_id = ?
    """, (tm, chal, interaction.user.id)).fetchone()[0]
    
    position = get_submission_position(challenge, interaction.user.id)
    
    message = f"<@{interaction.user.id}>'s submission with id `{name}` to leaderboard `{challenge}`:\n"
    
    if is_personal_best and position <= 3:
        medal_emoji = "🥇 " if position == 1 else "🥈 " if position == 2 else "🥉 "
        message += f"{medal_emoji}{get_ordinal(position)} place on {challenge}: {format_time(tm)}"
    else:
        message += f"{challenge}: {format_time(tm)}"
    
    await interaction.channel.send(message)