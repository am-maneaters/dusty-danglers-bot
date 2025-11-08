import discord
from discord.ext import commands
from datetime import datetime, timedelta, time as dtime
import json
import os
from flask import Flask
from threading import Thread
import asyncio
from dotenv import load_dotenv
import random
from typing import TypedDict
import requests
from bs4 import BeautifulSoup

load_dotenv()

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

# --- Constants ----
EMOJI_HOME = "<:dusty_danglers_night:1250533925156290761>"
EMOJI_AWAY = "<:dusty_danglers_day:1250533926796267530>"
BASE_URL = "https://ahahockey.com"


class Game(TypedDict):
    date: str
    time: str
    opponent: str
    opponent_link: str
    home_or_away: str
    location: str
    game_link: str


def load_games() -> list[Game]:
    with open(EVENTS_FILE, "r") as f:
        games = json.load(f)
        # parse dates
        events = []
        for game in games:
            event_datetime = parse_event_datetime(game)
            event = {
                "date": event_datetime.strftime("%A, %B %-d"),
                "time": event_datetime.strftime("%-I:%M%p"),
                "datetime": event_datetime,
                "opponent": game.get("opponent", ""),
                "opponent_link": f"{BASE_URL}{game.get("opponent_link", "")}",
                "home_or_away": game.get("home_or_away", ""),
                "location": game.get("location", ""),
                "game_link": f"{BASE_URL}{game.get("game_link", "")}",
            }
            events.append(event)
    return events


# --- Helper functions ---
def format_event_message(event):
    emoji = EMOJI_HOME if event["home_or_away"].lower() == "home" else EMOJI_AWAY

    msg = (
        f"@everyone Our next game is coming up!\n\n"
        f"{emoji} **{event['home_or_away']} vs [{event['opponent']}]({event['opponent_link']})**\n\n"
        f"🕒 {event["date"]} at {event["time"]}\n\n"
        f"📍 Location: {event['location']}\n\n"
        f":white_check_mark: RSVP [here]({event['game_link']})"
    )
    return msg


def parse_event_datetime(event):
    dt_str = f"{event['date']} {event['time']}"
    try:
        return datetime.strptime(dt_str, "%A %b %d %Y %-I:%M %p")
    except ValueError:
        print(f"Error parsing date/time for event: {event}")
        return None


def get_next_game():
    events = load_games()
    now = datetime.now()
    upcoming_events = []
    for event in events:
        event_datetime = event["datetime"]
        if event_datetime > now:
            upcoming_events.append((event_datetime, event))
    if upcoming_events:
        upcoming_events.sort(key=lambda x: x[0])
        return upcoming_events[0][1]
    return None


from bs4 import BeautifulSoup


