import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
import asyncio

from collections import defaultdict

queues = defaultdict(list)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

async def search_ytdlp_async(query,ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)



@bot.tree.command(name="skip", description="Salta la canción actual")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("Canción actual saltada!")
    else:
        await interaction.response.send_message("No hay canción reproduciéndose.")





@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} esta online!")



@bot.event
async def on_message(msg):    #Esto es temporal para imprimir el id del server cuando se manda un mensaje
    print(msg.guild.id)



@bot.tree.command(name="saludo", description="Saluda a quien que haya usado esto") #Creo que esto no es necesario, pero lo dejo porque funciona y si lo quito no vaya a ser que mame todo "4 4"
async def greet(interaction: discord.Interaction):
    username = interaction.user.mention
    await interaction.response.send_message(f"Hola amigo, {username}")


@bot.tree.command(name="play", description="Reproduce una cancion o la agrega a la cola")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel

    if voice_channel is None:
        await interaction.followup.send("Debes estar en un canal de voz.")
        return
        
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": "True",
        "youtube_include_dash_manifest": False,
        "youtube_include_hsl_manifest": False,
    }

    query = "ytsearch1: " + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])

    if not tracks:
        await interaction.followup.send("No se encontraron resultados")
        return

    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")

    ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k",
    }

    





    ffmpeg_path = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg", "ffmpeg.exe")



    # Agregar la canción a la cola del servidor
    queues[interaction.guild.id].append({"url": audio_url, "title": title})

    # Función para reproducir la siguiente canción
    def play_next(error=None):
        if queues[interaction.guild.id]:
            next_track = queues[interaction.guild.id].pop(0)
            source = discord.FFmpegOpusAudio(
                next_track["url"],
                **ffmpeg_options,
                executable=ffmpeg_path
            )
            voice_client.play(source, after=play_next)
        else:
            print("La cola ha terminado")

    # Iniciar reproducción si no hay nada sonando
    if not voice_client.is_playing():
        play_next()
        await interaction.followup.send(f"Reproduciendo: **{title}**")
    else:
        await interaction.followup.send(f"Agregada a la cola: **{title}**")


async def queue_cmd(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    queue_list = queues[guild_id]

    if not queue_list:
        await interaction.response.send_message("La cola esta vacia")
        return
    
    msg = "Canciones en cola:**\n"
    for i, track in enumerate(queue_list, start=1):
        title = track.get("Title", "Sin titulo")
        msg += f"{i}. {title}\n"

    if len(msg) > 1900:
        msg = msg[:1900] + "\n... (cola truncada)"
    await interaction.response.send_message(msg)


bot.run(TOKEN)

#  []