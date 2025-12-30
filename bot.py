import discord
import os
import datetime
import requests
from dotenv import load_dotenv
from discord.ext import commands
from keep_alive import keep_alive

load_dotenv()

# Configuration du bot
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Récupération de ta clé TMDB
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# --- FONCTIONS TMDB ---

def search_tmdb(query):
    """Cherche un film ou une série sur TMDB"""
    if not TMDB_API_KEY:
        print("Erreur : TMDB_API_KEY manquante dans l'environnement !")
        return []
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}&language=fr-FR"
    try:
        response = requests.get(url).json()
        return response.get('results', [])
    except Exception as e:
        print(f"Erreur lors de la recherche : {e}")
        return []

def get_details(item_id, media_type):
    """Récupère les détails complets"""
    url = f"https://api.themoviedb.org/3/{media_type}/{item_id}?api_key={TMDB_API_KEY}&language=fr-FR"
    return requests.get(url).json()

# --- 1. SYSTÈME DE RECHERCHE (MODAL & SELECT) ---

class SearchModal(discord.ui.Modal, title="🎬 Recherche Pathé"):
    recherche = discord.ui.TextInput(
        label="Quel film/série recherchez-vous ?",
        placeholder="Ex: Avatar, Inception, Breaking Bad...",
        min_length=2,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        resultats = search_tmdb(self.recherche.value)
        
        # On ne garde que les films et séries qui ont un nom et une date
        options = []
        for item in resultats:
            m_type = item.get('media_type')
            if m_type in ['movie', 'tv']:
                titre = item.get('title') or item.get('name')
                date = item.get('release_date') or item.get('first_air_date') or "????"
                
                options.append(discord.SelectOption(
                    label=titre[:100], 
                    description=f"[{m_type.upper()}] - Sortie : {date[:4]}", 
                    value=f"{m_type}|{item['id']}"
                ))

        if not options:
            return await interaction.followup.send(f"❌ Aucun résultat pour '{self.recherche.value}'", ephemeral=True)

        # Création du Menu Déroulant
        select = discord.ui.Select(placeholder="Choisissez parmi les résultats...", options=options[:25])

        async def select_callback(inter):
            await inter.response.defer(ephemeral=True)
            m_type, m_id = select.values[0].split('|')
            info = get_details(m_id, m_type)
            
            titre = info.get('title') or info.get('name')
            synopsis = info.get('overview', 'Aucun résumé disponible.')
            note = info.get('vote_average', 0)
            genres = ", ".join([g['name'] for g in info.get('genres', [])])
            
            embed = discord.Embed(
                title=f"🎬 {titre}",
                description=f"**Genre :** {genres}\n**Note :** ⭐ {note:.1f}/10\n\n**Synopsis :**\n{synopsis}",
                color=discord.Color.from_rgb(43, 45, 49),
                timestamp=datetime.datetime.now()
            )
            
            poster = info.get('poster_path')
            if poster:
                embed.set_image(url=f"https://image.tmdb.org/t/p/w500{poster}")
            
            # --- CONFIGURATION DU LIEN ---
            # Remplace 'ton-site.com' par ton vrai domaine
            lien_streaming = f"https://ton-site.com/watch/{m_type}/{m_id}" 
            
            view_link = discord.ui.View()
            view_link.add_item(discord.ui.Button(label="▶️ Regarder maintenant", url=lien_streaming, style=discord.ButtonStyle.link))
            
            await inter.followup.send(embed=embed, view=view_link, ephemeral=True)

        select.callback = select_callback
        view_select = discord.ui.View()
        view_select.add_item(select)
        await interaction.followup.send(f"🔎 Résultats pour **{self.recherche.value}** :", view=view_select, ephemeral=True)

# --- 2. BOUTONS DU CATALOGUE ---

class CatalogueButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    async def search_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchModal())

    @discord.ui.button(label="Anti-Pub", style=discord.ButtonStyle.danger, emoji="🚫")
    async def antipub_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛡️ Utilisez un bloqueur de pub pour une meilleure expérience.", ephemeral=True)

# --- 3. ÉVÉNEMENTS & COMMANDES ---

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    await bot.tree.sync()

@bot.tree.command(name="catalogue", description="Ouvrir le moteur de recherche Pathé")
async def catalogue(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ PATHÉ STREAMING",
        description="Cherchez parmi plus de **90,000** titres via notre moteur intelligent.\n\n"
                    "Cliquez sur **Rechercher** ci-dessous.",
        color=discord.Color.from_rgb(43, 45, 49)
    )
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png")
    await interaction.response.send_message(embed=embed, view=CatalogueButtons())

# --- LANCEMENT ---
keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))