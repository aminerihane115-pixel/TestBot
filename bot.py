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
DB_FILE = "/data/db_links.json"

# TES IDs
SUGGESTION_CHANNEL_ID = 1453864717897699382
ROLE_MODO_ID = 1453864714915287102

# --- GESTION DB ---
def load_db():
    if not os.path.exists(DB_FILE): 
        return {"links": {}, "favorites": {}, "banned_users": []}
    with open(DB_FILE, "r") as f:
        try: 
            data = json.load(f)
            # Migration auto vers le nouveau format si nécessaire
            if "links" not in data:
                return {"links": data, "favorites": {}, "banned_users": []}
            return data
        except: 
            return {"links": {}, "favorites": {}, "banned_users": []}

def save_db(db):
    with open(DB_FILE, "w") as f: 
        json.dump(db, f, indent=4)

def is_banned(user_id):
    db = load_db()
    return str(user_id) in db.get("banned_users", [])

# --- FONCTIONS TMDB ---
def search_tmdb(query):
    url = f"https://api.themoviedb.org/3/search/multi"
    params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'fr-FR'}
    try:
        return requests.get(url, params=params).json().get('results', [])
    except:
        return []

def get_details(endpoint):
    url = f"https://api.themoviedb.org/3/{endpoint}"
    params = {'api_key': TMDB_API_KEY, 'language': 'fr-FR'}
    return requests.get(url, params=params).json()

# --- SYSTÈME DE FAVORIS ---
class FavButton(discord.ui.Button):
    def __init__(self, m_id, titre):
        super().__init__(label="Favoris", style=discord.ButtonStyle.secondary, emoji="❤️")
        self.m_id = str(m_id)
        self.titre = titre

    async def callback(self, interaction: discord.Interaction):
        db = load_db()
        u_id = str(interaction.user.id)
        if u_id not in db["favorites"]: db["favorites"][u_id] = []
        
        # Vérifier si déjà présent
        if any(f['id'] == self.m_id for f in db["favorites"][u_id]):
            # On le retire s'il existe déjà (Toggle)
            db["favorites"][u_id] = [f for f in db["favorites"][u_id] if f['id'] != self.m_id]
            save_db(db)
            return await interaction.response.send_message(f"💔 **{self.titre}** retiré des favoris.", ephemeral=True)
        
        db["favorites"][u_id].append({"id": self.m_id, "titre": self.titre})
        save_db(db)
        await interaction.response.send_message(f"❤️ **{self.titre}** ajouté aux favoris !", ephemeral=True)

# --- SYSTÈME DE SUGGESTIONS ---
class SuggestionView(discord.ui.View):
    def __init__(self, user_id, titre):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.titre = titre

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        role = interaction.guild.get_role(ROLE_MODO_ID)
        if role in interaction.user.roles or interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message("❌ Réservé aux modérateurs.", ephemeral=True)
        return False

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await bot.fetch_user(self.user_id)
        try: await user.send(f"✅ Ta suggestion pour **{self.titre}** a été acceptée !")
        except: pass
        await interaction.response.edit_message(content=f"✅ **Accepté** par {interaction.user.mention} : {self.titre}", view=None)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectReasonModal(self.user_id, self.titre))

class RejectReasonModal(discord.ui.Modal, title="Raison du refus"):
    raison = discord.ui.TextInput(label="Pourquoi ?", placeholder="Ex: Introuvable...")
    def __init__(self, user_id, titre):
        super().__init__()
        self.user_id, self.titre = user_id, titre

    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        try: await user.send(f"❌ Suggestion **{self.titre}** refusée : {self.raison.value}")
        except: pass
        await interaction.response.edit_message(content=f"❌ **Refusé** par {interaction.user.mention} : {self.titre} ({self.raison.value})", view=None)

# --- NAVIGATION SÉRIES ---
class EpisodeSelect(discord.ui.Select):
    def __init__(self, serie_id, s_num, episodes):
        options = [discord.SelectOption(label=f"E{e['episode_number']} - {e['name'][:50]}", value=f"{serie_id}|{s_num}|{e['episode_number']}") for e in episodes[:25]]
        super().__init__(placeholder="Choisis l'épisode...", options=options)

    async def callback(self, interaction: discord.Interaction):
        s_id, s_num, e_num = self.values[0].split('|')
        db = load_db()
        cle = f"{s_id}_S{s_num}_E{e_num}"
        lien = db["links"].get(cle)
        
        view = discord.ui.View()
        if lien:
            view.add_item(discord.ui.Button(label="▶️ Regarder", url=lien, style=discord.ButtonStyle.link))
        else:
            view.add_item(discord.ui.Button(label="⌛ Bientôt disponible", disabled=True, style=discord.ButtonStyle.secondary))
            btn = discord.ui.Button(label="Suggérer", style=discord.ButtonStyle.primary)
            async def suggest_callback(i):
                chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
                await chan.send(f"📥 **Suggestion Série** : {cle} par {i.user.mention}", view=SuggestionView(i.user.id, f"Série {cle}"))
                await i.response.send_message("✅ Demande envoyée au staff !", ephemeral=True)
            btn.callback = suggest_callback
            view.add_item(btn)
        
        await interaction.response.send_message(f"📺 **{cle}** sélectionné (ID TMDB: {s_id}) :", view=view, ephemeral=True)

