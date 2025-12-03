import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from datetime import datetime
from typing import Set
import os
from aiohttp import web

# ===== CONFIGURACIÓN - Variables de entorno =====
CONFIG = {
    'TOKEN': os.getenv('DISCORD_TOKEN'),
    'CHANNEL_ID': int(os.getenv('DISCORD_CHANNEL_ID')) if os.getenv('DISCORD_CHANNEL_ID') else None,
    'PLACE_ID': '109983668079237',
    'SCAN_INTERVAL': 15,
    'MAX_PING': 150,
    'ONLY_NEW_SERVERS': True,
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

seen_servers: Set[str] = set()
server_count = 0

# ===== SERVIDOR HTTP PARA RENDER =====
async def health_check(request):
    """Endpoint para que Render detecte que el servicio está vivo"""
    return web.Response(text=f"🤖 Bot is running! | Servers detected: {server_count}")

async def start_http_server():
    """Inicia un servidor HTTP simple en el puerto que Render espera"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    port = int(os.getenv('PORT', 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f'🌐 Servidor HTTP iniciado en puerto {port}')

# ===== ESCANEAR SERVIDORES =====
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
                    jobid_preview = server['id'][:8]
                    
                    # Filtrar por ping
                    if ping > CONFIG['MAX_PING']:
                        filtered_by_ping += 1
                        continue
                    else:
                        print(f"  ✅ [{jobid_preview}...] {ping}ms - ACEPTADO")
                    
                    # Solo nuevos servidores
                    if CONFIG['ONLY_NEW_SERVERS'] and server['id'] in seen_servers:
                        print(f"     (Ya visto, ignorando)")
                        continue
                    
                    # Marcar como visto
                    seen_servers.add(server['id'])
                    new_servers_found += 1
                    
                    # Enviar notificación inmediatamente
                    await send_notification(server)
                    await asyncio.sleep(0.5)
                
                print(f'✅ Nuevos: {new_servers_found} | ❌ Filtrados (ping>{CONFIG["MAX_PING"]}ms): {filtered_by_ping}')
                
                if new_servers_found == 0:
                    print(f'ℹ️  No hay nuevos servidores con ping ≤ {CONFIG["MAX_PING"]}ms')
                
                # Limpiar cache
                if len(seen_servers) > 300:
                    to_remove = len(seen_servers) - 200
                    for _ in range(to_remove):
                        seen_servers.pop()
                    print('🗑️  Cache limpiado')
    
    except Exception as e:
        print(f'❌ Error al escanear: {str(e)}')

# ===== NOTIFICACIÓN DISCORD =====
async def send_notification(server):
    global server_count
    try:
        channel = bot.get_channel(CONFIG['CHANNEL_ID'])
        if not channel:
            print('❌ Canal no encontrado')
            return
        
        now = datetime.now()
        time_str = now.strftime('%H:%M')
        server_count += 1
        ping = server['ping']
        
        # Color según el ping
        if ping <= 30:
            color = 0x00ff00  # Verde (excelente)
        elif ping <= 50:
            color = 0x5865F2  # Azul (bueno)
        else:
            color = 0xffaa00  # Amarillo (moderado)
        
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
        embed.set_footer(text=f"Detected at {time_str} • hoy a las {time_str}")
        
        await channel.send(embed=embed)
        print(f"📤 Notificación enviada: {server['id'][:8]}... ({ping}ms)")
    
    except Exception as e:
        print(f'❌ Error al enviar notificación: {str(e)}')

# ===== TAREA PERIÓDICA =====
@tasks.loop(seconds=CONFIG['SCAN_INTERVAL'])
async def periodic_scan():
    await scan_servers()

@periodic_scan.before_loop
async def before_periodic_scan():
    await bot.wait_until_ready()

# ===== EVENTOS =====
@bot.event
async def on_ready():
    print('╔════════════════════════════════════════╗')
    print('🤖 BOT CONECTADO')
    print('╚════════════════════════════════════════╗')
    print(f'📝 Usuario: {bot.user.name}')
    print(f'🎮 Juego: Steal a Brainrot')
    print(f'⏱️  Intervalo de escaneo: {CONFIG["SCAN_INTERVAL"]}s')
    print(f'📶 FILTRO: Ping ≤ {CONFIG["MAX_PING"]}ms (Solo US/EEUU)')
    print('╚════════════════════════════════════════╗')
    print('🔄 Iniciando escaneo...\n')
    
    # Iniciar servidor HTTP para Render
    asyncio.create_task(start_http_server())
    
    # Iniciar escaneo
    await scan_servers()
    periodic_scan.start()

# ===== COMANDOS =====
@bot.command(name='scan')
async def scan_command(ctx):
    """Escanear servidores ahora"""
    await ctx.reply('🔍 Escaneando servidores...')
    await scan_servers()

@bot.command(name='stats')
async def stats_command(ctx):
    """Ver estadísticas del bot"""
    embed = discord.Embed(
        title='📊 Estadísticas del Bot',
        color=0x00ff00,
        timestamp=datetime.now()
    )
    
    embed.add_field(name='Servidores detectados', value=f'{server_count}', inline=True)
    embed.add_field(name='Servidores en cache', value=f'{len(seen_servers)}', inline=True)
    embed.add_field(name='Intervalo de escaneo', value=f'{CONFIG["SCAN_INTERVAL"]}s', inline=True)
    
    await ctx.reply(embed=embed)

@bot.command(name='clear')
@commands.has_permissions(administrator=True)
async def clear_command(ctx):
    """Limpiar cache (solo administradores)"""
    global server_count
    seen_servers.clear()
    server_count = 0
    await ctx.reply('🗑️ Cache limpiado y contador reseteado')

@clear_command.error
async def clear_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply('❌ Solo administradores pueden usar este comando')

@bot.command(name='help')
async def help_command(ctx):
    """Mostrar ayuda"""
    embed = discord.Embed(
        title='📖 Comandos Disponibles',
        description='Lista de comandos del bot:',
        color=0x0099ff
    )
    
    embed.add_field(name='!scan', value='Escanear servidores ahora', inline=False)
    embed.add_field(name='!stats', value='Ver estadísticas del bot', inline=False)
    embed.add_field(name='!clear', value='Limpiar cache (solo admins)', inline=False)
    embed.add_field(name='!help', value='Mostrar esta ayuda', inline=False)
    
    await ctx.reply(embed=embed)

# ===== MANEJO DE ERRORES =====
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f'❌ Error en comando: {str(error)}')

# ===== INICIAR =====
if __name__ == '__main__':
    print('🚀 Iniciando bot...\n')
    if not CONFIG['TOKEN'] or not CONFIG['CHANNEL_ID']:
        print('❌ ERROR: Configura DISCORD_TOKEN y DISCORD_CHANNEL_ID en las variables de entorno')
        exit(1)
    
    try:
        bot.run(CONFIG['TOKEN'])
    except Exception as e:
        print(f'❌ Error fatal: {str(e)}')
