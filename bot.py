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

# IDs des salons
SUGGESTION_CHANNEL_ID = 1453864717897699382
NOTIFICATION_CHANNEL_ID = 1453864717897699380  # Salon pour les notifications d'ajout

EMOJI_LIST = ["🧡", "💛", "💚", "💙", "🤍", "🟠", "🟣", "⚫", "❤️"]

# --- GESTION DB ---
def load_db():
    if not os.path.exists(DB_FILE): 
        return {"links": {}, "trailers": {}, "favorites": {}, "banned_users": []}
    with open(DB_FILE, "r", encoding='utf-8') as f:
        try: 
            data = json.load(f)
            if "links" not in data: data = {"links": data, "trailers": {}, "favorites": {}, "banned_users": []}
            if "trailers" not in data: data["trailers"] = {}
            return data
        except: return {"links": {}, "trailers": {}, "favorites": {}, "banned_users": []}

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

# --- FONCTION NOTIFICATION ---
async def send_notification(media_type, media_id, user):
    """Envoie une notification dans le salon quand un contenu est ajouté"""
    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if not channel:
        return
    
    # Récupérer les infos du média
    info = get_details(f"{media_type}/{media_id}")
    titre = info.get('title') or info.get('name')
    
    embed = discord.Embed(
        title=f"{'🎬' if media_type == 'movie' else '📺'} Nouveau contenu ajouté !",
        description=f"**{titre}**",
        color=0x00ff00
    )
    
    # Synopsis court
    synopsis = info.get('overview', 'Aucun synopsis disponible')[:200]
    embed.add_field(name="Synopsis", value=synopsis + "...", inline=False)
    
    # Affiche
    if info.get('poster_path'):
        embed.set_thumbnail(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
    
    embed.add_field(name="Type", value="Film 🎬" if media_type == "movie" else "Série 📺", inline=True)
    embed.add_field(name="ID TMDB", value=media_id, inline=True)
    embed.set_footer(text=f"Ajouté par {user.name}")
    
    # Bouton "Regarder"
    view = discord.ui.View()
    btn_watch = discord.ui.Button(label="Regarder", style=discord.ButtonStyle.primary, emoji="👁️")
    
    async def watch_callback(i):
        await show_media_from_notification(i, media_type, media_id)
    
    btn_watch.callback = watch_callback
    view.add_item(btn_watch)
    
    await channel.send(embed=embed, view=view)

async def show_media_from_notification(interaction, media_type, media_id):
    """Affiche la fiche complète du film/série depuis la notification"""
    info = get_details(f"{media_type}/{media_id}")
    titre = info.get('title') or info.get('name')
    
    if media_type == "movie":
        # FILM
        embed = discord.Embed(title=titre, color=0x2b2d31)
        
        genres = ", ".join([g['name'] for g in info.get('genres', [])])
        embed.add_field(name="Genres:", value=genres or "Non spécifié", inline=False)
        
        date_sortie = info.get('release_date', 'Inconnue')[:4]
        embed.add_field(name="Date de sortie:", value=date_sortie, inline=False)
        
        embed.add_field(name="Synopsis:", value=info.get('overview', 'Non spécifié')[:500], inline=False)
        
        if info.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
        
        embed.set_footer(text=f"ID TMDB: {media_id}")
        
        view = discord.ui.View()
        
        db = load_db()
        lien = db["links"].get(str(media_id))
        trailer = db["trailers"].get(str(media_id))
        
        if lien:
            view.add_item(discord.ui.Button(label="Lecture", emoji="🔗", url=lien, style=discord.ButtonStyle.link, row=0))
        
        if trailer:
            view.add_item(discord.ui.Button(label="Bande d'annonce", emoji="🔗", url=trailer, style=discord.ButtonStyle.link, row=0))
        
        btn_report = discord.ui.Button(label="Signaler un lien", emoji="🚩", style=discord.ButtonStyle.danger, row=1)
        
        async def report_cb(i):
            chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
            if chan:
                await chan.send(f"🚩 **Signalement** : {titre} (ID: {media_id})")
            await i.response.send_message("✅ Merci, le staff va vérifier !", ephemeral=True)
        
        btn_report.callback = report_cb
        view.add_item(btn_report)
        
        view.add_item(FavButton(media_id, titre, row=1))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    else:
        # SÉRIE
        embed = discord.Embed(title=f"{titre} - Saison 1", color=0x2b2d31)
        
        genres = ", ".join([g['name'] for g in info.get('genres', [])])
        embed.add_field(name="Genres:", value=genres or "Non spécifié", inline=False)
        embed.add_field(name="Date de sortie:", value=info.get('first_air_date', 'Inconnue')[:4], inline=False)
        
        embed.add_field(name="Synopsis:", value=info.get('overview', 'Non spécifié')[:300], inline=False)
        
        season_data = get_details(f"tv/{media_id}/season/1")
        
        db = load_db()
        episodes_text = "**Épisodes:**\n"
        for e in season_data.get('episodes', []):
            cle = f"{media_id}_S1_E{e['episode_number']}"
            lien = db["links"].get(cle)
            if lien:
                episodes_text += f"[Episode {e['episode_number']}]({lien})\n"
            else:
                episodes_text += f"Episode {e['episode_number']}\n"
        
        embed.add_field(name="", value=episodes_text, inline=False)
        
        if season_data.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}")
        
        embed.set_footer(text=f"ID TMDB: {media_id}")
        
        view = discord.ui.View()
        
        btn_report = discord.ui.Button(label="Signaler un lien", emoji="🚩", style=discord.ButtonStyle.danger, row=0)
        
        async def report_cb(i):
            chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
            if chan:
                await chan.send(f"🚩 **Signalement** : {titre} - Saison 1 (ID: {media_id})")
            await i.response.send_message("✅ Merci, le staff va vérifier !", ephemeral=True)
        
        btn_report.callback = report_cb
        view.add_item(btn_report)
        
        view.add_item(FavButton(media_id, titre, row=0))
        
        seasons = info.get('seasons', [])
        if seasons:
            options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=str(s['season_number'])) 
                       for s in seasons if s['season_number'] > 0][:25]
            
            if options:
                select = discord.ui.Select(placeholder="Saison 1", options=options, row=1)
                
                async def change_season_cb(i):
                    await change_season_from_fav(i, media_id, info, select.values[0])
                
                select.callback = change_season_cb
                view.add_item(select)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def change_season_from_fav(interaction, sid, info_serie, season_num):
    """Changement de saison depuis favoris ou notification"""
    titre = info_serie.get('name')
    season_data = get_details(f"tv/{sid}/season/{season_num}")
    
    embed = discord.Embed(title=f"{titre} - Saison {season_num}", color=0x2b2d31)
    
    genres = ", ".join([g['name'] for g in info_serie.get('genres', [])])
    embed.add_field(name="Genres:", value=genres or "Non spécifié", inline=False)
    embed.add_field(name="Date de sortie:", value=season_data.get('air_date', 'Inconnue')[:4], inline=False)
    
    embed.add_field(name="Synopsis:", value=season_data.get('overview') or info_serie.get('overview', 'Non spécifié')[:300], inline=False)
    
    db = load_db()
    episodes_text = "**Épisodes:**\n"
    for e in season_data.get('episodes', []):
        cle = f"{sid}_S{season_num}_E{e['episode_number']}"
        lien = db["links"].get(cle)
        if lien:
            episodes_text += f"[Episode {e['episode_number']}]({lien})\n"
        else:
            episodes_text += f"Episode {e['episode_number']}\n"
    
    embed.add_field(name="", value=episodes_text, inline=False)
    
    if season_data.get('poster_path'):
        embed.set_image(url=f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}")
    
    embed.set_footer(text=f"ID TMDB: {sid}")
    
    view = discord.ui.View()
    
    btn_report = discord.ui.Button(label="Signaler un lien", emoji="🚩", style=discord.ButtonStyle.danger, row=0)
    
    async def report_cb(i):
        chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
        if chan:
            await chan.send(f"🚩 **Signalement** : {titre} - Saison {season_num} (ID: {sid})")
        await i.response.send_message("✅ Merci, le staff va vérifier !", ephemeral=True)
    
    btn_report.callback = report_cb
    view.add_item(btn_report)
    
    view.add_item(FavButton(sid, titre, row=0))
    
    seasons = info_serie.get('seasons', [])
    options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=str(s['season_number']), default=(str(s['season_number'])==season_num)) 
               for s in seasons if s['season_number'] > 0][:25]
    
    if options:
        select = discord.ui.Select(placeholder=f"Saison {season_num}", options=options, row=1)
        
        async def change_cb(i):
            await change_season_from_fav(i, sid, info_serie, select.values[0])
        
        select.callback = change_cb
        view.add_item(select)
    
    await interaction.response.edit_message(embed=embed, view=view)