def parse_dusty_danglers_summary(game: dict):
    """Fetch and format a Dusty Danglers game summary from AHA Hockey."""
    game_link = game["game_link"]
    resp = requests.get(game_link)
    if resp.status_code != 200:
        return "❌ Could not fetch game summary."

    soup = BeautifulSoup(resp.text, "html.parser")
    summary = {}

    # --- Game Info ---
    summary["game_info"] = (
        f"🏒 **Game Summary vs {game['opponent']} ({game['date']})**\n"
    )

    # --- Final Score ---
    score_table = soup.find("table", class_="scorebox")
    dusty_score = None
    opponent_score = None
    if score_table:
        rows = score_table.find_all("tr")
        for row in rows:
            team_name = row.find("a")
            if not team_name:
                continue
            tds = row.find_all("td")
            team_score = tds[-1].get_text(strip=True)
            if "Dusty Danglers" in team_name.text:
                dusty_score = int(team_score)
                summary["final_score"] = {
                    "team": "Dusty Danglers",
                    "periods": [td.get_text(strip=True) for td in tds[1:-1]],
                    "final": team_score,
                }
            else:
                opponent_score = int(team_score)
                summary["opponent_score"] = {
                    "team": team_name.text.strip(),
                    "periods": [td.get_text(strip=True) for td in tds[1:-1]],
                    "final": team_score,
                }

    # Compute win/loss if both scores are known
    def format_loss_result(dusty_score, opponent_score, opponent_name):
        loss_result_templates = [
            "the danglers fell to the {opponent_name} with a final score of {opponent_score}-{dusty_score} :(",
            "rusty danglers, am i right? we lost to the {opponent_name}, {opponent_score}-{dusty_score}.",
            "turns out {dusty_score} is less than {opponent_score}. {opponent_name} beat us.",
            "{opponent_name} beat us??? how did we lose {opponent_score} to {dusty_score}??",
            "breaking news, the dusty danglers are in fact dusty. they lost to the {opponent_name}, {opponent_score}-{dusty_score}.",
            "i, the dusty dangler bot, simply would not have lost {opponent_score}-{dusty_score} to the {opponent_name}.",
            "i will pull this car over if you lose {opponent_score}-{dusty_score} to the {opponent_name} again.",
            "i'm tired of this, grandpa. we lost to the {opponent_name}, {opponent_score}-{dusty_score}.",
        ]
        return random.choice(loss_result_templates).format(
            dusty_score=dusty_score,
            opponent_score=opponent_score,
            opponent_name=opponent_name,
        )

    def format_win_result(dusty_score, opponent_score, opponent_name):
        win_result_templates = [
            "ezpz, we won {opponent_score}-{dusty_score} against {opponent_name}.",
            "imagine losing to the {opponent_name}, i couldn't! we won {dusty_score}-{opponent_score}.",
            "i almost feel bad for the {opponent_name}, we won {dusty_score}-{opponent_score} so easily.",
            "that's how you win a hockey game. {dusty_score}-{opponent_score} over the {opponent_name}.",
            "the dusty danglers are simply built different. we beat the {opponent_name}, {dusty_score}-{opponent_score}.",
            "another day, another W. we defeated the {opponent_name}, {dusty_score}-{opponent_score}.",
            "i would have bet my life savings on us winning {dusty_score}-{opponent_score} against {opponent_name}.",
            "did you see that? we crushed the {opponent_name}, {dusty_score}-{opponent_score}.",
            "i can't believe we won {dusty_score}-{opponent_score} against the {opponent_name}. oh wait yeah i can.",
            "we might never lose again. {opponent_name} lose {dusty_score}-{opponent_score}.",
            "remember when we lost to the {opponent_name}? me neither. cuz we won {dusty_score}-{opponent_score}.",
            "how about them danglers? we beat the {opponent_name}, {dusty_score}-{opponent_score}.",
            "perhaps the greatest hockey game ever played: dusty danglers {dusty_score}, {opponent_name} {opponent_score}.",
            "{dusty_score}>{opponent_score}, a mathematical proof that we beat the {opponent_name}.",
        ]
        return random.choice(win_result_templates).format(
            dusty_score=dusty_score,
            opponent_score=opponent_score,
            opponent_name=opponent_name,
        )

    result = ""
    if dusty_score is not None and opponent_score is not None:
        if dusty_score > opponent_score:
            result = format_win_result(dusty_score, opponent_score, game["opponent"])
        elif dusty_score < opponent_score:
            result = format_loss_result(dusty_score, opponent_score, game["opponent"])
        else:
            result = "🤝 **Tie Game.**"

    # --- Goals ---
    goals = []
    for row in soup.select("h3:-soup-contains('Goals') + table tbody tr"):
        if not (
            row.find("td", string=lambda x: x and "Dusty Danglers" in x)
            or row.find("img", alt="Dusty Danglers")
        ):
            continue
        cols = row.find_all("td")
        goals.append(
            {
                "scorer": cols[0].get_text(strip=True),
                "assist1": cols[2].get_text(strip=True),
                "assist2": cols[3].get_text(strip=True),
                "period": cols[5].get_text(strip=True),
                "time": cols[6].get_text(strip=True),
            }
        )
    summary["goals"] = goals

    # --- Goalies ---
    goalies = []
    for row in soup.select("h3:-soup-contains('Goalies') + table tbody tr"):
        if not row.find("img", alt="Dusty Danglers"):
            continue
        cols = row.find_all("td")
        goalies.append(
            {
                "player": cols[0].get_text(strip=True),
                "shots_against": cols[2].get_text(strip=True),
                "goals_against": cols[3].get_text(strip=True),
                "save_pct": cols[4].get_text(strip=True),
            }
        )
    summary["goalies"] = goalies

    # --- Shots on Goal ---
    shots = {}
    for h3 in soup.find_all("h3"):
        if h3.text.strip() == "Shots on Goal":
            table = h3.find_next("table")
            for row in table.find_all("tr"):
                if row.find("img", alt="Dusty Danglers"):
                    tds = row.find_all("td")
                    shots = {
                        "periods": [td.get_text(strip=True) for td in tds[1:-1]],
                        "total": tds[-1].get_text(strip=True),
                    }
                    break
    summary["shots_on_goal"] = shots

    # --- Format the Summary ---
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(summary.get("game_info", ""))

    # Final score + result
    if "final_score" in summary and "opponent_score" in summary:
        lines.append(f"**Result**: *{result}*")

    # Shots on goal
    if summary.get("shots_on_goal"):
        s = summary["shots_on_goal"]
        period_labels = ["1st", "2nd", "3rd", "OT"]
        period_texts = []
        for i, val in enumerate(s["periods"]):
            label = period_labels[i] if i < len(period_labels) else f"P{i+1}"
            period_texts.append(f"{label}: {val}")
        lines.append("\n🎯 **Shots on Goal**")
        lines.append(" • " + " | ".join(period_texts) + f" | **Total: {s['total']}**")

    # Goals section
    if goals:
        lines.append("\n🥅 **Goals**")
        for g in goals:
            assists = [a for a in [g["assist1"], g["assist2"]] if a]
            assist_text = f" _(Assists: {', '.join(assists)})_" if assists else ""
            lines.append(f"• {g['scorer']} — {g['period']}P {g['time']}{assist_text}")

        # get player with the most goals/assists
        player_stats = {}
        for g in goals:
            scorer = g["scorer"]
            player_stats[scorer] = player_stats.get(scorer, 0) + 1
            for assist in [g["assist1"], g["assist2"]]:
                if assist:
                    player_stats[assist] = player_stats.get(assist, 0) + 1

        # determine MVP (handle ties)
        if player_stats:
            max_points = max(player_stats.values())
            top_players = [p for p, pts in player_stats.items() if pts == max_points]
            if max_points > 1:
                if len(top_players) == 1:
                    lines.append(
                        f"\n🏆 Big game for **{top_players[0]}** with {max_points} point(s)!"
                    )
                else:
                    names = ", ".join(f"**{p}**" for p in top_players)
                    lines.append(f"\n🏆 MVPs: {names} — {max_points} point(s) each!")

        if len(goals) == 0:
            lines.append("• ope, we should probably try scoring more next time...")

    # Goalies section
    if goalies:
        lines.append("\n🧤 **Goalies**")
        for g in goalies:
            lines.append(
                f"• {g['player']} — {g['shots_against']} SA | {g['goals_against']} GA | {g['save_pct']} SV%"
            )
            if g["goals_against"] == "0":
                lines.append("🎉🎉🎉 shutout!!! 🎉🎉🎉")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# --- Bot events ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.loop.create_task(
        daily_check_loop(hour=10, minute=00)
    )  # Set your desired reminder time here


