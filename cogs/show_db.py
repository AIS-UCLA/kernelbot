from typing import Optional
import discord
from discord.app_commands import command, choices, Choice
from discord.ext.commands import Cog

from db import db, Perm
from utils import check_user

class ShowDBCog(Cog):
    @command()
    @check_user(Perm.ADMIN) 
    async def showdb(self, interaction: discord.Interaction, table: Optional[str] = None):
        """Shows the contents of the database, optionally filtered by table name"""
        await interaction.response.defer(ephemeral=True)
        
        if table is None:
            # Show available tables
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_list = "\n".join([f"- `{table[0]}`" for table in tables])
            await interaction.followup.send(f"## Database Tables\n{table_list}\nUse `/showdb table_name` to view contents.")
        else:
            try:
                rows = db.execute(f"SELECT * FROM {table} LIMIT 100").fetchall()
                if not rows:
                    await interaction.followup.send(f"Table `{table}` exists but contains no data.")
                    return
                    
                headers = [description[0] for description in db.execute(f"SELECT * FROM {table} LIMIT 1").description]
                header_row = " | ".join(headers)
                separator = "-" * len(header_row)
                
                data_rows = []
                for row in rows:
                    data_rows.append(" | ".join(str(item) for item in row))
                
                table_content = f"```\n{header_row}\n{separator}\n" + "\n".join(data_rows) + "\n```"
                
                if len(table_content) > 1900:
                    table_content = table_content[:1900] + "\n... (output truncated)"
                    
                await interaction.followup.send(f"## Contents of table `{table}`:\n{table_content}")
            except Exception as e:
                await interaction.followup.send(f"Error accessing table: {str(e)}")
    
    @showdb.autocomplete('table')
    async def table_autocomplete(self, interaction: discord.Interaction, current: str):
        """Provides autocomplete for database table names"""
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [table[0] for table in tables]
        return [
            Choice(name=name, value=name) 
            for name in table_names if current.lower() in name.lower()
        ][:25]