import sqlite3
import discord
from discord import app_commands
from threading import Lock
import requests
import config
from better_profanity import profanity
import aiohttp

lock = Lock()

class DiscordClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.synced = False
        self.tree = app_commands.CommandTree(self)
        self.filter_lists = {} 
        profanity.load_censor_words()

    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        if not self.synced:
            await self.tree.sync()
            self.synced = True
        print("Client is ready!")
    async def get_channel_id(self, name):
        channel = discord.utils.get(self.get_all_channels(), name=name)
        channel_id = channel.id
        return channel_id

    async def send_message(self, channel_name, message):
        channel_id = await self.get_channel_id(channel_name)
        channel = self.get_channel(channel_id)
        await channel.send(message)
        return "true"

    async def send_message_by_channel_id(self, channel_id:int, message:str):
        channel = self.get_channel(int(channel_id))
        await channel.send(message)
        return "true"

client = DiscordClient(intents=discord.Intents.default())

@client.tree.command(name="learn", description="Request to learn a course")
async def learn(interaction: discord.Interaction, course: str):

    guild_id = interaction.guild_id
    course_lower = course.lower()
    if profanity.contains_profanity(course_lower):
        await interaction.response.send_message("The course description contains prohibited content from the default filter. Please try again with a different description.", ephemeral=True)
        return
    conn = sqlite3.connect('filters.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT filter_word FROM filters WHERE guild_id = ?
    ''', (guild_id,))
    rows = cursor.fetchall()

    for row in rows:
        word = row[0]
        if word in course_lower:
            await interaction.response.send_message(f"The course description contains a prohibited word: '{word}' from the custom filter. Please try again with a different description.", ephemeral=True)
            conn.close()
            return

    conn.close()
            
    reply = f"{interaction.user.mention} Generating course: {course}..."
    await interaction.response.send_message(reply)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                config.API_ENDPOINT,
                json={
                    "course_description": course,
                    "channel_id": interaction.channel_id,
                    "mention": interaction.user.mention
                },
                timeout=10
            ) as response:
                print("HTTP request sent.")
    except Exception as e:
        await interaction.followup.send("An unexpected error occurred. Please try again later.", ephemeral=True)

@client.tree.command(name="viewfilter", description="View the current filter list for this server")
@app_commands.checks.has_permissions(administrator=True)
async def view_filter(interaction: discord.Interaction):
    guild_id = interaction.guild_id

    conn = sqlite3.connect('filters.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT filter_word FROM filters WHERE guild_id = ?
    ''', (guild_id,))
    rows = cursor.fetchall()
    
    if rows:
        filter_list = ", ".join(row[0] for row in rows)
        await interaction.response.send_message(f"Current filter list: {filter_list}", ephemeral=True)
    else:
        await interaction.response.send_message("There are no words in the filter list.", ephemeral=True)
    
    conn.close()

@client.tree.command(name="addfilter", description="Upload a text file to add words to the filter list")
@app_commands.checks.has_permissions(administrator=True)
async def add_filter(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith('.txt'):
        await interaction.response.send_message("Please upload a `.txt` file.", ephemeral=True)
        return
    
    try:
        file_content = await file.read()
        content = file_content.decode('utf-8').strip()
        
        if not all(word.strip().isalnum() for word in content.split(',')):
            await interaction.response.send_message("The file format is incorrect. Please ensure the file contains words separated by commas with no special characters.", ephemeral=True)
            return
        
        words = [word.strip() for word in content.split(',')]
        guild_id = interaction.guild_id
        
        conn = sqlite3.connect('filters.db')
        cursor = conn.cursor()

        for word in words:
            try:
                cursor.execute('''
                    INSERT INTO filters (guild_id, filter_word)
                    VALUES (?, ?)
                ''', (guild_id, word))
            except sqlite3.IntegrityError:
                pass 

        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"Successfully added {len(words)} words to the filter list.", ephemeral=True)
    
    except Exception as e:
        await interaction.response.send_message("Failed to process the file. Please ensure it is in the correct format.", ephemeral=True)

@client.tree.command(name="removefilter", description="Upload a text file to remove words from the filter list")
@app_commands.checks.has_permissions(administrator=True)
async def remove_filter(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith('.txt'):
        await interaction.response.send_message("Please upload a `.txt` file.", ephemeral=True)
        return
    
    try:
        file_content = await file.read()
        content = file_content.decode('utf-8').strip()
        
        if not all(word.strip().isalnum() for word in content.split(',')):
            await interaction.response.send_message("The file format is incorrect. Please ensure the file contains words separated by commas with no special characters.", ephemeral=True)
            return
        
        words = [word.strip() for word in content.split(',')]
        guild_id = interaction.guild_id
        
        conn = sqlite3.connect('filters.db')
        cursor = conn.cursor()

        # Remove each word from the filter list
        for word in words:
            cursor.execute('''
                DELETE FROM filters WHERE guild_id = ? AND filter_word = ?
            ''', (guild_id, word))

        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f"Successfully removed {len(words)} words from the filter list.", ephemeral=True)
    
    except Exception as e:
        await interaction.response.send_message("Failed to process the file. Please ensure it is in the correct format.", ephemeral=True)

@remove_filter.error
async def remove_filter_file_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have permission to remove filters.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing the file.", ephemeral=True)


@add_filter.error
async def add_filter_file_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have permission to add filters.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing the file.", ephemeral=True)

@view_filter.error
async def view_filter_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have permission to view filters.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while viewing the filter list.", ephemeral=True)
