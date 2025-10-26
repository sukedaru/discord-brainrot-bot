import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from datetime import datetime
from typing import Set
import os

# ===== CONFIGURACIÓN - Variables de entorno =====
CONFIG = {
    'TOKEN': os.getenv('DISCORD_TOKEN'),
    'CHANNEL_ID': int(os.getenv('DISCORD_CHANNEL_ID')) if os.getenv('DISCORD_CHANNEL_ID') else None,
    'PLACE_ID': '109983668079237',
    'SCAN_INTERVAL': 30,
    'MAX_PING': 50,
    'ONLY_NEW_SERVERS': True,
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

seen_servers: Set[str] = set()
server_count = 0

async def scan_servers():
    global server_count
    try:
        url = f"https://games.roblox.com/v1/games/{CONFIG['PLACE_ID']}/servers/Public?sortOrder=Desc&limit=100"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 429:
                    print('⚠️  Rate limit alcanzado. Esperando 60 segundos...')
                    await asyncio.sleep(60)
                    return
                elif response.status != 200:
                    print(f'❌ Error HTTP: {response.status}')
                    return
                
                data = await response.json()
                if not data.get('data'):
                    print('❌ No se encontraron servidores')
                    return
                
                servers = data['data']
                print(f'🔍 Escaneando {len(servers)} servidores...')
                
                new_servers_found = 0
                filtered_by_ping = 0
                
                for server in servers:
                    ping = server['ping']
                    
                    if ping > CONFIG['MAX_PING']:
                        filtered_by_ping += 1
                        continue
                    
                    if CONFIG['ONLY_NEW_SERVERS'] and server['id'] in seen_servers:
                        continue
                    
                    seen_servers.add(server['id'])
                    new_servers_found += 1
                    await send_notification(server)
                    await asyncio.sleep(1.5)
                
                print(f'✅ Nuevos: {new_servers_found} | ❌ Filtrados: {filtered_by_ping}')
                
                if len(seen_servers) > 300:
                    seen_servers.clear()
    except Exception as e:
        print(f'❌ Error: {str(e)}')

async def send_notification(server):
    global server_count
    try:
        channel = bot.get_channel(CONFIG['CHANNEL_ID'])
        if not channel:
            return
        
        now = datetime.now()
        time_str = now.strftime('%H:%M')
        server_count += 1
        ping = server['ping']
        
        color = 0x00ff00 if ping <= 30 else 0x5865F2
        
        embed = discord.Embed(
            title='🧠 Brainrot Server Notify | Suke Noti',
            description=f'**Servidor US/EEUU detectado** 🇺🇸',
            color=color,
            timestamp=now
        )
        embed.add_field(name='👥 Jugadores', value=f"{server['playing']}/{server['maxPlayers']}", inline=True)
        embed.add_field(name='📶 Ping', value=f"**{ping}ms** ⚡", inline=True)
        embed.add_field(name='🔢 Servidor #', value=f"{server_count}", inline=True)
        embed.add_field(name='🏠 Place ID', value=f"`{CONFIG['PLACE_ID']}`", inline=False)
        embed.add_field(name='🆔 Job ID', value=f"```{server['id']}```", inline=False)
        embed.set_footer(text=f"Detected at {time_str}")
        
        await channel.send(embed=embed)
        print(f"📤 Enviado: {server['id'][:8]}... ({ping}ms)")
    except Exception as e:
        print(f'❌ Error notificación: {str(e)}')

@tasks.loop(seconds=CONFIG['SCAN_INTERVAL'])
async def periodic_scan():
    await scan_servers()

@periodic_scan.before_loop
async def before_periodic_scan():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print('═══════════════════════════════════════')
    print('🤖 BOT CONECTADO')
    print(f'📝 Usuario: {bot.user.name}')
    print(f'⏱️  Intervalo: {CONFIG["SCAN_INTERVAL"]}s')
    print(f'📶 Ping ≤ {CONFIG["MAX_PING"]}ms')
    print('═══════════════════════════════════════\n')
    await scan_servers()
    periodic_scan.start()

@bot.command(name='scan')
async def scan_command(ctx):
    await ctx.reply('🔍 Escaneando...')
    await scan_servers()

@bot.command(name='stats')
async def stats_command(ctx):
    embed = discord.Embed(title='📊 Estadísticas', color=0x00ff00)
    embed.add_field(name='Detectados', value=f'{server_count}', inline=True)
    embed.add_field(name='Cache', value=f'{len(seen_servers)}', inline=True)
    await ctx.reply(embed=embed)

if __name__ == '__main__':
    print('🚀 Iniciando bot...\n')
    if not CONFIG['TOKEN'] or not CONFIG['CHANNEL_ID']:
        print('❌ ERROR: Configura DISCORD_TOKEN y DISCORD_CHANNEL_ID')
        exit(1)
    bot.run(CONFIG['TOKEN'])
