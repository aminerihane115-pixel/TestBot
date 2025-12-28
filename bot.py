import discord
import os
import datetime
from dotenv import load_dotenv
from discord.ext import commands
from keep_alive import keep_alive

load_dotenv()

print("Lancement du bot...")
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    print("Bot allumé !")
    try:
        synced = await bot.tree.sync()
        print(f"Commandes slash synchronisées : {len(synced)}")
    except Exception as e:
        print(e)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.content.lower() == 'bonjour':
        author = message.author
        await author.send("Comment tu vas ?")

    if message.content.lower() == "bienvenue":
        welcome_channel = bot.get_channel(1333441520732209225)
        if welcome_channel:
            await welcome_channel.send("Bienvenue sur le discord")

    await bot.process_commands(message)

@bot.tree.command(name="test", description="Tester les embeds")
async def test(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Test Title",
        description="Description de l'embed",
        color=discord.Color.blue()
    )
    embed.add_field(name="Python", value="Apprendre le python en s'amusant")
    embed.add_field(name="Wev", value="Apprendre le web en s'amusant")
    embed.set_footer(text="Pied de page")
    embed.set_image(url="https://media.discordapp.net/attachments/1453864717897699379/1454074612815102148/Pathe_Logo.svg.png?format=webp&quality=lossless&width=1124&height=850")
    await interaction.response.send_message(embed=embed)

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
    await interaction.response.send_message("Voici le lien de ma chaine : https://www.youtube.com/@Gravenilvectuto")

keep_alive() # Cela lance le serveur Flask
bot.run(os.getenv('DISCORD_TOKEN'))