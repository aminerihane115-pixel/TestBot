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
    if not os.path.exists(DB_FILE): return {"links": {}, "banned_users": [], "favorites": {}}
    with open(DB_FILE, "r") as f:
        try: 
            data = json.load(f)
            if "links" not in data: data = {"links": data, "banned_users": [], "favorites": {}}
            return data
        except: return {"links": {}, "banned_users": [], "favorites": {}}

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=4)

def is_banned(user_id):
    db = load_db()
    return str(user_id) in db.get("banned_users", [])

# --- FONCTIONS TMDB ---
def search_tmdb(query):
    url = f"https://api.themoviedb.org/3/search/multi"
    params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'fr-FR'}
    try: return requests.get(url, params=params).json().get('results', [])
    except: return []

def get_details(endpoint):
    url = f"https://api.themoviedb.org/3/{endpoint}"
    params = {'api_key': TMDB_API_KEY, 'language': 'fr-FR'}
    return requests.get(url, params=params).json()

# --- INTERFACE DE NAVIGATION (SINGLE MESSAGE) ---

class MovieView(discord.ui.View):
    def __init__(self, m_id, titre, user_id):
        super().__init__(timeout=None)
        self.m_id = str(m_id)
        self.user_id = str(user_id)
        self.titre = titre
        db = load_db()
        
        # Bouton Regarder
        lien = db["links"].get(self.m_id)
        if lien:
            self.add_item(discord.ui.Button(label="▶️ Regarder", url=lien, style=discord.ButtonStyle.link))
        else:
            btn = discord.ui.Button(label="⌛ Suggérer", style=discord.ButtonStyle.primary)
            btn.callback = self.suggest_callback
            self.add_item(btn)

        # Bouton Favoris
        fav_label = "⭐ Retirer des favoris" if self.m_id in db["favorites"].get(self.user_id, []) else "❤️ Ajouter aux favoris"
        self.fav_btn = discord.ui.Button(label=fav_label, style=discord.ButtonStyle.secondary)
        self.fav_btn.callback = self.toggle_fav
        self.add_item(self.fav_btn)

    async def suggest_callback(self, i):
        chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
        await chan.send(f"📥 **Suggestion Film** : {self.titre} par {i.user.mention}", view=SuggestionView(i.user.id, self.titre))
        await i.response.send_message("✅ Suggestion envoyée !", ephemeral=True)

    async def toggle_fav(self, i):
        db = load_db()
        user_favs = db["favorites"].get(self.user_id, [])
        if self.m_id in user_favs:
            user_favs.remove(self.m_id)
            msg = "💔 Retiré des favoris."
        else:
            user_favs.append(self.m_id)
            msg = "❤️ Ajouté aux favoris !"
        db["favorites"][self.user_id] = user_favs
        save_db(db)
        await i.response.send_message(msg, ephemeral=True)

class SeriesView(discord.ui.View):
    def __init__(self, s_id, seasons, user_id, current_embed):
        super().__init__(timeout=None)
        self.s_id = str(s_id)
        self.user_id = str(user_id)
        self.current_embed = current_embed
        
        # Select pour les saisons
        options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=str(s['season_number'])) for s in seasons if s['season_number'] > 0]
        self.select = discord.ui.Select(placeholder="Choisissez une saison...", options=options[:25])
        self.select.callback = self.select_season
        self.add_item(self.select)

    async def select_season(self, i):
        s_num = self.select.values[0]
        data = get_details(f"tv/{self.s_id}/season/{s_num}")
        episodes = data.get('episodes', [])
        
        db = load_db()
        desc = ""
        view = discord.ui.View()
        
        # Liste des épisodes dans l'embed
        for e in episodes[:20]:
            cle = f"{self.s_id}_S{s_num}_E{e['episode_number']}"
            status = "✅" if cle in db["links"] else "❌"
            desc += f"{status} **Épisode {e['episode_number']}** : {e['name']}\n"
        
        # Menu déroulant pour choisir l'épisode à regarder
        ep_options = [discord.SelectOption(label=f"Épisode {e['episode_number']}", value=f"{s_num}|{e['episode_number']}") for e in episodes[:25]]
        ep_select = discord.ui.Select(placeholder="Regarder un épisode...", options=ep_options)
        
        async def ep_callback(inter):
            sn, en = ep_select.values[0].split('|')
            cle = f"{self.s_id}_S{sn}_E{en}"
            lien = db["links"].get(cle)
            if lien:
                v = discord.ui.View().add_item(discord.ui.Button(label=f"▶️ Épisode {en}", url=lien))
                await inter.response.send_message(f"Voici votre lien pour l'épisode {en} :", view=v, ephemeral=True)
            else:
                await inter.response.send_message("⌛ Épisode non disponible, suggestion envoyée !", ephemeral=True)

        ep_select.callback = ep_callback
        view.add_item(ep_select)
        
        # Bouton Retour
        back = discord.ui.Button(label="⬅️ Retour aux saisons", style=discord.ButtonStyle.danger)
        async def back_cb(it): await it.response.edit_message(embed=self.current_embed, view=self)
        back.callback = back_cb
        view.add_item(back)

        new_embed = self.current_embed.copy()
        new_embed.title = f"📺 Saison {s_num}"
        new_embed.description = desc
        await i.response.edit_message(embed=new_embed, view=view)

