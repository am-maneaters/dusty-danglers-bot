import discord
from discord.ext import commands
from datetime import datetime, timedelta, time as dtime
import json
import os
import asyncio

from dotenv import load_dotenv
import random
from typing import TypedDict
import requests
from bs4 import BeautifulSoup

load_dotenv()

# --- Discord bot setup ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Event storage ---
EVENTS_FILE = "./events.json"

# --- Constants ----
EMOJI_HOME = "<:dusty_danglers_night:1250533925156290761>"
EMOJI_AWAY = "<:dusty_danglers_day:1250533926796267530>"
BASE_URL = "https://ahahockey.com"
DANGLERS_ROLE = "<@&1296192458073575464>"


class Game(TypedDict):
    date: str
    time: str
    opponent: str
    opponent_link: str
    home_or_away: str
    location: str
    game_link: str
    datetime: datetime


def load_games() -> list[Game]:
    with open(EVENTS_FILE, "r") as f:
        games = json.load(f)
        # parse dates
        events = []
        for game in games:
            event_datetime = parse_event_datetime(game)
            if event_datetime is None:
                print(f"Broken date {game.get('date', '')}")
            event = {
                "date": event_datetime.strftime("%A, %B %d"),
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
def format_rsvp_message(event):
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
        parsed_date = datetime.strptime(dt_str, "%A %b %d %Y %I:%M %p")
        return parsed_date
    except ValueError:
        return None


game_day_messages = [
    lambda: "WTFU ITS GAME DAY!!!",
    lambda: "GET IN LOSER, WE'RE GOING TO WIN OUR GAME TONIGHT!!!",
    lambda: "WELCOME TO DAY OF GAME",
    lambda: f"{(get_next_game()['datetime'] - datetime.now()).total_seconds():.0f} SECONDS TO GAME TIME",
    lambda: "TIME FOR AN EZ W TNIGHT!!!",
    lambda: "YOU HYPED? WELL YOU SHOULD BE, IT'S GAME DAY!!!",
    lambda: "SHAKE OFF THE DUST, DANGLERS, IT'S GAME DAY!!!",
    lambda: "I HEARD STEVE IS SCORING A HAT TRICK TONIGHT, GET HYPED!!!",
    lambda: "I HOPE YOU LIKE HOCKEY, CUZ WE HAVE HOCKEY TN!!!",
    lambda: "6-7?? MORE LIKE 7-6 IN OUR FAVOR TONIGHT!!!",
    lambda: "GRAB YOUR STICKS, IT'S GAME DAY!!!",
    lambda: "AJ'S GETTING HIS FIRST GOALIE GOAL TONIGHT, LET'S GO!!",
]


def format_game_day_message(event: Game):
    jersey_color = "light" if event["home_or_away"].lower() == "home" else "dark"
    emoji = EMOJI_HOME if event["home_or_away"].lower() == "home" else EMOJI_AWAY

    return (
        f"{DANGLERS_ROLE} {random.choice(game_day_messages)()}\n\n"
        f"{emoji} Personal reminder for <@1126284695689232415>, bring your {jersey_color} jersey\n\n"
        f"📍 See ya'll {event['time']} at {event['location']}"
    )


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


def parse_player_string(player_str):
    """Extract player name and number from a string like '#12. J. Doe'.
    Returns a tuple of (name, number) or (None, None) if parsing fails.
    Also removes capital C from the end of the name if it exists.
    """
    if not player_str:
        return None, None
    parts = player_str.split()
    if len(parts) < 2:
        return None, None
    number = parts[0].lstrip("#")
    if number.endswith("."):
        number = number[:-1].strip()
    name = " ".join(parts[1:])
    if name.endswith("C"):
        name = name[:-1].strip()
    return name, number


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
        f"🏒 **Dusty Danglers vs {game['opponent']} ({game['datetime'].strftime('%b %d')})**"
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
        scorer_name, scorer_number = parse_player_string(cols[0].get_text(strip=True))
        assist1_name, assist1_number = parse_player_string(cols[2].get_text(strip=True))
        assist2_name, assist2_number = parse_player_string(cols[3].get_text(strip=True))
        goals.append(
            {
                "scorer": f"#{scorer_number} {scorer_name}",
                "assist1": (
                    f"#{assist1_number} {assist1_name}" if assist1_name else None
                ),
                "assist2": (
                    f"#{assist2_number} {assist2_name}" if assist2_name else None
                ),
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
        goalie_name, goalie_number = parse_player_string(cols[0].get_text(strip=True))
        goalies.append(
            {
                "player": f"#{goalie_number} {goalie_name}",
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
    lines.append(summary.get("game_info", ""))

    # Final score + result
    if "final_score" in summary and "opponent_score" in summary:
        lines.append(f"*{result}*")

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
        # Split goals into periods
        period_goals = {
            "1": [],
            "2": [],
            "3": [],
        }

        for g in goals:
            period = g["period"]
            if period not in period_goals:
                period_goals[period] = []
            period_goals[period].append(g)

        for period in sorted(period_goals.keys()):
            lines.append(f"\n⏱️ **Period {period} Goals**")
            for g in period_goals[period]:
                assist_text = ""
                if g["assist1"] and not g["assist2"]:
                    assist_text = f" _(from {g['assist1']})_"
                if g["assist1"] and g["assist2"]:
                    assist_text = f" _(from {g['assist1']}, {g['assist2']})_"
                if not g["assist1"] and not g["assist2"]:
                    assist_text = " _(Unassisted)_"
                lines.append(f"• {g['time']} - {g['scorer']}{assist_text}")
            if not period_goals[period]:
                lines.append("• No goals scored in this period.")

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
                    names = ", ".join(f"{p}" for p in top_players)
                    lines.append(
                        f"\n🏆 **MVPs**\n {names} — {max_points} point(s) each!"
                    )

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

    return "\n".join(lines)


# --- Bot events ---
@bot.event
async def on_ready():
    await bot.tree.sync()  # Registers all slash commands with Discord
    print(f"✅ Logged in as {bot.user}")
    bot.loop.create_task(
        daily_check_loop(hour=10, minute=00)
    )  # Set your desired reminder time here


# --- Commands ---
@bot.tree.command(
    name="list_games", description="List all upcoming Dusty Danglers games"
)
async def list_games(interaction: discord.Interaction):
    events = load_games()
    if not events:
        await interaction.response.send_message("No games found.")
        return
    messages = [format_rsvp_message(event) for event in events]
    # Discord has message length limits; send in chunks if needed
    for msg in messages:
        await interaction.response.send_message(msg, suppress_embeds=True)


quotes = [
    ("SHOOT IT!!!", "Dan Fine"),
    ("NOT DOWN THE MIDDLE!!!", "Dan Fine"),
    ("GET IT OUT OF THERE!!!", "Dan Fine"),
    ("GET BACK!!!", "Dan Fine"),
]


@bot.tree.command(name="fine_yell_random", description="Send a random Dan Fine quote")
async def fine_yell_random(interaction: discord.Interaction):
    quote = random.choice(quotes)
    quote = f'*"{quote[0]}"* - {quote[1]}'
    await interaction.response.send_message(quote)


@bot.tree.command(name="fine_yell", description="Create a Dan Fine quote")
async def fine_yell(interaction: discord.Interaction, message: str):
    # make all caps and add exclamation marks
    arg = message.upper()
    if not arg.endswith("!"):
        arg += "!!!"
    quote = f'*"{arg}"* - Dan Fine'
    await interaction.response.send_message(quote)


@bot.tree.command(name="game_day_message", description="Get a message for game day")
async def game_day_message(interaction: discord.Interaction):
    event = get_next_game()
    if not event:
        await interaction.response.send_message("No upcoming games found.")
        return
    message = format_game_day_message(event)
    await interaction.response.send_message(message)


@bot.tree.command(name="next_game", description="Get the next upcoming game")
async def next_game(interaction: discord.Interaction):
    event = get_next_game()
    if not event:
        await interaction.response.send_message("No upcoming games found.")
        return
    await interaction.response.send_message(
        format_rsvp_message(event), suppress_embeds=True
    )


@bot.tree.command(name="dangler_bot_info", description="Get information about the bot")
async def bot_info(interaction: discord.Interaction):
    info = (
        "🤖 **Dusty Danglers Bot**\n\n"
        "📚 **Features:**\n"
        "- Lists upcoming games\n"
        "- Provides game summaries\n"
        "- Sends automated reminders\n"
        "- Provides Dan Fine quotes\n\n"
        "⚙️ **Developed by:** Sem\n"
        "🌐 **Source Code:** [GitHub Repository](https://github.com/am-maneaters/dusty-danglers-bot)"
    )
    await interaction.response.send_message(info)


@bot.tree.command(
    name="danglers_bot_message", description="Author a message as the bot"
)
async def danglers_bot_message(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)


@bot.tree.command(
    name="summarize_latest_game", description="Get a summary of the latest game"
)
async def summarize_latest_game(interaction: discord.Interaction):
    events = load_games()
    if not events:
        await interaction.response.send_message("No games found.")
        return
    # get the most recent past game
    now = datetime.now()
    past_events = []
    for event in events:
        event_datetime = event["datetime"]
        if event_datetime < now:
            past_events.append((event_datetime, event))
    if not past_events:
        await interaction.response.send_message("No past games found.")
        return
    past_events.sort(key=lambda x: x[0], reverse=True)
    latest_game = past_events[0][1]
    summary = parse_dusty_danglers_summary(latest_game)
    await interaction.response.send_message(summary)


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
                await channel.send(format_rsvp_message(event), suppress_embeds=True)


bot.run(TOKEN)
