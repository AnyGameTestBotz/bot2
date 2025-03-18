import os

# Bot configuration
TOKEN = os.getenv('TOKENDC', '')  # Discord bot token from environment variable
COMMAND_PREFIX = '?'  # Command prefix
MAX_PINGS = 20  # Maximum number of pings per command
PING_DELAY = 1  # Delay between pings in seconds
MIN_COOLDOWN = 5  # Minimum cooldown time in seconds
MAX_COOLDOWN = 45  # Maximum cooldown time in seconds