# --- VUES ---

class FavoritesView(discord.ui.View):
    """Vue pour afficher les favoris avec des cœurs cliquables"""
    def __init__(self, favorites):
        super().__init__(timeout=180)
        self.favorites = favorites
        
        for i, fav in enumerate(favorites[:len(EMOJI_LIST)]):
            self.add_item(FavEmojiButton(fav, EMOJI_LIST[i], row=i//3))

class FavEmojiButton(discord.ui.Button):
    """Bouton cœur pour les favoris"""
    def __init__(self, fav, emoji, row):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, row=row)
        self.fav = fav
    
    async def callback(self, interaction: discord.Interaction):
        # Déterminer si c'est un film ou une série
        results = search_tmdb(self.fav['titre'])
        media_type = "movie"
        media_id = self.fav['id']
        
        for r in results:
            if str(r['id']) == str(media_id):
                media_type = r['media_type']
                break
        
        await show_media_from_notification(interaction, media_type, media_id)

class ResultView(discord.ui.View):
    """Vue des résultats de recherche avec embed noir et cœurs colorés"""
    def __init__(self, results, query):
        super().__init__(timeout=180)
        self.results = results
        self.query = query
        self.current_page = 0
        
        for i, res in enumerate(results[:len(EMOJI_LIST)]):
            self.add_item(EmojiButton(res, EMOJI_LIST[i], results, query, row=i//3))
        
        self.add_item(NavButton("⏮️", "first", row=3))
        self.add_item(NavButton("◀️", "prev", row=3))
        self.add_item(NavButton("🏠", "home", row=3))
        self.add_item(NavButton("▶️", "next", row=3))
        self.add_item(NavButton("⏭️", "last", row=3))

class NavButton(discord.ui.Button):
    def __init__(self, emoji, action, row):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.primary, row=row)
        self.action = action
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class EmojiButton(discord.ui.Button):
    def __init__(self, res, emoji, all_results, query, row):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, row=row)
        self.res = res
        self.all_results = all_results
        self.query = query

    async def callback(self, interaction: discord.Interaction):
        m_type, m_id = self.res['media_type'], self.res['id']
        info = get_details(f"{m_type}/{m_id}")
        titre = info.get('title') or info.get('name')
        
        if m_type == "movie":
            embed = discord.Embed(title=titre, color=0x2b2d31)
            
            genres = ", ".join([g['name'] for g in info.get('genres', [])])
            embed.add_field(name="Genres:", value=genres or "Non spécifié", inline=False)
            
            date_sortie = info.get('release_date', 'Inconnue')[:4]
            embed.add_field(name="Date de sortie:", value=date_sortie, inline=False)
            
            embed.add_field(name="Synopsis:", value=info.get('overview', 'Non spécifié')[:500], inline=False)
            
            if info.get('poster_path'):
                embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
            
            embed.set_footer(text=f"ID TMDB: {m_id}")
            
            view = discord.ui.View()
            
            btn_back = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.primary, row=0)
            
            async def back_cb(i):
                await self.show_search_results(i)
            
            btn_back.callback = back_cb
            view.add_item(btn_back)
            
            db = load_db()
            lien = db["links"].get(str(m_id))
            trailer = db["trailers"].get(str(m_id))
            
            if lien:
                view.add_item(discord.ui.Button(label="Lecture", emoji="🔗", url=lien, style=discord.ButtonStyle.link, row=1))
            
            if trailer:
                view.add_item(discord.ui.Button(label="Bande d'annonce", emoji="🔗", url=trailer, style=discord.ButtonStyle.link, row=1))
            
            btn_report = discord.ui.Button(label="Signaler un lien", emoji="🚩", style=discord.ButtonStyle.danger, row=2)
            
            async def report_cb(i):
                chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
                if chan:
                    await chan.send(f"🚩 **Signalement** : {titre} (ID: {m_id})")
                await i.response.send_message("✅ Merci, le staff va vérifier !", ephemeral=True)
            
            btn_report.callback = report_cb
            view.add_item(btn_report)
            
            view.add_item(FavButton(m_id, titre, row=2))
            
            await interaction.response.edit_message(content=None, embed=embed, view=view)
            
        else:
            await self.show_serie_main(interaction, info, m_id)

    async def show_search_results(self, interaction):
        embed = discord.Embed(
            title=f"🔎 Résultat de la Recherche \"{self.query}\"",
            description="**Pour accéder à votre Recherche, cliquez sur l'emoji correspondant.**",
            color=0x2b2d31
        )
        
        result_text = ""
        for idx, r in enumerate(self.all_results[:len(EMOJI_LIST)]):
            result_text += f"{EMOJI_LIST[idx]} {r.get('title') or r.get('name')}\n"
        
        embed.add_field(name="", value=result_text, inline=False)
        embed.set_footer(text=f"Page 1/1 - Total de {len(self.all_results)} résultat(s)")
        
        await interaction.response.edit_message(content=None, embed=embed, view=ResultView(self.all_results, self.query))

    async def show_serie_main(self, interaction, info, sid):
        titre = info.get('name')
        
        embed = discord.Embed(title=f"{titre} - Saison 1", color=0x2b2d31)
        
        genres = ", ".join([g['name'] for g in info.get('genres', [])])
        embed.add_field(name="Genres:", value=genres or "Non spécifié", inline=False)
        embed.add_field(name="Date de sortie:", value=info.get('first_air_date', 'Inconnue')[:4], inline=False)
        
        embed.add_field(name="Synopsis:", value=info.get('overview', 'Non spécifié')[:300], inline=False)
        
        season_data = get_details(f"tv/{sid}/season/1")
        
        db = load_db()
        episodes_text = "**Épisodes:**\n"
        for e in season_data.get('episodes', []):
            cle = f"{sid}_S1_E{e['episode_number']}"
            lien = db["links"].get(cle)
            if lien:
                episodes_text += f"[Episode {e['episode_number']}]({lien})\n"
            else:
                episodes_text += f"Episode {e['episode_number']}\n"
        
        embed.add_field(name="", value=episodes_text, inline=False)
        
        if season_data.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}")
        
        embed.set_footer(text=f"ID TMDB: {sid}")
        
        view = discord.ui.View()
        
        btn_back = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.primary, row=0)
        
        async def back_cb(i):
            await self.show_search_results(i)
        
        btn_back.callback = back_cb
        view.add_item(btn_back)
        
        btn_report = discord.ui.Button(label="Signaler un lien", emoji="🚩", style=discord.ButtonStyle.danger, row=0)
        
        async def report_cb(i):
            chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
            if chan:
                await chan.send(f"🚩 **Signalement** : {titre} - Saison 1 (ID: {sid})")
            await i.response.send_message("✅ Merci, le staff va vérifier !", ephemeral=True)
        
        btn_report.callback = report_cb
        view.add_item(btn_report)
        
        view.add_item(FavButton(sid, titre, row=0))
        
        seasons = info.get('seasons', [])
        if seasons:
            options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=str(s['season_number'])) 
                       for s in seasons if s['season_number'] > 0][:25]
            
            if options:
                select = discord.ui.Select(placeholder="Saison 1", options=options, row=1)
                select.callback = lambda i: self.change_season(i, sid, info, select.values[0])
                view.add_item(select)
        
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    async def change_season(self, interaction, sid, info_serie, season_num):
        titre = info_serie.get('name')
        season_data = get_details(f"tv/{sid}/season/{season_num}")
        
        embed = discord.Embed(title=f"{titre} - Saison {season_num}", color=0x2b2d31)
        
        genres = ", ".join([g['name'] for g in info_serie.get('genres', [])])
        embed.add_field(name="Genres:", value=genres or "Non spécifié", inline=False)
        embed.add_field(name="Date de sortie:", value=season_data.get('air_date', 'Inconnue')[:4], inline=False)
        
        embed.add_field(name="Synopsis:", value=season_data.get('overview') or info_serie.get('overview', 'Non spécifié')[:300], inline=False)
        
        db = load_db()
        episodes_text = "**Épisodes:**\n"
        for e in season_data.get('episodes', []):
            cle = f"{sid}_S{season_num}_E{e['episode_number']}"
            lien = db["links"].get(cle)
            if lien:
                episodes_text += f"[Episode {e['episode_number']}]({lien})\n"
            else:
                episodes_text += f"Episode {e['episode_number']}\n"
        
        embed.add_field(name="", value=episodes_text, inline=False)
        
        if season_data.get('poster_path'):
            embed.set_image(url=f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}")
        
        embed.set_footer(text=f"ID TMDB: {sid}")
        
        view = discord.ui.View()
        
        btn_back = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.primary, row=0)
        
        async def back_cb(i):
            await self.show_search_results(i)
        
        btn_back.callback = back_cb
        view.add_item(btn_back)
        
        btn_report = discord.ui.Button(label="Signaler un lien", emoji="🚩", style=discord.ButtonStyle.danger, row=0)
        
        async def report_cb(i):
            chan = bot.get_channel(SUGGESTION_CHANNEL_ID)
            if chan:
                await chan.send(f"🚩 **Signalement** : {titre} - Saison {season_num} (ID: {sid})")
            await i.response.send_message("✅ Merci, le staff va vérifier !", ephemeral=True)
        
        btn_report.callback = report_cb
        view.add_item(btn_report)
        
        view.add_item(FavButton(sid, titre, row=0))
        
        seasons = info_serie.get('seasons', [])
        options = [discord.SelectOption(label=f"Saison {s['season_number']}", value=str(s['season_number']), default=(str(s['season_number'])==season_num)) 
                   for s in seasons if s['season_number'] > 0][:25]
        
        if options:
            select = discord.ui.Select(placeholder=f"Saison {season_num}", options=options, row=1)
            select.callback = lambda i: self.change_season(i, sid, info_serie, select.values[0])
            view.add_item(select)
        
        await interaction.response.edit_message(embed=embed, view=view)

