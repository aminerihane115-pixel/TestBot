import discord
import os
import datetime
import requests
import json
from dotenv import load_dotenv
from discord.ext import commands
from keep_alive import keep_alive

load_dotenv()

# --- CONFIGURATION ---
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
DB_FILE = "db_links.json"

# TES IDs (Ne pas toucher)
SUGGESTION_CHANNEL_ID = 1453864717897699382
ROLE_MODO_ID = 1453864714915287102

# --- GESTION DB ---
def load_db():
    if not os.path.exists(DB_FILE): return {}
    with open(DB_FILE, "r") as f:
        try: return json.load(f)
        except: return {}

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=4)

def is_banned(user_id):
    db = load_db()
    return str(user_id) in db.get("banned_users", [])

def get_tmdb(endpoint):
    """Fonction unique pour parler à TMDB"""
    url = f"https://api.themoviedb.org/3/{endpoint}?api_key={TMDB_API_KEY}&language=fr-FR"
    return requests.get(url).json()

# --- SYSTÈME DE SUGGESTIONS (INTERACTIF) ---
class SuggestionView(discord.ui.View):
    def __init__(self, user_id, titre):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.titre = titre

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        role = interaction.guild.get_role(ROLE_MODO_ID)
        if role in interaction.user.roles or interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("❌ Seuls les modérateurs peuvent faire cela.", ephemeral=True)
        return False

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await bot.fetch_user(self.user_id)
        try:
            await user.send(f"✅ Ta suggestion pour **{self.titre}** a été acceptée ! Elle sera bientôt disponible.")
        except: pass
        await interaction.response.edit_message(content=f"✅ Suggestion acceptée par {interaction.user.mention} pour {self.titre}", view=None)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectReasonModal(self.user_id, self.titre))

class RejectReasonModal(discord.ui.Modal, title="Raison du refus"):
    raison = discord.ui.TextInput(label="Pourquoi refuser ?", placeholder="Ex: Déjà présent, Introuvable...")
    def __init__(self, user_id, titre):
        super().__init__()
        self.user_id, self.titre = user_id, titre

    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        try:
            await user.send(f"❌ Ta suggestion pour **{self.titre}** a été refusée.\n**Raison :** {self.raison.value}")
        except: pass
        await interaction.response.edit_message(content=f"❌ Refusé par {interaction.user.mention} : {self.raison.value}", view=None)

# --- NAVIGATION SÉRIES ---
class EpisodeSelect(discord.ui.Select):
    def __init__(self, serie_id, s_num, episodes):
        options = [discord.SelectOption(label=f"E{e['episode_number']} - {e['name'][:50]}", value=f"{serie_id}|{s_num}|{e['episode_number']}") for e in episodes[:25]]
        super().__init__(placeholder="Choisissez l'épisode...", options=options)

    async def callback(self, interaction: discord.Interaction):
        s_id, s_num, e_num = self.values[0].split('|')
        db = load_db()
        cle = f"{s_id}_S{s_num}_E{e_num}"
        lien = db.get(cle)
        
        view = discord.ui.View()
        if lien:
            view.add_item(discord.ui.Button(label="▶️ Regarder", url=lien, style=discord.ButtonStyle.link))
        else:
            btn_s = discord.ui.Button(label="Faire une suggestion", style=discord.ButtonStyle.primary)
            async def s_c(i):
                chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
                await chan.send(f"📥 **Suggestion** : Episode {cle} par {i.user.mention}", view=SuggestionView(i.user.id, f"Ep {cle}"))
                await i.response.send_message("✅ Envoyé au staff !", ephemeral=True)
            btn_s.callback = s_c
            view.add_item(btn_s)
        
        await interaction.response.send_message(f"Épisode {e_num} :", view=view, ephemeral=True)

class SaisonSelect(discord.ui.Select):
    def __init__(self, serie_id, saisons):
        options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=f"{serie_id}|{s['season_number']}") for s in saisons if s['season_number'] > 0]
        super().__init__(placeholder="Choisissez la saison...", options=options)

    async def callback(self, interaction: discord.Interaction):
        s_id, s_num = self.values[0].split('|')
        data = get_tmdb(f"tv/{s_id}/season/{s_num}")
        view = discord.ui.View().add_item(EpisodeSelect(s_id, s_num, data.get('episodes', [])))
        await interaction.response.send_message(f"Saison {s_num} :", view=view, ephemeral=True)

