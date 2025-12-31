import discord
import os
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

# IDs des salons (à vérifier)
SUGGESTION_CHANNEL_ID = 1453864717897699382 

EMOJI_LIST = ["🧡", "💛", "💚", "💙", "🤍", "🟠", "🟣", "⚫", "❤️"]

# --- GESTION DB ---
def load_db():
    if not os.path.exists(DB_FILE): 
        return {"links": {}, "favorites": {}, "banned_users": []}
    with open(DB_FILE, "r", encoding='utf-8') as f:
        try: 
            data = json.load(f)
            if "links" not in data: data = {"links": data, "favorites": {}, "banned_users": []}
            return data
        except: return {"links": {}, "favorites": {}, "banned_users": []}

def save_db(db):
    with open(DB_FILE, "w", encoding='utf-8') as f: 
        json.dump(db, f, indent=4, ensure_ascii=False)

# --- FONCTIONS TMDB ---
def search_tmdb(query):
    url = f"https://api.themoviedb.org/3/search/multi"
    params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'fr-FR'}
    return requests.get(url, params=params).json().get('results', [])

def get_details(endpoint):
    url = f"https://api.themoviedb.org/3/{endpoint}"
    params = {'api_key': TMDB_API_KEY, 'language': 'fr-FR'}
    return requests.get(url, params=params).json()

# --- VUES ---

class ResultView(discord.ui.View):
    """Vue initiale des résultats avec les cœurs"""
    def __init__(self, results):
        super().__init__(timeout=180)
        self.results = results
        for i, res in enumerate(results[:len(EMOJI_LIST)]):
            self.add_item(EmojiButton(res, EMOJI_LIST[i], results))

class EmojiButton(discord.ui.Button):
    def __init__(self, res, emoji, all_results):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary)
        self.res = res
        self.all_results = all_results

    async def callback(self, interaction: discord.Interaction):
        m_type, m_id = self.res['media_type'], self.res['id']
        info = get_details(f"{m_type}/{m_id}")
        titre = info.get('title') or info.get('name')
        
        # TRANSFORMATION DU MESSAGE : On passe à la fiche du média ou choix saison
        embed = discord.Embed(title=titre, color=0x2b2d31)
        embed.add_field(name="Synopsis", value=info.get('overview', '...')[:500], inline=False)
        if info.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
        
        view = discord.ui.View()
        # Bouton Retour Recherche
        btn_back = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary)
        async def back_cb(i):
            text = f"🔎 **Résultats pour votre recherche**\n\n"
            for idx, r in enumerate(self.all_results):
                text += f"{EMOJI_LIST[idx]} {r.get('title') or r.get('name')}\n"
            await i.response.edit_message(content=text, embed=None, view=ResultView(self.all_results))
        btn_back.callback = back_cb
        view.add_item(btn_back)
        
        view.add_item(FavButton(m_id, titre))

        if m_type == "movie":
            db = load_db()
            lien = db["links"].get(str(m_id))
            if lien:
                view.add_item(discord.ui.Button(label="Regarder", url=lien, style=discord.ButtonStyle.link))
            else:
                view.add_item(discord.ui.Button(label="Bientôt disponible", style=discord.ButtonStyle.secondary, disabled=True))
        else:
            # SERIES : Menu de sélection des saisons (Exactement comme sur l'image)
            options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=f"{m_id}|{s['season_number']}") 
                       for s in info.get('seasons', []) if s['season_number'] > 0]
            if options:
                select = discord.ui.Select(placeholder="Choisissez une saison...", options=options[:25])
                select.callback = lambda i: self.show_episodes(i, select.values[0], info)
                view.add_item(select)

        await interaction.response.edit_message(content=None, embed=embed, view=view)

    async def show_episodes(self, interaction, value, info_serie):
        """TRANSFORMATION DU MESSAGE : Affichage des épisodes cliquables"""
        sid, snum = value.split('|')
        data = get_details(f"tv/{sid}/season/{snum}")
        db = load_db()
        
        titre_complet = f"{info_serie.get('name')} - Saison {snum}"
        
        # Construction de la liste des épisodes en liens bleus (Markdown)
        episodes_text = ""
        for e in data.get('episodes', []):
            cle = f"{sid}_S{snum}_E{e['episode_number']}"
            lien = db["links"].get(cle)
            if lien:
                episodes_text += f"🔹 **[Épisode {e['episode_number']} : {e['name']}]({lien})**\n"
            else:
                episodes_text += f"❌ Épisode {e['episode_number']} : {e['name']} (Indisponible)\n"

        embed = discord.Embed(title=titre_complet, color=0x2b2d31)
        embed.description = f"**Date de sortie:** {data.get('air_date', 'Inconnue')}\n\n**Épisodes:**\n{episodes_text}"
        
        if data.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{data['poster_path']}")

        view = discord.ui.View()
        # Bouton Retour à la fiche série
        btn_back_serie = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary)
        btn_back_serie.callback = lambda i: self.callback(i)
        view.add_item(btn_back_serie)
        
        # Bouton Signaler
        btn_report = discord.ui.Button(label="Signaler un lien", emoji="🚩", style=discord.ButtonStyle.danger)
        async def report_cb(i):
            chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
            await chan.send(f"🚩 **Signalement** : {titre_complet} (ID: {sid})")
            await i.response.send_message("Merci, le staff va vérifier !", ephemeral=True)
        btn_report.callback = report_cb
        view.add_item(btn_report)
        
        view.add_item(FavButton(sid, info_serie.get('name')))

        await interaction.response.edit_message(content=None, embed=embed, view=view)

