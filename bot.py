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

SUGGESTION_CHANNEL_ID = 1453864717897699382

# Liste d'emojis pour les boutons
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
    """Vue des boutons emojis sous la recherche"""
    def __init__(self, results):
        super().__init__(timeout=180)
        for i, res in enumerate(results[:len(EMOJI_LIST)]):
            self.add_item(EmojiButton(res, EMOJI_LIST[i]))

class EmojiButton(discord.ui.Button):
    def __init__(self, res, emoji):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary)
        self.res = res

    async def callback(self, interaction: discord.Interaction):
        m_type, m_id = self.res['media_type'], self.res['id']
        info = get_details(f"{m_type}/{m_id}")
        titre = info.get('title') or info.get('name')
        
        embed = discord.Embed(title=titre, description=info.get('overview', '...')[:500], color=0x2b2d31)
        if info.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
        
        view = discord.ui.View()
        view.add_item(FavButton(m_id, titre))

        if m_type == "movie":
            db = load_db()
            lien = db["links"].get(str(m_id))
            if lien:
                view.add_item(discord.ui.Button(label="Regarder", url=lien, style=discord.ButtonStyle.link))
            else:
                btn_sug = discord.ui.Button(label="Suggérer", emoji="⏳", style=discord.ButtonStyle.primary)
                async def sug_cb(i):
                    chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
                    await chan.send(f"📥 **Suggestion** : {titre} (ID: {m_id})", view=SuggestionView(i.user.id, titre))
                    await i.response.send_message("✅ Suggestion envoyée !", ephemeral=True)
                btn_sug.callback = sug_cb
                view.add_item(btn_sug)
        else:
            # Pour les séries : On crée le menu déroulant des saisons
            options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=f"{m_id}|{s['season_number']}") 
                       for s in info.get('seasons', []) if s['season_number'] > 0]
            if options:
                select = discord.ui.Select(placeholder="Choisissez une saison...", options=options[:25])
                # Ici on utilise edit_message pour transformer le message actuel
                select.callback = lambda i: self.show_episodes(i, select.values[0], info)
                view.add_item(select)

        # On modifie le message de recherche au lieu d'en envoyer un nouveau
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    async def show_episodes(self, interaction, value, info_serie):
        sid, snum = value.split('|')
        data = get_details(f"tv/{sid}/season/{snum}")
        db = load_db()
        
        # Titre et Poster de la saison
        text = f"🟦 **Saison {snum}**\n\n"
        ep_options = []
        
        for e in data.get('episodes', []):
            cle = f"{sid}_S{snum}_E{e['episode_number']}"
            statut = "✅" if cle in db["links"] else "❌"
            text += f"{statut} **Épisode {e['episode_number']}** : {e['name']}\n"
            if cle in db["links"]:
                ep_options.append(discord.SelectOption(label=f"Épisode {e['episode_number']}", value=db["links"][cle]))

        view = discord.ui.View()
        if ep_options:
            ep_sel = discord.ui.Select(placeholder="Regarder un épisode...", options=ep_options[:25])
            async def ep_cb(i):
                v = discord.ui.View().add_item(discord.ui.Button(label="▶️ Lecteur", url=ep_sel.values[0]))
                await i.response.send_message(f"📺 Bon visionnage !", view=v, ephemeral=True)
            ep_sel.callback = ep_cb
            view.add_item(ep_sel)
        
        # Bouton Retour (pour revenir au choix des saisons)
        btn_back = discord.ui.Button(label="Retour aux saisons", style=discord.ButtonStyle.danger, emoji="⬅️")
        async def back_cb(i):
            # On recrée la vue de la série (re-déclenche le callback de EmojiButton logic)
            await self.callback(i)
        btn_back.callback = back_cb
        view.add_item(btn_back)

        # Création de l'embed pour l'image de la saison
        embed = discord.Embed(color=0x2b2d31)
        if data.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{data['poster_path']}")
        elif info_serie.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info_serie['poster_path']}")

        # Transformation du message en liste d'épisodes
        await interaction.response.edit_message(content=text, embed=embed, view=view)

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
            return await interaction.response.send_message(f"💔 **{self.titre}** retiré.", ephemeral=True)
        
        db["favorites"][uid].append({"id": self.m_id, "titre": self.titre})
        save_db(db)
        await interaction.response.send_message(f"❤️ **{self.titre}** ajouté !", ephemeral=True)

