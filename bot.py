import discord
import os
import datetime
from dotenv import load_dotenv
from discord.ext import commands
from keep_alive import keep_alive

load_dotenv()

# Configuration du bot
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# --- 1. CLASSE POUR LES BOUTONS ---
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
async def on_member_join(member):
    # Nouvel ID du salon de bienvenue
    channel = bot.get_channel(1453864716911771779) 
    if channel:
        embed = discord.Embed(
            title="👋 Bienvenue !",
            description=f"Bienvenue {member.mention} sur le serveur !\nOn est ravi de te voir ici.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Membre #{member.guild.member_count}")
        await channel.send(content=f"Bienvenue {member.mention} !", embed=embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    if message.content.lower() == 'bonjour':
        await message.author.send("Comment tu vas ?")
    await bot.process_commands(message)

# --- 3. COMMANDES SLASH ---

@bot.tree.command(name="test_bienvenue", description="Simule une arrivée pour tester le salon de bienvenue")
async def test_bienvenue(interaction: discord.Interaction):
    channel = bot.get_channel(1453864716911771779)
    if channel:
        embed = discord.Embed(
            title="👋 Test de Bienvenue !",
            description=f"Ceci est un test. Bienvenue {interaction.user.mention} !",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Test • Membre #{interaction.guild.member_count}")
        
        await channel.send(content=f"Test réussi pour {interaction.user.mention} !", embed=embed)
        await interaction.response.send_message(f"Test envoyé dans <#1453864716911771779>", ephemeral=True)
    else:
        await interaction.response.send_message("Erreur : Salon introuvable.", ephemeral=True)

@bot.tree.command(name="catalogue", description="Affiche le catalogue de films")
async def catalogue(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎬 Catalogue Films",
        description="Notre catalogue contient actuellement **18,906** films.\n"
                    "📺 **Catalogue Séries**\n"
                    "Notre catalogue contient actuellement **6,739** séries.",
        color=discord.Color.from_rgb(43, 45, 49)
    )
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png?format=webp&quality=lossless&width=1124&height=850")
    embed.set_footer(text=f"Pathé Bot • {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    await interaction.response.send_message(embed=embed, view=CatalogueButtons())

@bot.tree.command(name="warnguy", description="Alerter une personne")
async def warnguy(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message("Alerte envoyée !")
    await member.send("Tu as reçu une alerte")

@bot.tree.command(name="banguy", description="Bannir une personne")
async def banguy(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message("Ban envoyé !")
    try: await member.send("Tu as été banni")
    except: pass
    await member.ban(reason="Tu n'es pas abonné")

@bot.tree.command(name="youtube", description="Affiche ma chaine youtube")
async def youtube(interaction: discord.Interaction):
    await interaction.response.send_message("Voici le lien : https://www.youtube.com/@Gravenilvectuto")

# --- 4. LANCEMENT ---
keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))