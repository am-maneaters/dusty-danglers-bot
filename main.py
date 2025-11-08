import discord
from discord.ext import commands
from datetime import datetime, timedelta, time as dtime
import json
import os
from flask import Flask
from threading import Thread
import asyncio

# --- Flask web server to keep Render alive ---
app = Flask("")


@app.route("/")
def home():
    return "Bot is running!"


def run():
    app.run(host="0.0.0.0", port=8080)


Thread(target=run).start()

# --- Discord bot setup ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Event storage ---
EVENTS_FILE = "events.json"


def load_events():
    with open(EVENTS_FILE, "r") as f:
        return json.load(f)


# --- Helper functions ---
def format_event_message(event):
    emoji = (
        ":dusty_danglers_night:"
        if event["home_or_away"].lower() == "home"
        else ":dusty_danglers_day:"
    )
    msg = (
        f"{emoji} **{event['home_or_away']} vs {event['opponent']}**\n"
        f"🕒 {event['date']} at {event['time']}\n"
        f"📍 Location: {event['location']}"
    )
    return msg


def get_next_event():
    events = load_events()
    now = datetime.now()
    upcoming_events = []
    for event in events:
        dt_str = f"{event['date']} {event['time']}"
        try:
            event_datetime = datetime.strptime(dt_str, "%A %b %d %I:%M %p")
        except ValueError:
            continue  # Skip malformed dates
        if event_datetime > now:
            upcoming_events.append((event_datetime, event))
    if upcoming_events:
        upcoming_events.sort(key=lambda x: x[0])
        return upcoming_events[0][1]
    return None


# --- Bot events ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.loop.create_task(
        daily_check_loop(hour=12, minute=0)
    )  # Set your desired reminder time here


# --- Commands ---
@bot.command()
async def list_events(ctx):
    events = load_events()
    if not events:
        await ctx.send("No events found.")
        return
    messages = [format_event_message(event) for event in events]
    # Discord has message length limits; send in chunks if needed
    for msg in messages:
        await ctx.send(msg)


@bot.command()
async def next_event(ctx):
    event = get_next_event()
    if not event:
        await ctx.send("No upcoming events found.")
        return
    await ctx.send(format_event_message(event))


# --- Automated 4-day reminder ---
async def daily_check_loop(hour=12, minute=0):
    """Loop that checks events at a specific time each day"""
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
        target_time = datetime.combine(now.date(), dtime(hour, minute))
        if now > target_time:
            target_time += timedelta(days=1)
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        # Check events 4 days out
        channel = bot.get_channel(CHANNEL_ID)
        events = load_events()
        today = datetime.now().date()
        for event in events:
            dt_str = f"{event['date']} {event['time']}"
            try:
                event_datetime = datetime.strptime(dt_str, "%A %b %d %I:%M %p")
            except ValueError:
                continue
            if event_datetime.date() - today == timedelta(days=4):
                await channel.send(format_event_message(event))


bot.run(TOKEN)