class SuggestionView(discord.ui.View):
    def __init__(self, user_id, titre):
        super().__init__(timeout=None)
        self.user_id, self.titre = user_id, titre

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction, button):
        user = await bot.fetch_user(self.user_id)
        try: await user.send(f"✅ Ta suggestion pour **{self.titre}** a été acceptée !")
        except: pass
        await interaction.response.edit_message(content=f"✅ Accepté : {self.titre}", view=None)

# --- COMMANDES ---

@bot.tree.command(name="catalogue", description="Ouvrir le catalogue Pathé")
async def catalogue(interaction: discord.Interaction):
    db = load_db()
    if str(interaction.user.id) in db["banned_users"]:
        return await interaction.response.send_message("❌ Vous êtes banni.", ephemeral=True)

    embed = discord.Embed(title="✨ PATHÉ STREAMING", description="Cherchez votre film ou série ci-dessous.", color=0x2b2d31)
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png")
    
    view = discord.ui.View()
    btn_search = discord.ui.Button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    btn_search.callback = lambda i: i.response.send_modal(SearchModal())
    view.add_item(btn_search)

    btn_fav = discord.ui.Button(label="Mes Favoris", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def show_favs(i):
        db = load_db()
        favs = db["favorites"].get(str(i.user.id), [])
        if not favs: return await i.response.send_message("💔 Liste vide.", ephemeral=True)
        txt = "\n".join([f"• **{f['titre']}** (ID: `{f['id']}`)" for f in favs])
        await i.response.send_message(f"⭐ **Tes Favoris :**\n{txt}", ephemeral=True)
    btn_fav.callback = show_favs
    view.add_item(btn_fav)

    await interaction.response.send_message(embed=embed, view=view)

class SearchModal(discord.ui.Modal, title="🎬 Recherche Pathé"):
    recherche = discord.ui.TextInput(label="Nom du film ou de la série", min_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        results = search_tmdb(self.recherche.value)
        valid = [r for r in results if r.get('media_type') in ['movie', 'tv']][:len(EMOJI_LIST)]
        
        if not valid:
            return await interaction.response.send_message("❌ Aucun résultat.", ephemeral=True)

        text = f"🔎 **Résultats pour \"{self.recherche.value}\"**\n\n"
        text += "Cliquez sur l'emoji correspondant pour voir les détails.\n\n"
        for i, r in enumerate(valid):
            titre = r.get('title') or r.get('name')
            text += f"{EMOJI_LIST[i]} {titre}\n"
        
        # Message ephémère qui va être transformé par la suite
        await interaction.response.send_message(text, view=ResultView(valid), ephemeral=True)

# --- ADMIN COMMANDS ---

@bot.tree.command(name="ajouter_saison", description="Ajouter une saison entière")
async def add_season(interaction: discord.Interaction, tmdb_id: str, saison: int, liens: str):
    if not interaction.user.guild_permissions.administrator: return
    liste_liens = liens.replace(',', ' ').split()
    db = load_db()
    for i, lien in enumerate(liste_liens, 1):
        db["links"][f"{tmdb_id}_S{saison}_E{i}"] = lien
    save_db(db)
    await interaction.response.send_message(f"✅ {len(liste_liens)} épisodes ajoutés !", ephemeral=True)

@bot.tree.command(name="ajouter_lien", description="Ajouter un lien unique")
async def add_link(interaction: discord.Interaction, tmdb_id: str, lien: str):
    if not interaction.user.guild_permissions.administrator: return
    db = load_db()
    db["links"][tmdb_id] = lien
    save_db(db)
    await interaction.response.send_message(f"✅ Lien sauvegardé pour `{tmdb_id}`", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot prêt : {bot.user}")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))