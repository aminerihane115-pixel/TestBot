import discord
import os
import json
import requests
from dotenv import load_dotenv
from discord.ext import commands
from keep_alive import keep_alive

load_dotenv()

# Configuration
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
DB_FILE = "db_links.json"

# --- GESTION DE LA BASE DE DONNÉES ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

# --- FONCTIONS TMDB ---
def search_tmdb(query):
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}&language=fr-FR"
    return requests.get(url).json().get('results', [])

def get_details(item_id, media_type):
    url = f"https://api.themoviedb.org/3/{media_type}/{item_id}?api_key={TMDB_API_KEY}&language=fr-FR"
    return requests.get(url).json()

# --- COMMANDE POUR AJOUTER TES LIENS UQLOAD ---
@bot.tree.command(name="ajouter_lien", description="Lier un lien Uqload à un ID TMDB (Admin)")
async def add_link(interaction: discord.Interaction, tmdb_id: str, lien_uqload: str):
    # Optionnel: ajoute une vérification d'ID Discord ici pour être le seul à l'utiliser
    db = load_db()
    db[tmdb_id] = lien_uqload
    save_db(db)
    await interaction.response.send_message(f"✅ Lien ajouté pour l'ID {tmdb_id} !", ephemeral=True)

# --- RECHERCHE ET AFFICHAGE ---
class SearchModal(discord.ui.Modal, title="🎬 Recherche Pathé"):
    recherche = discord.ui.TextInput(label="Nom du film/série", placeholder="Ex: Avatar...")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        resultats = search_tmdb(self.recherche.value)
        options = []
        for item in resultats[:25]:
            m_type = item.get('media_type')
            if m_type in ['movie', 'tv']:
                titre = item.get('title') or item.get('name')
                options.append(discord.SelectOption(label=titre[:100], value=f"{m_type}|{item['id']}"))

        if not options:
            return await interaction.followup.send("❌ Aucun résultat.", ephemeral=True)

        select = discord.ui.Select(options=options)

        async def callback(inter):
            m_type, m_id = select.values[0].split('|')
            info = get_details(m_id, m_type)
            db = load_db()
            
            # On vérifie si tu as ajouté le lien pour cet ID
            lien_final = db.get(str(m_id)) 
            
            embed = discord.Embed(title=info.get('title') or info.get('name'), description=info.get('overview'), color=0x2b2d31)
            if info.get('poster_path'):
                embed.set_image(url=f"https://image.tmdb.org/t/p/w500{info['poster_path']}")
            
            view = discord.ui.View()
            if lien_final:
                view.add_item(discord.ui.Button(label="▶️ Regarder sur Uqload", url=lien_final, style=discord.ButtonStyle.link))
            else:
                view.add_item(discord.ui.Button(label="⌛ Bientôt disponible", disabled=True, style=discord.ButtonStyle.secondary))
            
            # Petit plus: on affiche l'ID pour que tu puisses le copier facilement pour l'ajouter plus tard
            embed.set_footer(text=f"ID TMDB : {m_id}")
            
            await inter.response.send_message(embed=embed, view=view, ephemeral=True)

        select.callback = callback
        view = discord.ui.View(); view.add_item(select)
        await interaction.followup.send("Choisissez un résultat :", view=view, ephemeral=True)

# --- BOUTONS PRINCIPAUX ---
class CatalogueButtons(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    async def search(self, interaction, button): await interaction.response.send_modal(SearchModal())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Connecté : {bot.user}")

@bot.tree.command(name="catalogue")
async def catalogue(interaction):
    embed = discord.Embed(title="✨ PATHÉ STREAMING", color=0x2b2d31)
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png")
    await interaction.response.send_message(embed=embed, view=CatalogueButtons())

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))