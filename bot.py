import discord
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime
import speedtest
import aiohttp
import asyncio
import random
import psutil
import json
import os

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

channel_id = int(os.getenv('ChannelID'))
VER = "beta 0.1.2"

status_p2pquake = "未接続"
status_wolfx = "未接続"

WOLFX_WS_URL = 'wss://ws-api.wolfx.jp/jma_eew'
P2PQUAKE_WS_URL = 'wss://api.p2pquake.net/v2/ws'

with open('testdata.json', 'r', encoding='utf-8') as f:
    test_data_list = json.load(f)

@client.event
async def on_ready():
    print("Bot起動完了")
    await tree.sync()
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(name="CPU, RAM, Ping計測中")
    )
    client.loop.create_task(fetch_p2pquake())
    client.loop.create_task(fetch_wolfx())
    client.loop.create_task(change_bot_presence())

async def change_bot_presence():
    while True:
        try:
            cpu_usage = psutil.cpu_percent()
            memory_usage = psutil.virtual_memory().percent
            latency = client.latency * 1000
            ping = "N/A" if latency == float('inf') else f"{round(latency)}ms"

            status_message = f"CPU: {cpu_usage}% | RAM: {memory_usage}% | Ping: {ping}"
            await client.change_presence(
                status=discord.Status.online,
                activity=discord.CustomActivity(name=status_message)
            )
            await asyncio.sleep(10)
        except (discord.ConnectionClosed, ConnectionResetError) as e:
            print(f"ステータス更新エラー: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"予期しないエラー: {e}")

async def fetch_p2pquake():
    global status_p2pquake
    p2pquake_url = P2PQUAKE_WS_URL
    retry_delay = 5

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.ws_connect(p2pquake_url) as ws:
                    status_p2pquake = "接続中"
                    print("P2PQuakeに接続しました。")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            code = data.get('code')
                            if code == 551:
                                await process_p2pquake_info(data)
                            elif code == 552:
                                await process_p2pquake_tsunami(data)
                            elif code == 556:
                                await process_p2pquake_eew(data)
            except aiohttp.ClientError as e:
                print(f"P2PQuake接続エラー: {e}")
                status_p2pquake = "接続エラー"
            except Exception as e:
                print(f"P2PQuakeエラー: {e}")
                status_p2pquake = "接続エラー"
            finally:
                print(f"P2PQuake: {retry_delay}秒後に再接続します...")
                status_p2pquake = "再接続中"
                await asyncio.sleep(retry_delay)

async def fetch_wolfx(data=None):
    global status_wolfx
    retry_delay = 5
    wolfx_url = WOLFX_WS_URL

    async with aiohttp.ClientSession() as session:
        if data:
            await process_eew_data(data, is_test=True)
        else:
            while True:
                try:
                    async with session.ws_connect(wolfx_url) as ws:
                        status_wolfx = "接続中"
                        print("Wolfxに接続しました。")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data.get('type') == 'jma_eew':
                                    await process_eew_data(data)
                except aiohttp.ClientError as e:
                    print(f"Wolfx接続エラー: {e}")
                    status_wolfx = "接続エラー"
                except Exception as e:
                    print(f"Wolfxエラー: {e}")
                    status_wolfx = "接続エラー"
                finally:
                    print(f"Wolfx: {retry_delay}秒後に再接続します...")
                    status_wolfx = "再接続中"
                    await asyncio.sleep(retry_delay)

async def process_p2pquake_info(data):
    quaketype = data.get('issue', {}).get('type', '不明')
    source = data.get('issue', {}).get('source', '不明')
    details = data.get('earthquake', {})
    place = details.get('hypocenter', {}).get('name', '不明')
    magnitude = details.get('hypocenter', {}).get('magnitude', '不明')
    formatted_mag = f"{magnitude:.1f}" if isinstance(magnitude, (int, float)) else '不明'
    depth = details.get('hypocenter', {}).get('depth', '不明')
    depth = "ごく浅い" if depth == 0 else (f"{depth}km" if depth != '不明' else '不明')
    max_intensity = details.get('maxScale', '不明')
    domestic_tsunami = details.get('domesticTsunami', '情報なし')
    occurrence_time = details.get('time', '不明')
    formatted_time = format_time(occurrence_time)

    tsunami_text = get_tsunami_text(domestic_tsunami)
    color, image, formatted_intensity = get_intensity_info(max_intensity)

    embed = None
    if quaketype == "ScalePrompt":
        points_info = "\n".join([
            f"{point['addr']}: 震度{scale_to_intensity(point['scale'])}"
            for point in data['points']
        ])
        embed = discord.Embed(
            title="🌍 震度速報",
            description=(
                f"{formatted_time}頃、\n"
                f"**最大震度{formatted_intensity}**を観測する地震が発生しました。\n"
                f"**{tsunami_text}**\n今後の情報に注意してください。"
            ),
            color=color
        )
        embed.add_field(name="震度情報", value=points_info, inline=False)
        await update_presence(f"震度速報: 最大震度{formatted_intensity}を観測する地震がありました")
    elif quaketype == "Destination":
        embed = discord.Embed(
            title="🌍 震源情報",
            description=f"{formatted_time}頃、地震がありました。\n**{tsunami_text}**",
            color=color
        )
        embed.add_field(name="震源", value=place, inline=True)
        embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
        embed.add_field(name="深さ", value=depth, inline=True)
        await update_presence(f"震源情報: {place}で地震がありました")
    elif quaketype == "DetailScale":
        embed = discord.Embed(
            title="🌍 地震情報",
            description=(
                f"{formatted_time}頃、\n{place}で"
                f"**最大震度{formatted_intensity}**の地震がありました。\n**{tsunami_text}**"
            ),
            color=color
        )
        embed.add_field(name="震央", value=place, inline=True)
        embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
        embed.add_field(name="深さ", value=depth, inline=True)
        await update_presence(f"地震情報: {place}で最大震度{formatted_intensity}の地震がありました")
    elif quaketype == "Foreign":
        image = 'foreign.png'
        embed = discord.Embed(
            title="🌍 遠地地震情報",
            description=(
                f"{formatted_time}頃、\n海外で大きな地震がありました。\n**{tsunami_text}**"
            ),
            color=color
        )
        embed.add_field(name="震源", value=place, inline=True)
        embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
        embed.add_field(name="深さ", value=depth, inline=True)
        await update_presence(f"遠地地震: {place}, M{formatted_mag}")

    if embed:
        embed.set_footer(text=f"{source} | Version {VER}")
        await send_embed(embed, image, quaketype != "Destination" and quaketype != "Other")

async def process_p2pquake_eew(data):
    hypocenter_name = data.get('earthquake', {}).get('hypocenter', {}).get('name', '不明')
    magnitude = data.get('earthquake', {}).get('hypocenter', {}).get('magnitude', '不明')
    depth = data.get('earthquake', {}).get('hypocenter', {}).get('depth', '不明')
    areas_info = [
        f"{area.get('name', '不明')}（{format_time(area.get('arrivalTime', '不明'), '%H時%M分%S秒')}）"
        for area in data.get('areas', [])
    ]
    areas_text = "\n".join(areas_info) if areas_info else "発表なし"
    origin_time_str = data.get('earthquake', {}).get('originTime', '不明')
    formatted_origin_time = format_time(origin_time_str, '%d日%H時%M分%S秒')

    embed = discord.Embed(
        title="🚨緊急地震速報",
        description=(
            "緊急地震速報です。強い揺れに警戒して下さい。\n"
            "緊急地震速報が発令された地域では、震度5弱以上の揺れが来るかもしれません。\n"
            "落ち着いて、身の安全を図ってください。"
        ),
        color=0xff0000
    )
    embed.add_field(name="発震時間", value=formatted_origin_time, inline=True)
    embed.add_field(name="震源地", value=hypocenter_name, inline=True)
    embed.add_field(name="マグニチュード", value=f"M{magnitude}", inline=True)
    embed.add_field(name="深さ", value=f"{depth}km", inline=True)
    embed.add_field(name="発表地域、到達予想時刻", value=areas_text, inline=False)
    embed.set_footer(text=f"気象庁 | Version {VER}")

    channel = client.get_channel(channel_id)
    await channel.send(embed=embed)

async def process_p2pquake_tsunami(data):
    issue_info = data.get('issue', {})
    areas = data.get('areas', [])
    issue_type = issue_info.get('type', '不明')
    issue_time_str = issue_info.get('time', '不明')
    formatted_issue_time = format_time(issue_time_str)
    cancelled = issue_info.get('cancelled', False)
    source = issue_info.get('source', '不明')

    if cancelled:
        description = f"津波情報が解除されました。"
        color = 0x00ff00
    else:
        description = f"津波情報が発表されました。"
        color = 0xff0000

    embed = discord.Embed(title="🌊 津波情報", description=description, color=color)
    embed.add_field(name="発表時間", value=formatted_issue_time, inline=True)

    if not cancelled and areas:
        areas_info = []
        for area in areas:
            name = area.get('name', '不明')
            grade = area.get('grade', '不明')
            immediate = area.get('immediate', False)
            first_height = area.get('firstHeight', {})
            arrival_time = first_height.get('arrivalTime', '不明')
            condition = first_height.get('condition', '不明')

            max_height = area.get('maxHeight', {})
            height_description = max_height.get('description', '不明')
            height_value = max_height.get('value', '不明')

            arrival_time_formatted = format_time(arrival_time, "%H時%M分")

            area_text = f"{name} ({grade})\n到達予想時刻: {arrival_time_formatted}\n予想高さ: {height_description}"
            if immediate:
                area_text += "\n直ちに津波来襲と予測"

            areas_info.append(area_text)

        areas_text = "\n\n".join(areas_info)
        embed.add_field(name="予報区情報", value=areas_text, inline=False)
    else:
        embed.add_field(name="予報区情報", value="予報区情報なし", inline=False)

    embed.set_footer(text=f"{source} | Version {VER}")

    channel = client.get_channel(channel_id)
    await channel.send(embed=embed)

async def process_eew_data(data, is_test=False):
    forecast_warning = os.getenv('ForecastWarning', 'None')
    if forecast_warning == 'None':
        return
    if forecast_warning == 'Warning' and not data.get('isWarn', False):
        return
    if forecast_warning == 'Forecast' and data.get('isWarn', False):
        return

    report_number = data.get('Serial', '不明')
    is_final = data.get('isFinal', False)
    is_cancel = data.get('isCancel', False)
    is_assumption = data.get('isAssumption', False)
    warn_area = data.get('WarnArea', [])
    chiiki_list = [area.get('Chiiki', '不明') for area in warn_area]
    chiiki = ', '.join(chiiki_list) if chiiki_list else '発表なし'
    magnitude = data.get('Magunitude', '不明')
    formatted_mag = f"{float(magnitude):.1f}" if magnitude != '不明' else '不明'
    max_intensity = data.get('MaxIntensity', '不明')
    ac_epicenter = data.get('Accuracy', {}).get('Epicenter', '不明')
    ac_depth = data.get('Accuracy', {}).get('Depth', '不明')
    ac_magnitude = data.get('Accuracy', {}).get('Magnitude', '不明')
    origin_time_str = data.get('OriginTime', '不明')
    hypocenter = data.get('Hypocenter', '不明')
    depth = data.get('Depth', '不明')
    formatted_origin_time = format_time(origin_time_str)

    image = get_eew_image(max_intensity, depth)
    title_type = "警報" if data.get('isWarn', False) else "予報"
    title = f"{'**テストデータです！**' if is_test else ''}{'🚨' if data.get('isWarn', False) else '⚠️'}緊急地震速報({title_type}) 第{report_number}報"
    description = f"**{formatted_origin_time}頃{hypocenter}で地震、推定最大震度{max_intensity}**"
    color = 0xff0000 if data.get('isWarn', False) else 0xffd700

    if is_final:
        title += "【最終報】"
    if is_cancel:
        title += "【キャンセル】"
    if is_assumption:
        title += "【仮定震源】"

    if max_intensity in ["6弱", "6強", "7"]:
        description += "\n\n**緊急地震速報の特別警報です。身の安全を確保してください**"
    else:
        description += "\n\n**強い揺れに警戒してください**" if data.get('isWarn', False) else "\n\n**揺れに備えてください**"

    if int(depth) >= 150:
        description += "\n\n震源が深いため、震央から離れた場所で揺れが大きくなることがあります"

    if is_assumption:
        description += "\n\n**以下の情報は仮に割り振られた情報であり、地震学的な意味を持ちません**"

    embed = discord.Embed(title=title, description=description, color=color)
    embed.add_field(name="推定震源地", value=hypocenter, inline=True)
    embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
    embed.add_field(name="深さ", value=f"{depth}km", inline=True)
    embed.add_field(name="震源の精度", value=ac_epicenter, inline=True)
    embed.add_field(name="深さの精度", value=ac_depth, inline=True)
    embed.add_field(name="マグニチュードの精度", value=ac_magnitude, inline=True)
    embed.add_field(name="警報区域", value=chiiki, inline=False)
    embed.set_footer(text=f"気象庁 | Version {VER}")

    file_path = "eew/warning" if data.get('isWarn', False) else "eew/forecast"
    file = discord.File(f"{file_path}/{image}", filename=image)
    embed.set_thumbnail(url=f"attachment://{image}")

    channel = client.get_channel(channel_id)
    await channel.send(embed=embed, file=file, silent=is_test)
    await update_presence(f"{hypocenter}最大震度{max_intensity}の地震")
    if is_final:
        await asyncio.sleep(20)
        await update_presence("CPU, RAM, Ping計測中")

@tree.command(name="testdata", description="eewのテストをします")
async def testdata(interaction: discord.Interaction):
    await interaction.response.send_message("# 実際の地震ではありません\nテストデータの送信を開始します。")
    for data in test_data_list:
        await fetch_wolfx(data)
        await asyncio.sleep(random.uniform(0.5, 1))

@tree.command(name="status", description="BOTのステータスを表示します")
async def status(interaction: discord.Interaction):
    await interaction.response.defer()

    embed_1 = discord.Embed(title="ステータス", description="基本情報", color=0x00ff00)
    embed_1.add_field(name="CPU使用率", value=f"{psutil.cpu_percent()}%", inline=True)
    embed_1.add_field(name="メモリ使用量", value=f"{psutil.virtual_memory().percent}%", inline=True)
    embed_1.add_field(name="Ping", value=f"{round(client.latency * 1000)}ms", inline=True)
    embed_1.add_field(name="P2PQuake(地震情報)", value=status_p2pquake, inline=True)
    embed_1.add_field(name="Wolfx(緊急地震速報)", value=status_wolfx, inline=True)
    embed_1.set_footer(text="1/2")

    await interaction.followup.send(embed=embed_1)

    speedtest_message = await interaction.followup.send("インターネット速度を計測中です...")

    try:
        st = speedtest.Speedtest()
        st.get_best_server()

        download_speed = int(st.download() / 10**6)
        upload_speed = int(st.upload() / 10**6)
        server_info = st.results.server['name']
    except Exception as e:
        download_speed = "N/A"
        upload_speed = "N/A"
        server_info = "N/A"
        print(f"スピードテストに失敗しました: {e}")

    embed_2 = discord.Embed(title="インターネット速度", description="インターネット情報", color=0x00ff00)
    embed_2.add_field(name="サーバー", value=server_info, inline=True)
    embed_2.add_field(name="ダウンロード", value=f"{download_speed}Mbps", inline=True)
    embed_2.add_field(name="アップロード", value=f"{upload_speed}Mbps", inline=True)
    embed_2.set_footer(text="2/2")

    await speedtest_message.edit(content=None, embed=embed_2)

def format_time(time_str, fmt="%d日%H時%M分"):
    if time_str != '不明':
        try:
            time_obj = datetime.strptime(time_str, "%Y/%m/%d %H:%M:%S")
            return time_obj.strftime(fmt)
        except ValueError:
            return '不明'
    return '不明'

def get_tsunami_text(domestic_tsunami):
    return {
        "None": "この地震による津波の心配はありません。",
        "Unknown": "この地震による津波の有無は不明です。",
        "Checking": "この地震による津波の有無は現在調査中です。",
        "NonEffective": "この地震により若干の海面変動が予想されますが、被害の心配はありません。",
        "Watch": "この地震により津波注意報が発表されています。",
        "Warning": "この地震により津波警報が発表されています。"
    }.get(domestic_tsunami, "情報なし")

def get_intensity_info(max_intensity):
    intensity_map = [
        (70, 0x9e00ff, 'shindo7.png', '7'),
        (60, 0xff0000, 'shindo6s.png', '6強'),
        (55, 0xe52020, 'shindo6w.png', '6弱'),
        (50, 0xe58a20, 'shindo5s.png', '5強'),
        (45, 0xe3a631, 'shindo5w.png', '5弱'),
        (40, 0xe6d53c, 'shindo4.png', '4'),
        (30, 0x41ab45, 'shindo3.png', '3'),
        (20, 0x4178ab, 'shindo2.png', '2'),
        (10, 0x515b63, 'shindo1.png', '1'),
    ]
    for threshold, color, image, intensity in intensity_map:
        if max_intensity >= threshold:
            return color, image, intensity
    return 0x515b63, 'unknown.png', '不明'

def scale_to_intensity(scale):
    return {
        10: "1",
        20: "2",
        30: "3",
        40: "4",
        45: "5弱",
        50: "5強",
        55: "6弱",
        60: "6強",
        70: "7"
    }.get(scale, "不明")

def get_eew_image(max_intensity, depth):
    depth = int(depth) if depth != '不明' else 0
    if max_intensity == '1':
        return 'shindo1.png'
    elif max_intensity == '2':
        return 'shindo2.png'
    elif max_intensity == '3':
        return 'shindo3.png'
    elif max_intensity == '4':
        return 'shindo4.png'
    elif max_intensity == '5弱':
        return 'shindo5w.png'
    elif max_intensity == '5強':
        return 'shindo5s.png'
    elif max_intensity == '6弱':
        return 'shindo6w.png'
    elif max_intensity == '6強':
        return 'shindo6s.png'
    elif max_intensity == '7':
        return 'shindo7.png'
    elif depth >= 150:
        return 'deep.png'
    else:
        return 'unknown.png'

async def update_presence(message):
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(name=message)
    )
    await asyncio.sleep(20)
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(name="CPU, RAM, Ping計測中")
    )

async def send_embed(embed, image_file, with_image=True):
    channel = client.get_channel(channel_id)
    if with_image:
        file = discord.File(f"info/{image_file}", filename=image_file)
        embed.set_thumbnail(url=f"attachment://{image_file}")
        await channel.send(embed=embed, file=file)
    else:
        await channel.send(embed=embed)

client.run(os.getenv('TOKEN'))