# --- Commands ---
@bot.command()
async def list_games(ctx: commands.Context):
    events = load_games()
    if not events:
        await ctx.send("No games found.")
        return
    messages = [format_event_message(event) for event in events]
    # Discord has message length limits; send in chunks if needed
    for msg in messages:
        await ctx.send(msg, suppress_embeds=True)


quotes = [
    ("SHOOT IT!!!", "Dan Fine"),
    ("NOT DOWN THE MIDDLE!!!", "Dan Fine"),
    ("GET IT OUT OF THERE!!!", "Dan Fine"),
    ("GET BACK!!!", "Dan Fine"),
]


@bot.command()
async def yell(ctx: commands.Context):
    quote = random.choice(quotes)
    quote = f'*"{quote[0]}"* - {quote[1]}'
    await ctx.send(quote)
    await ctx.message.delete()


@bot.command()
async def next_game(ctx: commands.Context):
    event = get_next_game()
    if not event:
        await ctx.send("No upcoming games found.")
        return
    await ctx.message.delete()
    await ctx.send(format_event_message(event), suppress_embeds=True)


@bot.command()
async def summarize_latest_game(ctx: commands.Context):
    events = load_games()
    if not events:
        await ctx.send("No games found.")
        return
    # get the most recent past game
    now = datetime.now()
    past_events = []
    for event in events:
        event_datetime = event["datetime"]
        if event_datetime < now:
            past_events.append((event_datetime, event))
    if not past_events:
        await ctx.send("No past games found.")
        return
    past_events.sort(key=lambda x: x[0], reverse=True)
    latest_game = past_events[0][1]
    summary = parse_dusty_danglers_summary(latest_game)
    await ctx.message.delete()
    await ctx.send(summary)


# --- Automated 3-day reminder ---
async def daily_check_loop(hour=10, minute=0):
    print("🔍 Checking for games 3 days out...")
    """Loop that checks games at a specific time each day"""
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
        target_time = datetime.combine(now.date(), dtime(hour, minute))
        if now > target_time:
            target_time += timedelta(days=1)
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        # Check games 3 days out
        channel = bot.get_channel(CHANNEL_ID)
        events = load_games()
        today = datetime.now().date()
        for event in events:
            event_datetime = event.get("datetime")
            if event_datetime.date() - today == timedelta(days=3):
                await channel.send(format_event_message(event), suppress_embeds=True)


bot.run(TOKEN)