# --- RECHERCHE ---
class SearchModal(discord.ui.Modal, title="🎬 Recherche Pathé"):
    recherche = discord.ui.TextInput(label="Quel film/série recherchez-vous ?", min_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = get_tmdb(f"search/multi?query={self.recherche.value}")
        results = data.get('results', [])
        
        options = []
        for r in results:
            m_type = r.get('media_type')
            if m_type in ['movie', 'tv']:
                titre = r.get('title') or r.get('name')
                date = r.get('release_date') or r.get('first_air_date') or "????"
                options.append(discord.SelectOption(label=titre[:100], description=f"{date[:4]}", value=f"{m_type}|{r['id']}"))

        if not options: return await interaction.followup.send("❌ Aucun résultat.")

        select = discord.ui.Select(placeholder="Choisissez...", options=options[:25])
        async def sel_callback(inter):
            m_type, m_id = select.values[0].split('|')
            info = get_tmdb(f"{m_type}/{m_id}")
            titre = info.get('title') or info.get('name')
            embed = discord.Embed(title=f"🎬 {titre}", description=info.get('overview', '')[:500], color=0x2b2d31)
            if info.get('poster_path'): embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
            embed.set_footer(text=f"ID TMDB : {m_id}")

            view = discord.ui.View()
            if m_type == 'movie':
                db = load_db()
                lien = db.get(str(m_id))
                if lien: view.add_item(discord.ui.Button(label="▶️ Regarder", url=lien, style=discord.ButtonStyle.link))
                else:
                    btn_s = discord.ui.Button(label="Faire une suggestion", style=discord.ButtonStyle.primary)
                    async def s_c(i):
                        chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
                        await chan.send(f"📥 **Suggestion** : {titre} par {i.user.mention}", view=SuggestionView(i.user.id, titre))
                        await i.response.send_message("✅ Envoyé au staff !", ephemeral=True)
                    btn_s.callback = s_c
                    view.add_item(btn_s)
            else:
                view.add_item(SaisonSelect(m_id, info.get('seasons', [])))

            await inter.response.send_message(embed=embed, view=view, ephemeral=True)
        
        select.callback = sel_callback
        await interaction.followup.send("Résultats :", view=discord.ui.View().add_item(select), ephemeral=True)

# --- BOUTONS CATALOGUE ---
class CatalogueButtons(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    async def search(self, interaction, button): await interaction.response.send_modal(SearchModal())
    @discord.ui.button(label="Anti-Pub", style=discord.ButtonStyle.danger, emoji="🚫")
    async def anti(self, interaction, button): await interaction.response.send_message("🛡️ Utilisez un bloqueur de pub !", ephemeral=True)

# --- COMMANDES ---

@bot.tree.command(name="ajouter_lien", description="Admin: Lier un ID TMDB à un lien")
async def add_link(interaction: discord.Interaction, tmdb_id: str, lien: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin uniquement.", ephemeral=True)
    db = load_db(); db[tmdb_id] = lien; save_db(db)
    await interaction.response.send_message(f"✅ Lié : {tmdb_id}", ephemeral=True)

@bot.tree.command(name="ban", description="Bannir du serveur + Blacklist Bot")
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Banni via le Bot Pathé"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Pas la permission.", ephemeral=True)
    
    # 1. Blacklist Bot
    db = load_db()
    bans = db.get("banned_users", [])
    if str(membre.id) not in bans: bans.append(str(membre.id))
    db["banned_users"] = bans; save_db(db)

    # 2. Ban Serveur
    try:
        await membre.ban(reason=raison)
        await interaction.response.send_message(f"🚫 **{membre.name}** banni du serveur et du bot.")
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Blacklisté du bot, mais erreur ban serveur : {e}", ephemeral=True)

@bot.tree.command(name="unban", description="Débannir du serveur + Enlever Blacklist")
async def unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Pas la permission.", ephemeral=True)

    # 1. Enlever Blacklist Bot
    db = load_db()
    bans = db.get("banned_users", [])
    if user_id in bans:
        bans.remove(user_id)
        db["banned_users"] = bans
        save_db(db)
        msg_bot = "✅ Retiré de la blacklist du bot."
    else:
        msg_bot = "ℹ️ N'était pas dans la blacklist du bot."

    # 2. Deban Serveur
    try:
        user_obj = discord.Object(id=int(user_id))
        await interaction.guild.unban(user_obj)
        msg_discord = "✅ Débanni du serveur Discord."
    except Exception as e:
        msg_discord = f"⚠️ Erreur débannissement serveur (Peut-être déjà débanni ou ID invalide)."

    await interaction.response.send_message(f"{msg_bot}\n{msg_discord}")

@bot.tree.command(name="catalogue", description="Ouvrir le catalogue")
async def catalogue(interaction: discord.Interaction):
    if is_banned(interaction.user.id): return await interaction.response.send_message("❌ Vous êtes banni.", ephemeral=True)
    embed = discord.Embed(title="✨ PATHÉ STREAMING", description="Cherchez parmi 90,000 titres.", color=0x2b2d31)
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png")
    await interaction.response.send_message(embed=embed, view=CatalogueButtons())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ {bot.user} prêt.")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))