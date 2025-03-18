import discord
from discord.ext import commands
import asyncio
import time
import random
from config import TOKEN, COMMAND_PREFIX, MAX_PINGS, PING_DELAY, MIN_COOLDOWN, MAX_COOLDOWN
from flask import Flask, render_template
import threading

# Initialize bot with specific intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Add debug logging for intents
print("Debug: Bot Intents Configuration:")
print(f"- Message Content Intent: {intents.message_content}")
print(f"- Members Intent: {intents.members}")
print(f"- All Intents: {intents}")

# Store cooldowns for users
cooldowns = {}
# Store active spam pings
active_spam_pings = set()
# Authorized users who can stop spam pings
AUTHORIZED_USERS = ['airgt1', 'uselesscatvr']

# Bot status information
bot_status = {
    'is_ready': False,
    'guild_count': 0,
    'last_ping': None,
    'active_pings': 0
}

# Initialize Flask app
webapp = Flask(__name__)


@webapp.route('/')
def home():
    """Render the status page"""
    return render_template('status.html', status=bot_status)


def run_flask():
    """Run the Flask webapp"""
    webapp.run(host='0.0.0.0', port=5000)


@bot.event
async def on_ready():
    """Event handler for when the bot is ready and connected"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

    # Update bot status
    bot_status['is_ready'] = True
    bot_status['guild_count'] = len(bot.guilds)

    # Register slash commands
    try:
        print("Attempting to sync slash commands...")
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message):
    """Event handler for processing messages"""
    # Don't process commands here to avoid double-processing
    if message.author == bot.user:
        return

    # Check if message is "stopping" from authorized users
    if (message.content.lower() == "stopping"
            and message.author.name.lower() in AUTHORIZED_USERS
            and message.reference and message.reference.resolved
            and message.reference.resolved.author == bot.user):

        channel_id = str(message.channel.id)
        if channel_id in active_spam_pings:
            active_spam_pings.remove(channel_id)
            await message.channel.send("_ _")

    # Process commands after checking for stop message
    await bot.process_commands(message)


def get_cooldown_time():
    """Generate a random cooldown time between MIN_COOLDOWN and MAX_COOLDOWN"""
    return random.randint(MIN_COOLDOWN, MAX_COOLDOWN)


def is_on_cooldown(user_id):
    """Check if a user is on cooldown"""
    if user_id in cooldowns:
        cooldown_time = cooldowns[user_id]['time']
        if time.time() - cooldowns[user_id]['start'] < cooldown_time:
            return True
    return False


def update_cooldown(user_id):
    """Update the cooldown timestamp for a user"""
    cooldowns[user_id] = {'start': time.time(), 'time': get_cooldown_time()}


class SlashContext:

    def __init__(self, interaction):
        self.author = interaction.user
        self.channel = interaction.channel
        self._has_responded = False
        self.interaction = interaction

    async def send(self, content):
        try:
            if not self._has_responded:
                await self.interaction.response.send_message(content)
                self._has_responded = True
            else:
                await self.interaction.followup.send(content)
        except discord.NotFound:
            # If interaction expired, send message directly to channel
            await self.channel.send(content)
        except Exception as e:
            print(f"Error sending message in SlashContext: {e}")
            # Fallback to channel send if any other error occurs
            await self.channel.send(content)


async def handle_spam_ping(ctx, member: discord.Member):
    """Common handler for both prefix and slash commands"""
    print(
        f"Starting spam ping for {member.name} requested by {ctx.author.name}")
    print(
        f"Command type: {'Slash' if isinstance(ctx, SlashContext) else 'Prefix'}"
    )
    print(
        f"User authorization status: {ctx.author.name.lower() in AUTHORIZED_USERS}"
    )

    # Check if the user is authorized
    if ctx.author.name.lower() not in AUTHORIZED_USERS:
        print(f"Unauthorized attempt by {ctx.author.name}")
        await ctx.send("You are not authorized to use this command.")
        return

    # Check if the command user is on cooldown
    if is_on_cooldown(ctx.author.id):
        remaining_time = int(cooldowns[ctx.author.id]['time'] -
                             (time.time() - cooldowns[ctx.author.id]['start']))
        await ctx.send(
            f"You need to wait {remaining_time} seconds before using this command again."
        )
        return

    # Check if a member was mentioned
    if member is None:
        await ctx.send("Please mention a user to ping. Usage: ?spamping @user")
        return

    # Don't allow pinging the bot itself
    if member.id == bot.user.id:
        await ctx.send("Can't Ping Self.")
        return

    # Don't allow self-pinging
    if member.id == ctx.author.id:
        await ctx.send("You can't ping yourself.")
        return

    # Update cooldown for the command user
    update_cooldown(ctx.author.id)

    # Add this channel to active spam pings
    channel_id = str(ctx.channel.id)
    active_spam_pings.add(channel_id)

    try:
        for i in range(MAX_PINGS):
            print(f"Sending ping {i+1}/{MAX_PINGS} to {member.name}")
            # Check if spam ping was stopped
            if channel_id not in active_spam_pings:
                print(f"Spam ping stopped for {member.name}")
                await ctx.send("_ _")
                return

            await ctx.send(f"{member.mention}")
            await asyncio.sleep(PING_DELAY)  # Add delay between pings

        # Remove channel from active spam pings
        if channel_id in active_spam_pings:
            active_spam_pings.remove(channel_id)
            print(f"Spam ping completed for {member.name}, sending 'a'")
            await ctx.send("a"
                           )  # Send "a" only if spam ping completes normally

    except Exception as e:
        print(f"Error during spam ping: {e}")
        if channel_id in active_spam_pings:
            active_spam_pings.remove(channel_id)
        await ctx.send("An error occurred during spam ping.")


@bot.command(name='spamping')
async def spam_ping(ctx, member: discord.Member = None):
    """
    Command to spam ping a mentioned user
    Usage: ?spamping @user
    """
    await handle_spam_ping(ctx, member)


@bot.tree.command(name='spamping', description='Spam ping a mentioned user')
@discord.app_commands.check(
    lambda interaction: interaction.user.name.lower() in AUTHORIZED_USERS)
async def slash_spam_ping(interaction: discord.Interaction,
                          member: discord.Member):
    """Slash command version of spam ping"""
    print(f"Slash command received from {interaction.user.name}")
    print(
        f"Authorization status: {interaction.user.name.lower() in AUTHORIZED_USERS}"
    )
    ctx = SlashContext(interaction)
    await handle_spam_ping(ctx, member)


@slash_spam_ping.error
async def slash_spam_ping_error(interaction: discord.Interaction,
                                error: discord.app_commands.AppCommandError):
    """Error handler for the slash_spam_ping command"""
    print(f"Slash command error: {error}")
    try:
        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "You are not authorized to use this command.")
        elif isinstance(error, discord.app_commands.CommandInvokeError):
            if isinstance(error.original, commands.MemberNotFound):
                await interaction.response.send_message(
                    "Could not find that user.")
            elif isinstance(error.original, commands.MissingPermissions):
                await interaction.response.send_message(
                    "You don't have permission to use this command.")
            else:
                await interaction.response.send_message(
                    f"An error occurred: {str(error.original)}")
        else:
            await interaction.response.send_message(
                f"An error occurred: {str(error)}")
    except Exception as e:
        print(f"Error in slash command error handler: {e}")
        # Fallback if interaction has already been responded to
        try:
            await interaction.channel.send(
                "An error occurred while processing the command.")
        except:
            print(f"Failed to send error message to channel: {e}")


@spam_ping.error
async def spam_ping_error(ctx, error):
    """Error handler for the spam_ping command"""
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("Could not find that user.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")


# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        print("Error: Discord token not found in environment variables!")
        exit(1)

    # Add debug logging
    print("Debug: Token validation check:")
    print(f"- Token present: {bool(TOKEN)}")
    print(f"- Token length: {len(TOKEN)}")
    print(
        f"- Token format check: {TOKEN.startswith('MT') or TOKEN.startswith('NT')}"
    )

    try:
        print("Starting bot...")
        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.start()

        # Run the bot
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("Error: Failed to log in to Discord. Please check the token.")
    except discord.PrivilegedIntentsRequired:
        print(
            "Error: Bot requires privileged intents. Please enable them in the Discord Developer Portal."
        )
    except Exception as e:
        print(f"Error: An unexpected error occurred: {str(e)}")
        if "Cannot connect to host discord.com:443" in str(e):
            print(
                "Network connection issue. Please check your internet connection."
            )
        elif "Event loop is closed" in str(e):
            print(
                "Event loop was closed. This might be due to the bot being shut down improperly."
            )
