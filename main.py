import os, json, time, threading, requests
from datetime import datetime
from flask import Flask
import discord
from discord import app_commands

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", 8080))
OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS","").split(",") if x]
RENDER_URL = os.getenv("RENDER_URL")

# ================= FILES =================
BLOCKED_FILE = "blocked.json"
USERS_FILE = "users.json"
ACCESS_FILE = "access.json"
MAINT_FILE = "maintenance.json"
KICK_FILE = "kick.json"

def load(f):
    try:
        with open(f,"r") as file:
            return json.load(file)
    except:
        return {}

def save(f,d):
    with open(f,"w") as file:
        json.dump(d,file)

BLOCKED = load(BLOCKED_FILE)
USERS = load(USERS_FILE)
ACCESS = load(ACCESS_FILE) or {"enabled": False, "users": {}}
MAINT = load(MAINT_FILE) or {"enabled": False}
KICKS = load(KICK_FILE)
WAITING = {}

# ================= EMBED =================
def embed(title, desc, color=0x5865F2):
    e = discord.Embed(
        title=title,
        description=desc,
        color=color,
        timestamp=datetime.utcnow()
    )
    e.set_footer(text="Ban System • Online")
    return e

# ================= ROBLOX =================
def roblox(uid):
    try:
        r = requests.get(f"https://users.roblox.com/v1/users/{uid}",timeout=5).json()
        return r.get("name","Unknown"), r.get("displayName","Unknown")
    except:
        return "Unknown","Unknown"

# ================= CLEAN =================
def cleanup():
    for uid in list(BLOCKED.keys()):
        d = BLOCKED[uid]
        if not d["perm"] and time.time() > d["expire"]:
            del BLOCKED[uid]
    save(BLOCKED_FILE, BLOCKED)

# ================= DISCORD =================
class Bot(discord.Client):
    def init(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = Bot()

def owner(interaction):
    return interaction.user.id in OWNER_IDS

@bot.event
async def on_ready():
    print("Bot Online")

# ================= SLASH COMMANDS =================

@bot.tree.command(name="access")
async def access(interaction: discord.Interaction, action: str, user_id: str = None):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    action = action.lower()

    if action == "on":
        ACCESS["enabled"] = True

    elif action == "off":
        ACCESS["enabled"] = False

    elif action == "add" and user_id:
        ACCESS["users"][str(user_id)] = True

    elif action == "remove" and user_id:
        ACCESS["users"].pop(str(user_id), None)

    elif action == "list":
        users = "\n".join(f"`{u}`" for u in ACCESS["users"]) or "No users"
        return await interaction.response.send_message(
            embed=embed("🔐 ACCESS LIST", users, 0x00ff00)
        )

    save(ACCESS_FILE, ACCESS)

    await interaction.response.send_message(
        embed=embed(
            "🔐 ACCESS UPDATED",
            f"**Action:** `{action}`\n**User:** `{user_id or 'N/A'}`",
            0x00ff00
        )
    )

# ================= FLASK =================
app = Flask(__name__)

@app.route("/ping")
def ping():
    return "pong"

@app.route("/maintenance")
def maintenance_check():
    return "true" if MAINT.get("enabled") else "false"

@app.route("/access/<uid>")
def access_check(uid):
    # Access mode OFF = everyone allowed
    if not ACCESS.get("enabled"):
        return "true"

    # Access mode ON = only whitelisted IDs
    return "true" if str(uid) in ACCESS.get("users", {}) else "false"

@app.route("/kickcheck/<uid>")
def kick_check(uid):
    if uid in KICKS:
        del KICKS[uid]
        save(KICK_FILE, KICKS)
        return "kick"
    return "ok"

@app.route("/check/<uid>")
def check(uid):
    cleanup()
    d = BLOCKED.get(uid)
    if d and (d["perm"] or time.time() < d.get("expire", 0)):
        return "true"
    return "false"

@app.route("/reason/<uid>")
def reason(uid):
    cleanup()
    d = BLOCKED.get(uid)
    return d.get("msg","") if d else ""

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ================= KEEP ALIVE =================
def keep_alive():
    if not RENDER_URL:
        return
    while True:
        try:
            requests.get(f"{RENDER_URL}/ping", timeout=5)
        except:
            pass
        time.sleep(300)

threading.Thread(target=run_flask).start()
threading.Thread(target=keep_alive, daemon=True).start()

bot.run(TOKEN)