class FavButton(discord.ui.Button):
    def __init__(self, m_id, titre, row=0):
        super().__init__(label="Favoris", style=discord.ButtonStyle.secondary, emoji="🤍", row=row)
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
        if not favs: 
            return await i.response.send_message("❌ Ta liste de favoris est vide.", ephemeral=True)
        
        embed_fav = discord.Embed(
            title="❤️ Mes Favoris",
            color=0x2b2d31
        )
        
        fav_text = ""
        for idx, f in enumerate(favs[:len(EMOJI_LIST)]):
            fav_text += f"{EMOJI_LIST[idx]} {f['titre']}\n"
        
        embed_fav.add_field(name="", value=fav_text, inline=False)
        embed_fav.set_footer(text=f"Page 1/1 - Total de {len(favs)} résultat(s)")
        
        await i.response.send_message(embed=embed_fav, view=FavoritesView(favs), ephemeral=True)
    
    btn_fav.callback = show_favs
    view.add_item(btn_fav)
    
    await interaction.response.send_message(embed=embed, view=view)

class SearchModal(discord.ui.Modal, title="🎬 Recherche"):
    recherche = discord.ui.TextInput(label="Nom du film ou de la série", min_length=2)
    
    async def on_submit(self, interaction: discord.Interaction):
        results = search_tmdb(self.recherche.value)
        valid = [r for r in results if r.get('media_type') in ['movie', 'tv']][:len(EMOJI_LIST)]
        
        if not valid: 
            return await interaction.response.send_message("❌ Aucun résultat trouvé.", ephemeral=True)
        
        embed = discord.Embed(
            title=f"🔎 Résultat de la Recherche \"{self.recherche.value}\"",
            description="**Pour accéder à votre Recherche, cliquez sur l'emoji correspondant.**",
            color=0x2b2d31
        )
        
        result_text = ""
        for i, r in enumerate(valid):
            result_text += f"{EMOJI_LIST[i]} {r.get('title') or r.get('name')}\n"
        
        embed.add_field(name="", value=result_text, inline=False)
        embed.set_footer(text=f"Page 1/1 - Total de {len(valid)} résultat(s)")
        
        await interaction.response.send_message(embed=embed, view=ResultView(valid, self.recherche.value), ephemeral=True)