# --- SYSTÈME DE SUGGESTIONS (INCHANGÉ) ---
class SuggestionView(discord.ui.View):
    def __init__(self, user_id, titre):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.titre = titre

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await bot.fetch_user(self.user_id)
        try: await user.send(f"✅ Ta suggestion pour **{self.titre}** a été acceptée !")
        except: pass
        await interaction.response.edit_message(content=f"✅ **Accepté** : {self.titre}", view=None)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=f"❌ **Refusé** : {self.titre}", view=None)

# --- MOTEUR DE RECHERCHE ---
class SearchModal(discord.ui.Modal, title="🎬 Recherche Pathé"):
    recherche = discord.ui.TextInput(label="Nom du film ou de la série", min_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        results = search_tmdb(self.recherche.value)
        if not results: return await interaction.followup.send("❌ Aucun résultat.", ephemeral=True)

        options = []
        for r in results[:25]:
            titre = r.get('title') or r.get('name')
            options.append(discord.SelectOption(label=titre[:100], value=f"{r['media_type']}|{r['id']}"))

        select = discord.ui.Select(options=options)
        async def callback(i):
            m_type, m_id = select.values[0].split('|')
            info = get_details(f"{m_type}/{m_id}")
            titre = info.get('title') or info.get('name')
            embed = discord.Embed(title=titre, description=info.get('overview', '...')[:500], color=0x2b2d31)
            if info.get('poster_path'): embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
            
            if m_type == 'movie':
                await i.response.send_message(embed=embed, view=MovieView(m_id, titre, i.user.id), ephemeral=True)
            else:
                await i.response.send_message(embed=embed, view=SeriesView(m_id, info.get('seasons', []), i.user.id, embed), ephemeral=True)

        select.callback = callback
        await interaction.followup.send("Choisissez dans la liste :", view=discord.ui.View().add_item(select), ephemeral=True)

# --- COMMANDES ADMIN ---

@bot.tree.command(name="ajouter_lien", description="Ajouter un lien (Film ou Episode unique)")
async def add_link(interaction: discord.Interaction, tmdb_id: str, lien: str):
    if not interaction.user.guild_permissions.administrator: return
    db = load_db()
    db["links"][tmdb_id] = lien
    save_db(db)
    await interaction.response.send_message(f"✅ Lien ajouté pour `{tmdb_id}`", ephemeral=True)

@bot.tree.command(name="ajouter_serie", description="Ajouter une saison entière (Séparez les liens par des virgules)")
async def add_serie(interaction: discord.Interaction, tmdb_id: str, saison: int, liens: str):
    if not interaction.user.guild_permissions.administrator: return
    db = load_db()
    liste_liens = [l.strip() for l in liens.split(",")]
    for index, lien in enumerate(liste_liens):
        cle = f"{tmdb_id}_S{saison}_E{index+1}"
        db["links"][cle] = lien
    save_db(db)
    await interaction.response.send_message(f"✅ {len(liste_liens)} épisodes ajoutés pour la saison {saison} !", ephemeral=True)

@bot.tree.command(name="export_db")
async def export_db(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return
    with open(DB_FILE, "rb") as f:
        await interaction.response.send_message(file=discord.File(f, "db_links.json"), ephemeral=True)

@bot.tree.command(name="catalogue")
async def catalogue(interaction: discord.Interaction):
    embed = discord.Embed(title="✨ PATHÉ STREAMING", description="Bienvenue ! Utilisez le bouton ci-dessous pour chercher.", color=0x2b2d31)
    view = discord.ui.View()
    btn = discord.ui.button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    async def search_cb(i): await i.response.send_modal(SearchModal())
    btn = discord.ui.Button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    btn.callback = search_cb
    view.add_item(btn)
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot prêt : {bot.user}")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))