class FavButton(discord.ui.Button):
    def __init__(self, m_id, titre):
        super().__init__(label="Favoris", style=discord.ButtonStyle.secondary, emoji="❤️")
        self.m_id, self.titre = str(m_id), titre

    async def callback(self, interaction: discord.Interaction):
        db = load_db()
        uid = str(interaction.user.id)
        if uid not in db["favorites"]: db["favorites"][uid] = []
        if any(f['id'] == self.m_id for f in db["favorites"][uid]):
            db["favorites"][uid] = [f for f in db["favorites"][uid] if f['id'] != self.m_id]
            save_db(db)
            return await interaction.response.send_message(f"💔 Retiré des favoris.", ephemeral=True)
        db["favorites"][uid].append({"id": self.m_id, "titre": self.titre})
        save_db(db)
        await interaction.response.send_message(f"❤️ Ajouté aux favoris !", ephemeral=True)

# --- COMMANDES ---

@bot.tree.command(name="catalogue", description="Ouvrir le catalogue")
async def catalogue(interaction: discord.Interaction):
    embed = discord.Embed(title="✨ PATHÉ STREAMING", description="Utilisez le bouton ci-dessous pour chercher.", color=0x2b2d31)
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png")
    view = discord.ui.View()
    btn_search = discord.ui.Button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    btn_search.callback = lambda i: i.response.send_modal(SearchModal())
    view.add_item(btn_search)
    
    btn_fav = discord.ui.Button(label="Mes Favoris", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def show_favs(i):
        db = load_db()
        favs = db["favorites"].get(str(i.user.id), [])
        if not favs: return await i.response.send_message("Liste vide.", ephemeral=True)
        txt = "\n".join([f"• {f['titre']}" for f in favs])
        await i.response.send_message(f"⭐ **Tes Favoris :**\n{txt}", ephemeral=True)
    btn_fav.callback = show_favs
    view.add_item(btn_fav)
    
    await interaction.response.send_message(embed=embed, view=view)

class SearchModal(discord.ui.Modal, title="🎬 Recherche"):
    recherche = discord.ui.TextInput(label="Nom du film ou de la série", min_length=2)
    async def on_submit(self, interaction: discord.Interaction):
        results = search_tmdb(self.recherche.value)
        valid = [r for r in results if r.get('media_type') in ['movie', 'tv']][:len(EMOJI_LIST)]
        if not valid: return await interaction.response.send_message("❌ Aucun résultat.", ephemeral=True)
        
        text = f"🔎 **Résultats pour \"{self.recherche.value}\"**\n\n"
        for i, r in enumerate(valid):
            text += f"{EMOJI_LIST[i]} {r.get('title') or r.get('name')}\n"
        
        await interaction.response.send_message(text, view=ResultView(valid), ephemeral=True)

@bot.tree.command(name="ajouter_saison")
async def add_season(interaction: discord.Interaction, tmdb_id: str, saison: int, liens: str):
    if not interaction.user.guild_permissions.administrator: return
    liste_liens = liens.replace(',', ' ').split()
    db = load_db()
    for i, lien in enumerate(liste_liens, 1):
        db["links"][f"{tmdb_id}_S{saison}_E{i}"] = lien
    save_db(db)
    await interaction.response.send_message(f"✅ Ajouté !", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot connecté : {bot.user}")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))