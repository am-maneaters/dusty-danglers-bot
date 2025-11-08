import discord
from discord.ext import tasks, commands
from datetime import datetime, timedelta
import json
import os
from flask import Flask
from threading import Thread

# --- Flask web server to keep Render alive ---
app = Flask("")


@app.route("/")
def home():
    return "Bot is running!"


def run():
    app.run(host="0.0.0.0", port=8080)


Thread(target=run).start()

# --- Discord bot setup ---
TOKEN = os.getenv("TOKEN")  # Discord bot token from Render environment variables
CHANNEL_ID = int(
    os.getenv("CHANNEL_ID")
)  # Channel ID from Render environment variables

intents = discord.Intents.default()
intents.message_content = True  # THIS IS REQUIRED

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Event storage ---
EVENTS_FILE = "events.json"


def load_events():
    with open(EVENTS_FILE, "r") as f:
        return json.load(f)


# --- Bot events ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    check_events.start()


# --- Daily reminder check ---
@tasks.loop(hours=24)
async def check_events():
    today = datetime.now().date()
    channel = bot.get_channel(CHANNEL_ID)
    events = load_events()

    for event in events:
        # Convert "Wednesday Nov 12" + time into a datetime object
        dt_str = f"{event['date']} {event['time']}"
        event_datetime = datetime.strptime(dt_str, "%A %b %d %I:%M %p")
        if event_datetime.date() - today == timedelta(days=4):
            msg = (
                f"📅 Reminder: **{event['home_or_away']} vs {event['opponent']}**\n"
                f"🕒 {event['date']} at {event['time']}\n"
                f"📍 Location: {event['location']}"
            )
            await channel.send(msg)


bot.run(TOKEN)
