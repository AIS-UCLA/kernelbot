from typing import Optional
import discord
from discord.app_commands import autocomplete, command, describe
from discord.ext.commands import Cog

from utils import challenge_ac, fmt_time
from db import db, Perm
from utils import check_user

class ShowSubmissionsCog(Cog):
    @command()
    @check_user(Perm.USER, Perm.ADMIN)
    @autocomplete(challenge=challenge_ac)
    @describe(
        challenge="Name of the challenge to show your submissions for",
    )
    async def submissions(self, interaction: discord.Interaction, challenge: str):
        """Show your submissions for a specific challenge"""
        await interaction.response.defer(ephemeral=True) 
        
        # Only allow viewing your own submissions
        target_user = interaction.user
        
        challenge_exists = db.execute("SELECT 1 FROM challenges WHERE name = ?", (challenge,)).fetchone()
        if not challenge_exists:
            await interaction.followup.send(f"Challenge `{challenge}` not found.", ephemeral=True)
            return
            
        submissions = db.execute("""
            SELECT s.name, s.type, s.timing, s.created_at
            FROM submissions s
            JOIN challenges c ON s.comp_id = c.id
            WHERE c.name = ? AND s.user_id = ?
            ORDER BY s.timing ASC
        """, (challenge, str(target_user.id))).fetchall()
        
        if not submissions:
            await interaction.followup.send(f"You have no submissions for challenge `{challenge}`.", ephemeral=True)
            return
            
        best_time = submissions[0][2]
        
        message = f"# Your Submissions for `{challenge}`\n"
        message += f"Total submissions: **{len(submissions)}**\n"
        message += f"Best time: **{fmt_time(best_time)}**\n\n"
        message += "## Submission History\n"
        
        for i, (name, ktype, timing, created_at) in enumerate(submissions):
            is_best = "🏆 " if timing == best_time else ""
            message += f"{i+1}. {is_best}`{name} ({ktype})` in {fmt_time(timing)}"
            
            if created_at:
                message += f" - {created_at}"
                
            message += "\n"
            
        await interaction.followup.send(message)

    @command(name="admin_submissions")
    @check_user(Perm.ADMIN) 
    @autocomplete(challenge=challenge_ac)
    @describe(
        challenge="Name of the challenge to show submissions for",
        user="User to show submissions for",
    )
    async def admin_submissions(self, interaction: discord.Interaction, challenge: str, user: discord.User):
        """Admin command to view any user's submissions for a challenge"""
        await interaction.response.defer(ephemeral=True)
        
        challenge_exists = db.execute("SELECT 1 FROM challenges WHERE name = ?", (challenge,)).fetchone()
        if not challenge_exists:
            await interaction.followup.send(f"Challenge `{challenge}` not found.", ephemeral=True)
            return
            
        submissions = db.execute("""
            SELECT s.name, s.type, s.timing, s.created_at
            FROM submissions s
            JOIN challenges c ON s.comp_id = c.id
            WHERE c.name = ? AND s.user_id = ?
            ORDER BY s.timing ASC
        """, (challenge, str(user.id))).fetchall()
        
        if not submissions:
            await interaction.followup.send(f"{user.display_name} has no submissions for challenge `{challenge}`.", ephemeral=True)
            return
            
        best_time = submissions[0][2]
        
        message = f"# Submissions for `{challenge}` by {user.mention}\n"
        message += f"Total submissions: **{len(submissions)}**\n"
        message += f"Best time: **{fmt_time(best_time)}**\n\n"
        message += "## Submission History\n"
        
        for i, (name, ktype, timing, created_at) in enumerate(submissions):
            is_best = "🏆 " if timing == best_time else ""
            message += f"{i+1}. {is_best}`{name} ({ktype})` in {fmt_time(timing)}"
            
            if created_at:
                message += f" - {created_at}"
                
            message += "\n"
            
        await interaction.followup.send(message)