@bot.tree.command(name="ajouter_film", description="Ajouter un film avec ses liens")
async def add_film(interaction: discord.Interaction, tmdb_id: str, lien_lecture: str, lien_bande_annonce: str = None):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("❌ Réservé aux admins.", ephemeral=True)
    
    db = load_db()
    db["links"][tmdb_id] = lien_lecture
    
    if lien_bande_annonce:
        db["trailers"][tmdb_id] = lien_bande_annonce
    
    save_db(db)
    
    msg = f"✅ Film ajouté (ID: {tmdb_id})\n📺 Lien de lecture ajouté"
    if lien_bande_annonce:
        msg += "\n🎬 Bande-annonce ajoutée"
    
    await interaction.response.send_message(msg, ephemeral=True)
    
    # Envoyer notification
    await send_notification("movie", tmdb_id, interaction.user)

@bot.tree.command(name="ajouter_saison", description="Ajouter une saison complète d'une série")
async def add_season(interaction: discord.Interaction, tmdb_id: str, saison: int, liens: str):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("❌ Réservé aux admins.", ephemeral=True)
    
    liste_liens = liens.replace(',', ' ').split()
    db = load_db()
    
    for i, lien in enumerate(liste_liens, 1):
        db["links"][f"{tmdb_id}_S{saison}_E{i}"] = lien
    
    save_db(db)
    await interaction.response.send_message(f"✅ {len(liste_liens)} épisodes ajoutés pour la saison {saison} !", ephemeral=True)
    
    # Envoyer notification
    await send_notification("tv", tmdb_id, interaction.user)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot connecté : {bot.user}")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))