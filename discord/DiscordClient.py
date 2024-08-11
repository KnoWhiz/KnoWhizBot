import discord
from discord import app_commands
from threading import Lock
import requests
import config

lock = Lock()

class DiscordClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.synced = False
        self.tree = app_commands.CommandTree(self)
        self.filter_lists = {} 

    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        print(f'Guilds connected to: {", ".join(guild.name for guild in self.guilds)}')

        if not self.synced:
            print("Syncing commands...")
            await self.tree.sync()
            self.synced = True
            print("Commands have been synced with Discord API")

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
    print(f"Slash command 'learn' triggered by {interaction.user.name} with course: {course}")

    guild_id = interaction.guild_id
    course_lower = course.lower()

    # Check if the course description contains any filtered words
    if guild_id in client.filter_lists:
        for word in client.filter_lists[guild_id]:
            if word in course_lower:
                await interaction.response.send_message(f"The course description contains a prohibited word: '{word}'. Please try again.")
                return
            
    reply = f"{interaction.user.mention} Generating course: {course}..."
    await interaction.response.send_message(reply)
    
    result = ""
    try:
        with lock: 
            print("Sending HTTP request to /v1/discord/zeroshot_trigger...")
            response = requests.post(
                config.API_ENDPOINT,
                json={
                    "course_description": course,
                    "channel_id": interaction.channel_id,
                    "mention": interaction.user.mention
                },
                timeout=10
            )
            print("HTTP request sent.")
    except Exception as e:
        result = None 
        await interaction.followup.send("An unexpected error occurred. Please try again later.")
    finally:
        if result:
            await interaction.followup.send(result)

@client.tree.command(name="addfilter", description="Add a word to the filter list for this server")
async def add_filter(interaction: discord.Interaction, word: str):
    guild_id = interaction.guild_id
    
    if guild_id not in client.filter_lists:
        client.filter_lists[guild_id] = []
    
    if word not in client.filter_lists[guild_id]:
        client.filter_lists[guild_id].append(word)
        await interaction.response.send_message(f"'{word}' has been added to the filter list.")
    else:
        await interaction.response.send_message(f"'{word}' is already in the filter list.")

@client.tree.command(name="removefilter", description="Remove a word from the filter list for this server")
async def remove_filter(interaction: discord.Interaction, word: str):
    guild_id = interaction.guild_id

    if guild_id in client.filter_lists and word in client.filter_lists[guild_id]:
        client.filter_lists[guild_id].remove(word)
        await interaction.response.send_message(f"'{word}' has been removed from the filter list.")
    else:
        await interaction.response.send_message(f"'{word}' is not in the filter list.")

@client.tree.command(name="viewfilter", description="View the current filter list for this server")
async def view_filter(interaction: discord.Interaction):
    guild_id = interaction.guild_id

    if guild_id in client.filter_lists and client.filter_lists[guild_id]:
        filter_list = ", ".join(client.filter_lists[guild_id])
        await interaction.response.send_message(f"Current filter list: {filter_list}")
    else:
        await interaction.response.send_message("There are no words in the filter list.")