class SaisonSelect(discord.ui.Select):
    def __init__(self, serie_id, saisons):
        options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=f"{serie_id}|{s['season_number']}") for s in saisons if s['season_number'] > 0]
        super().__init__(placeholder="Choisis la saison...", options=options)

    async def callback(self, interaction: discord.Interaction):
        s_id, s_num = self.values[0].split('|')
        data = get_details(f"tv/{s_id}/season/{s_num}")
        view = discord.ui.View().add_item(EpisodeSelect(s_id, s_num, data.get('episodes', [])))
        await interaction.response.send_message(f"📂 **Saison {s_num}** (ID TMDB: {s_id}) :", view=view, ephemeral=True)

# --- MOTEUR DE RECHERCHE ---
class SearchModal(discord.ui.Modal, title="🎬 Recherche Pathé"):
    recherche = discord.ui.TextInput(label="Quel film ou série ?", min_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        results = search_tmdb(self.recherche.value)
        
        options = []
        for r in results:
            if r.get('media_type') in ['movie', 'tv']:
                titre = r.get('title') or r.get('name')
                date = r.get('release_date') or r.get('first_air_date') or "????"
                options.append(discord.SelectOption(label=titre[:100], description=f"{r['media_type'].upper()} - {date[:4]}", value=f"{r['media_type']}|{r['id']}"))

        if not options:
            return await interaction.followup.send(f"❌ Aucun résultat.", ephemeral=True)

        select = discord.ui.Select(placeholder="Fais ton choix...", options=options[:25])

        async def sel_callback(inter):
            m_type, m_id = select.values[0].split('|')
            info = get_details(f"{m_type}/{m_id}")
            titre = info.get('title') or info.get('name')
            desc = info.get('overview', 'Pas de résumé.')[:500]
            img = f"https://image.tmdb.org/t/p/w500{info['poster_path']}" if info.get('poster_path') else None

            embed = discord.Embed(title=f"🎬 {titre}", description=desc, color=0x2b2d31)
            if img: embed.set_image(url=img)
            embed.set_footer(text=f"ID TMDB : {m_id}")

            view = discord.ui.View()
            # Ajout du bouton FAVORIS pour tout (Film et Série)
            view.add_item(FavButton(m_id, titre))

            if m_type == 'movie':
                db = load_db()
                lien = db["links"].get(str(m_id))
                if lien:
                    view.add_item(discord.ui.Button(label="▶️ Regarder", url=lien, style=discord.ButtonStyle.link))
                else:
                    view.add_item(discord.ui.Button(label="⌛ Bientôt", disabled=True))
                    btn_s = discord.ui.Button(label="Suggérer", style=discord.ButtonStyle.primary)
                    async def suggest_callback(i):
                        chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
                        await chan.send(f"📥 **Suggestion** : {titre} par {i.user.mention}", view=SuggestionView(i.user.id, titre))
                        await i.response.send_message("✅ Envoyé !", ephemeral=True)
                    btn_s.callback = suggest_callback
                    view.add_item(btn_s)
            else:
                view.add_item(SaisonSelect(m_id, info.get('seasons', [])))

            await inter.response.send_message(embed=embed, view=view, ephemeral=True)
       
        select.callback = sel_callback
        await interaction.followup.send("🔎 Résultats trouvés :", view=discord.ui.View().add_item(select), ephemeral=True)

# --- BOUTONS PRINCIPAUX ---
class CatalogueButtons(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    async def search(self, interaction, button): await interaction.response.send_modal(SearchModal())
    
    @discord.ui.button(label="Mes Favoris", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def my_favs(self, interaction, button):
        db = load_db()
        favs = db["favorites"].get(str(interaction.user.id), [])
        if not favs: return await interaction.response.send_message("💔 Ta liste est vide.", ephemeral=True)
        txt = "\n".join([f"• **{f['titre']}** (ID: `{f['id']}`)" for f in favs])
        await interaction.response.send_message(f"⭐ **Tes Favoris :**\n{txt}", ephemeral=True)

    @discord.ui.button(label="Anti-Pub", style=discord.ButtonStyle.danger, emoji="🚫")
    async def anti(self, interaction, button): await interaction.response.send_message("🛡️ Installez uBlock Origin !", ephemeral=True)

# --- COMMANDES ADMIN ---

@bot.tree.command(name="ajouter_lien", description="Admin : Lier un film/épisode")
async def add_link(interaction: discord.Interaction, tmdb_id: str, lien: str):
    if not interaction.user.guild_permissions.administrator: return
    db = load_db(); db["links"][tmdb_id] = lien; save_db(db)
    await interaction.response.send_message(f"✅ Lien sauvegardé pour **{tmdb_id}**", ephemeral=True)

@bot.tree.command(name="catalogue")
async def catalogue(interaction: discord.Interaction):
    if is_banned(interaction.user.id): return await interaction.response.send_message("❌ Vous êtes banni.", ephemeral=True)
    embed = discord.Embed(title="✨ PATHÉ STREAMING", description="Cherchez votre film ou série ci-dessous.", color=0x2b2d31)
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png")
    await interaction.response.send_message(embed=embed, view=CatalogueButtons())

# --- REST DU CODE (BAN/EXPORT) ---
@bot.tree.command(name="export_db")
async def export_db(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "rb") as f:
            await interaction.response.send_message("📁 Base de données :", file=discord.File(f, "db_links.json"), ephemeral=True)

@bot.tree.command(name="ban")
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Banni"):
    if not interaction.user.guild_permissions.administrator: return
    db = load_db()
    if str(membre.id) not in db["banned_users"]: db["banned_users"].append(str(membre.id))
    save_db(db)
    await membre.ban(reason=raison)
    await interaction.response.send_message(f"🚫 {membre} banni.")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Connecté : {bot.user}")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))