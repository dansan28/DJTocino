import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
import asyncio
from collections import defaultdict

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Cola de canciones por servidor
queues = defaultdict(list)

# Opciones optimizadas de yt-dlp (globales)
YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "extract_flat": "in_playlist",
    "skip_download": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",  # Bind a IPv4
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -b:a 128k",
    "executable": r"C:\Users\danie\ProyectosProgramacion\bot_musica_discord\bin\ffmpeg\ffmpeg.exe"
}

# Función para búsqueda rápida de yt-dlp
async def search_youtube(query):
    loop = asyncio.get_running_loop()
    try:
        # Buscar con timeout
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _search_sync(query)),
            timeout=10.0
        )
        return data
    except asyncio.TimeoutError:
        print("Timeout en búsqueda de YouTube")
        return None
    except Exception as e:
        print(f"Error en búsqueda: {e}")
        return None

def _search_sync(query):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        if info and "entries" in info and len(info["entries"]) > 0:
            return info["entries"][0]
    return None

# Función para obtener URL de streaming
async def get_stream_url(video_url):
    loop = asyncio.get_running_loop()
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _get_stream_sync(video_url)),
            timeout=10.0
        )
        return data
    except asyncio.TimeoutError:
        print("Timeout obteniendo stream URL")
        return None
    except Exception as e:
        print(f"Error obteniendo stream: {e}")
        return None

def _get_stream_sync(video_url):
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info.get("url")

# Intents y bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Evento al iniciar
@bot.event
async def on_ready():
    print(f"🎵 {bot.user} está online!")
    print(f"📡 Latencia: {round(bot.latency * 1000)}ms")
    
    try:
        # Sincronizar comandos
        synced = await bot.tree.sync()
        print(f"✅ Sincronizados {len(synced)} comandos:")
        for cmd in synced:
            print(f"   - /{cmd.name}")
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")  # Mostrar latencia

# Comando saludo
@bot.tree.command(name="saludo", description="Saluda a quien use el comando")
async def greet(interaction: discord.Interaction):
    await interaction.response.send_message(f"¡Hola amigo, {interaction.user.mention}! 👋")

# Comando de prueba de latencia
@bot.tree.command(name="ping", description="Muestra la latencia del bot")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latencia: {latency}ms")

# Comando skip
@bot.tree.command(name="skip", description="Salta la canción actual")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("⏭️ Canción saltada!")
    else:
        await interaction.response.send_message("❌ No hay canción reproduciéndose.")

# Comando play mejorado con respuesta inmediata
@bot.tree.command(name="play", description="Reproduce una canción o la agrega a la cola")
@app_commands.describe(song_query="Nombre de la canción o URL de YouTube")
async def play(interaction: discord.Interaction, song_query: str):
    # Respuesta inmediata simple
    await interaction.response.send_message(f"🔍 Buscando: **{song_query}**...")
    
    try:
        # Validar canal de voz
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.edit_original_response(content="❌ Debes estar en un canal de voz.")
            return

        voice_channel = interaction.user.voice.channel

        # Buscar canción
        video_info = await search_youtube(song_query)
        
        if not video_info:
            await interaction.edit_original_response(content="❌ No se encontró la canción o hubo un error.")
            return

        title = video_info.get("title", "Desconocido")
        video_url = video_info.get("webpage_url") or video_info.get("url")
        
        # Conectar a canal de voz
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            voice_client = await voice_channel.connect()
        elif voice_channel != voice_client.channel:
            await voice_client.move_to(voice_channel)

        # Obtener URL de streaming
        stream_url = await get_stream_url(video_url)
        
        if not stream_url:
            await interaction.edit_original_response(content="❌ No se pudo obtener el audio.")
            return

        # Agregar a cola
        guild_id = interaction.guild.id
        queues[guild_id].append({
            "url": stream_url,
            "title": title,
            "video_url": video_url
        })

        # Función para reproducir siguiente
        def play_next(error=None):
            if error:
                print(f"❌ Error reproduciendo: {error}")
            
            guild_queue = queues[guild_id]
            
            if guild_queue:
                next_song = guild_queue.pop(0)
                try:
                    audio_source = discord.FFmpegPCMAudio(next_song["url"], **FFMPEG_OPTIONS)
                    voice_client.play(audio_source, after=play_next)
                    print(f"▶️ Reproduciendo: {next_song['title']}")
                except Exception as e:
                    print(f"❌ Error: {e}")
                    play_next()

        # Reproducir o agregar a cola
        if not voice_client.is_playing() and not voice_client.is_paused():
            play_next()
            await interaction.edit_original_response(content=f"▶️ Reproduciendo: **{title}**")
        else:
            queue_position = len(queues[guild_id])
            await interaction.edit_original_response(content=f"➕ Agregada a la cola: **{title}** (Posición: {queue_position})")

    except Exception as e:
        print(f"❌ Error en /play: {e}")
        try:
            await interaction.edit_original_response(content="❌ Error inesperado al reproducir.")
        except:
            print("No se pudo enviar mensaje de error")

# Comando para ver la cola
@bot.tree.command(name="queue", description="Muestra la cola de canciones")
async def queue_cmd(interaction: discord.Interaction):
    guild_queue = queues[interaction.guild.id]
    
    if not guild_queue:
        await interaction.response.send_message("📭 La cola está vacía.")
        return
    
    queue_list = "\n".join([
        f"`{i+1}.` {track['title']}" 
        for i, track in enumerate(guild_queue[:10])  # Mostrar máximo 10
    ])
    
    total = len(guild_queue)
    footer = f"\n\n📊 Total: {total} canciones" if total > 10 else ""
    
    await interaction.response.send_message(f"📜 **Cola de reproducción:**\n{queue_list}{footer}")

# Comando para pausar
@bot.tree.command(name="pause", description="Pausa la reproducción")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("⏸️ Reproducción pausada.")
    else:
        await interaction.response.send_message("❌ No hay nada reproduciéndose.")

# Comando para reanudar
@bot.tree.command(name="resume", description="Reanuda la reproducción")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("▶️ Reproducción reanudada.")
    else:
        await interaction.response.send_message("❌ No hay nada en pausa.")

# Comando para desconectar
@bot.tree.command(name="leave", description="Desconecta el bot del canal de voz")
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    
    if voice_client:
        queues[interaction.guild.id].clear()
        await voice_client.disconnect()
        await interaction.response.send_message("👋 Desconectado y cola limpiada.")
    else:
        await interaction.response.send_message("❌ No estoy en ningún canal de voz.")

# Ejecutar bot
if __name__ == "__main__":
    bot.run(TOKEN)