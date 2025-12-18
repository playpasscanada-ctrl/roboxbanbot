import os, json, time, threading, requests
from datetime import datetime
from flask import Flask
import discord
from discord import app_commands

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", 8080))
OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS","").split(",") if x]

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
ACCESS = load(ACCESS_FILE)
MAINT = load(MAINT_FILE)
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
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced")

bot = Bot()

def owner(interaction):
    return interaction.user.id in OWNER_IDS

@bot.event
async def on_ready():
    print("Bot Online")

# ================= SLASH COMMANDS =================

@bot.tree.command(name="add", description="Permanent ban user")
async def add(interaction: discord.Interaction, user_id: str):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    WAITING[interaction.user.id] = {"type":"perm","uid":user_id}
    u,d = roblox(user_id)

    await interaction.response.send_message(
        embed=embed(
            "🔨 PERMANENT BAN",
            f"**Name:** {d}\n**Username:** @{u}\n**ID:** `{user_id}`\n\n✍️ Type reason",
            0xff0000
        )
    )

@bot.tree.command(name="tempban", description="Temporary ban user")
async def tempban(interaction: discord.Interaction, user_id: str, minutes: int):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    WAITING[interaction.user.id] = {"type":"temp","uid":user_id,"mins":minutes}
    u,d = roblox(user_id)

    await interaction.response.send_message(
        embed=embed(
            "⏱ TEMP BAN",
            f"**Name:** {d}\n**Username:** @{u}\n**ID:** `{user_id}`\n"
            f"**Time:** `{minutes} minutes`\n\n✍️ Type reason",
            0xffa500
        )
    )

@bot.tree.command(name="unban", description="Unban user")
async def unban(interaction: discord.Interaction, user_id: str):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    BLOCKED.pop(user_id, None)
    save(BLOCKED_FILE, BLOCKED)

    await interaction.response.send_message(
        embed=embed("✅ UNBANNED", f"User `{user_id}` unbanned", 0x00ff00)
    )

@bot.tree.command(name="list", description="Show banned users")
async def listban(interaction: discord.Interaction):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    cleanup()
    if not BLOCKED:
        return await interaction.response.send_message(
            embed=embed("📭 No Bans","No users banned",0x00ff00)
        )

    txt=""
    for i,(uid,d) in enumerate(BLOCKED.items(),1):
        u,n = roblox(uid)
        t="PERM" if d["perm"] else f"{int((d['expire']-time.time())/60)}m"
        txt+=f"**{i}. {n} (@{u})**\nID:`{uid}` `{t}`\nReason:{d['msg']}\n\n"

    await interaction.response.send_message(embed=embed("🚫 Blocked Users",txt))

# ================= NEW COMMANDS =================

@bot.tree.command(name="kick", description="Kick player from game")
async def kick(interaction: discord.Interaction, user_id: str):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    KICKS[user_id] = time.time()
    save(KICK_FILE, KICKS)

    await interaction.response.send_message(
        embed=embed("🦵 KICK", f"User `{user_id}` will be kicked", 0xff5555)
    )

@bot.tree.command(name="access", description="Access control")
async def access(interaction: discord.Interaction, action: str, user_id: str = None):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    if action == "on":
        ACCESS["enabled"] = True
    elif action == "off":
        ACCESS["enabled"] = False
    elif action == "add" and user_id:
        ACCESS["users"][user_id] = True
    elif action == "remove" and user_id:
        ACCESS["users"].pop(user_id, None)
    elif action == "list":
        users = "\n".join(f"`{u}`" for u in ACCESS["users"]) or "No users"
        return await interaction.response.send_message(
            embed=embed("🔐 ACCESS LIST", users, 0x00ff00)
        )

    save(ACCESS_FILE, ACCESS)
    await interaction.response.send_message(
        embed=embed("🔐 ACCESS UPDATED", f"Action: `{action}`", 0x00ff00)
    )

@bot.tree.command(name="maintenance", description="Maintenance mode")
async def maintenance(interaction: discord.Interaction, mode: str):
    if not owner(interaction):
        return await interaction.response.send_message("No permission")

    MAINT["enabled"] = (mode == "on")
    save(MAINT_FILE, MAINT)

    await interaction.response.send_message(
        embed=embed("🛠 MAINTENANCE", f"Status: `{mode.upper()}`", 0xffaa00)
    )

# ================= REASON INPUT =================
@bot.event
async def on_message(msg):
    if msg.author.id in WAITING:
        d = WAITING[msg.author.id]
        uid = d["uid"]
        reason = msg.content

        if d["type"]=="perm":
            BLOCKED[uid]={"perm":True,"msg":reason}
            title="✅ PERM BAN ADDED"
            color=0xff0000
        else:
            BLOCKED[uid]={
                "perm":False,
                "msg":reason,
                "expire":time.time()+d["mins"]*60
            }
            title="✅ TEMP BAN ADDED"
            color=0xffa500

        save(BLOCKED_FILE, BLOCKED)
        del WAITING[msg.author.id]

        await msg.channel.send(embed=embed(
            title,
            f"**User ID:** `{uid}`\n**Reason:** {reason}",
            color
        ))

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
    if not ACCESS.get("enabled"):
        return "true"
    return "true" if uid in ACCESS.get("users",{}) else "false"

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
    if d and (d["perm"] or time.time()<d.get("expire",0)):
        return "true"
    return "false"

@app.route("/reason/<uid>")
def reason(uid):
    cleanup()
    d = BLOCKED.get(uid)
    return d.get("msg","") if d else ""

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_flask).start()
bot.run(TOKEN)
