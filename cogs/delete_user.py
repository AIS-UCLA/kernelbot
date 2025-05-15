from typing import Optional
import discord
from discord.app_commands import autocomplete, command, Choice
from discord.ext.commands import Cog
from utils import check_user
from db import db, Perm
import asyncio

async def user_id_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]]:
    """Autocomplete for all user IDs in the system (both registered users and submission creators)"""
    query = f"%{current}%" if current else "%"
    
    registered_users = db.execute(
        """SELECT id, username, 'registered' as type FROM users 
           WHERE CAST(id AS TEXT) LIKE ?""", 
        (query,)
    ).fetchall()
    
    unregistered_users = db.execute(
        """SELECT DISTINCT s.user_id as id, 'unregistered' as type
           FROM submissions s
           LEFT JOIN users u ON s.user_id = u.id
           WHERE u.id IS NULL AND CAST(s.user_id AS TEXT) LIKE ?""",
        (query,)
    ).fetchall()
    
    choices = []
    
    for user_id, username, user_type in registered_users:
        choices.append(Choice(name=f"{user_id} ({username})", value=str(user_id)))
    
    for user_id, user_type in unregistered_users:
        choices.append(Choice(name=f"{user_id} (unregistered)", value=str(user_id)))
    
    return choices[:25]

class DeleteUserCog(Cog):
    @command()
    @check_user(Perm.ADMIN)  # Only admins can delete users
    @autocomplete(user_id=user_id_autocomplete)
    async def delete_user(self, interaction: discord.Interaction, user_id: str):
        """Delete a user and all their submissions from the database by Discord ID"""
        if not user_id:
            await interaction.response.send_message("Please specify a user ID to delete.", ephemeral=True)
            return
        
        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.response.send_message("Invalid user ID format. Please provide a numeric Discord ID.", ephemeral=True)
            return
            
        user_data = db.execute("SELECT id, username FROM users WHERE id = ?", (user_id_int,)).fetchone()
        
        submission_count = db.execute(
            "SELECT COUNT(*) FROM submissions WHERE user_id = ?", (user_id_int,)
        ).fetchone()[0]
        
        if not user_data and submission_count == 0:
            await interaction.response.send_message(
                f"User ID `{user_id}` not found in the database and has no submissions.", 
                ephemeral=True
            )
            return
        
        if user_data:
            discord_id = user_data[0]
            username = user_data[1]
            user_info = f"<@{discord_id}> (username: {username})"
        else:
            discord_id = user_id_int
            user_info = f"<@{discord_id}> (unregistered)"
        
        confirm_message = await interaction.response.send_message(
            f"Are you sure you want to delete user {user_info} and all their submissions? "
            f"This action cannot be undone.\n\n"
            f"User has {submission_count} submissions in the database.\n\n"
            f"Reply with 'confirm' to proceed.",
            ephemeral=True
        )
        
        def check(message):
            return message.author.id == interaction.user.id and message.content.lower() == 'confirm'
        
        try:
            await interaction.client.wait_for('message', check=check, timeout=30.0)
            
            try:
                db.execute("BEGIN TRANSACTION")
                
                deleted_submissions = db.execute(
                    "DELETE FROM submissions WHERE user_id = ? RETURNING comp_id, name", 
                    (discord_id,)
                ).fetchall()
                
                submission_info = ""
                if deleted_submissions:
                    submission_names = [sub[1] for sub in deleted_submissions]
                    submission_info = f"Deleted submissions: {', '.join(submission_names)}"
                
                challenges = []
                if user_data:  # Only check for challenges if the user is registered
                    challenges = db.execute(
                        "SELECT id, name FROM challenges WHERE creator_id = ?", 
                        (discord_id,)
                    ).fetchall()
                
                if challenges:
                    challenge_names = [challenge[1] for challenge in challenges]
                    challenge_ids = [challenge[0] for challenge in challenges]
                    
                    for challenge_id in challenge_ids:
                        db.execute(
                            "DELETE FROM submissions WHERE comp_id = ?", 
                            (challenge_id,)
                        )
                    
                    db.execute(
                        "DELETE FROM challenges WHERE creator_id = ?", 
                        (discord_id,)
                    )
                    
                    challenge_message = f"Deleted {len(challenges)} challenges created by the user: {', '.join(challenge_names)}"
                else:
                    challenge_message = "No challenges were created by this user."
                
                if user_data:
                    db.execute("DELETE FROM users WHERE id = ?", (discord_id,))
                    user_message = f"User {user_info} has been deleted from the database."
                else:
                    user_message = f"Unregistered user <@{discord_id}>'s submissions have been deleted."
                
                db.execute("COMMIT")
                
                response = f"{user_message}\n"
                response += f"Removed {len(deleted_submissions)} submissions from the leaderboard.\n"
                if submission_info:
                    response += f"{submission_info}\n"
                response += f"{challenge_message}"
                
                await interaction.followup.send(response, ephemeral=True)
            except Exception as e:
                db.execute("ROLLBACK")
                await interaction.followup.send(
                    f"Error deleting user: {str(e)}", 
                    ephemeral=True
                )
        
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "Deletion cancelled due to timeout.", 
                ephemeral=True
            )
