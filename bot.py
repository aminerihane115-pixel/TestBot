import discord
import os
import datetime
from dotenv import load_dotenv
from discord.ext import commands
from keep_alive import keep_alive

load_dotenv()

# Configuration du bot
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# --- 1. CLASSE POUR LES BOUTONS (DOIT ÊTRE PLACÉE ICI) ---
class CatalogueButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Sélection Aléatoire", style=discord.ButtonStyle.primary, emoji="🎲")
    async def random_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Lancement d'un film aléatoire...", ephemeral=True)

    @discord.ui.button(label="Anti-Pub", style=discord.ButtonStyle.danger, emoji="🚫")
    async def antipub_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Système anti-pub actif.", ephemeral=True)

    @discord.ui.button(label="Rechercher", style=discord.ButtonStyle.success, emoji="🔎")
    async def search_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Fonction de recherche bientôt disponible !", ephemeral=True)

    @discord.ui.button(label="Mon profil", style=discord.ButtonStyle.secondary, emoji="👤")
    async def profile_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Profil de {interaction.user.display_name}", ephemeral=True)

    @discord.ui.button(label="Faire une demande d'ajout !", style=discord.ButtonStyle.danger, emoji="📝", row=2)
    async def request_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Votre demande a été transmise aux administrateurs.", ephemeral=True)

# --- 2. ÉVÉNEMENTS ---
@bot.event
async def on_ready():
    print(f"Bot allumé : {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Commandes slash synchronisées : {len(synced)}")
    except Exception as e:
        print(e)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    if message.content.lower() == 'bonjour':
        await message.author.send("Comment tu vas ?")
    if message.content.lower() == "bienvenue":
        welcome_channel = bot.get_channel(1333441520732209225)
        if welcome_channel:
            await welcome_channel.send("Bienvenue sur le discord")
    await bot.process_commands(message)

# --- 3. COMMANDES SLASH ---

@bot.tree.command(name="catalogue", description="Affiche le catalogue de films")
async def catalogue(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎬 Catalogue Films",
        description="Notre catalogue contient actuellement **18,906** films.\n"
                    "📺 **Catalogue Séries**\n"
                    "Notre catalogue contient actuellement **6,739** séries,\n"
                    "réparties sur **6,777** saisons, **72,569** épisodes uniques !\n\n"
                    "🔗 Il y a un total de **90,924** liens disponibles.",
        color=discord.Color.from_rgb(43, 45, 49)
    )
    # Image Pathé
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png?format=webp&quality=lossless&width=1124&height=850")
    embed.set_footer(text=f"Pathé Bot • {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # On envoie l'embed avec les boutons
    await interaction.response.send_message(embed=embed, view=CatalogueButtons())

@bot.tree.command(name="warnguy", description="Alerter une personne")
async def warnguy(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message("Alerte envoyée !")
    await member.send("Tu as reçu une alerte")

@bot.tree.command(name="banguy", description="Bannir une personne")
async def banguy(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message("Ban envoyé !")
    try: 
        await member.send("Tu as été banni")
    except: 
        pass
    await member.ban(reason="Tu n'es pas abonné")

@bot.tree.command(name="youtube", description="Affiche ma chaine youtube")
async def youtube(interaction: discord.Interaction):
    await interaction.response.send_message("Voici le lien : https://www.youtube.com/@Gravenilvectuto")

# --- 4. LANCEMENT ---
keep_alive() # Indispensable pour Render
bot.run(os.getenv('DISCORD_TOKEN'))