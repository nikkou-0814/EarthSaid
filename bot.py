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
import traceback

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

channel_id = int(os.getenv('ChannelID'))
VER = "beta 0.1.3"

status_p2pquake = "接続していません"
status_wolfx = "接続していません"

WOLFX_WS_URL = 'wss://ws-api.wolfx.jp/jma_eew'
P2PQUAKE_WS_URL = 'https://api.p2pquake.net/v2/ws'

with open('testdata.json', 'r', encoding='utf-8') as f:
    test_data_list = json.load(f)

@client.event
async def on_ready():
    print("Bot起動完了")
    await tree.sync()
    await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"CPU, RAM, Ping計測中"))
    client.fetch_p2pquake_task = asyncio.create_task(fetch_p2pquake())
    client.fetch_wolfx_task = asyncio.create_task(fetch_wolfx())
    client.change_bot_presence_task = asyncio.create_task(change_bot_presence(client))

async def change_bot_presence(client):
    while True:
        try:
            cpu_usage = psutil.cpu_percent()
            memory_info = psutil.virtual_memory()
            memory_usage = memory_info.percent

            latency = client.latency * 1000
            ping = round(latency) if latency != float('inf') else "N/A"

            status_message = f"CPU: {cpu_usage}% | RAM: {memory_usage}% | Ping: {ping}ms"
            await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=status_message))
            await asyncio.sleep(10)
        except (discord.ConnectionClosed, ConnectionResetError) as e:
            print(f"ステータス更新中に接続エラーが発生しました: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"予期しないエラーが発生しました: {e}")
            traceback.print_exc()

async def run_speedtest():
    try:
        st = await asyncio.to_thread(speedtest.Speedtest)
        await asyncio.to_thread(st.get_best_server)
        download_speed = await asyncio.to_thread(lambda: int(st.download() / 10**6))
        upload_speed = await asyncio.to_thread(lambda: int(st.upload() / 10**6))
        server_info = st.results.server['name']
    except Exception as e:
        download_speed = "N/A"
        upload_speed = "N/A"
        server_info = "N/A"
        print(f"スピードテストに失敗しました: {e}")
    
    return server_info, download_speed, upload_speed

# WebSocket connection
async def websocket_listener(url, process_function, status_variable_name):
    retry_count = 0
    while True:
        try:
            session = aiohttp.ClientSession()
            async with session.ws_connect(url) as ws:
                globals()[status_variable_name] = "接続しています"
                print(f"{url}へ接続しました。")
                retry_count = 0
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        await process_function(data)
        except aiohttp.ClientError as e:
            print(f"{url}: WebSocket接続エラー: {e}")
            globals()[status_variable_name] = "接続エラー"
        except Exception as e:
            print(f"{url}: エラーが発生しました: {e}")
            traceback.print_exc()
            globals()[status_variable_name] = "接続エラー"
        finally:
            await session.close()
            retry_count += 1
            print(f"{url}: 5秒後に再接続を試みます... (試行回数: {retry_count})")
            globals()[status_variable_name] = "再接続中"
            await asyncio.sleep(5)

async def process_p2pquake_message(data):
    if data['code'] == 551:
        await process_p2pquake_info(data)
    elif data["code"] == 552:
        await process_p2pquake_tsunami(data)
    elif data['code'] == 556:
        await process_p2pquake_eew(data)

async def process_wolfx_message(data):
    if data.get('type') == 'jma_eew':
        await process_eew_data(data)

async def fetch_p2pquake():
    while True:
        try:
            await websocket_listener(
                P2PQUAKE_WS_URL,
                process_p2pquake_message,
                'status_p2pquake'
            )
        except Exception as e:
            print(f"fetch_p2pquake: エラーが発生しました: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

async def fetch_wolfx():
    while True:
        try:
            await websocket_listener(
                WOLFX_WS_URL,
                process_wolfx_message,
                'status_wolfx'
            )
        except Exception as e:
            print(f"fetch_wolfx: エラーが発生しました: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

# P2PQuake info
async def process_p2pquake_info(data):
    quaketype = data.get('issue', {}).get('type', '不明')
    source = data.get('issue', {}).get('source', '不明')
    details = data.get('earthquake', {})
    place = details.get('hypocenter', {}).get('name', '不明')
    magnitude = details.get('hypocenter', {}).get('magnitude', '不明')
    formatted_mag = "{:.1f}".format(magnitude) if isinstance(magnitude, (int, float)) else '不明'
    depth = details.get('hypocenter', {}).get('depth', '不明')
    depth = "ごく浅い" if depth == 0 else (f"{depth}km" if depth != '不明' else '不明')
    max_intensity = details.get('maxScale', '不明')
    domestic_tsunami = details.get('domesticTsunami', '情報なし')
    occurrence_time = details.get('time', '不明')
    formatted_time = '不明'
    comments = data.get('comments', {}).get('freeFormComment', '不明')

    if occurrence_time != '不明':
        try:
            occurrence_time_obj = datetime.strptime(occurrence_time, "%Y/%m/%d %H:%M:%S")
            formatted_time = occurrence_time_obj.strftime("%d日%H時%M分")
        except ValueError:
            formatted_time = '不明'

    tsunami_text = (
        "この地震による津波の心配はありません。" if domestic_tsunami == "None" else
        "この地震による津波の有無は不明です。" if domestic_tsunami == "Unknown" else
        "この地震による津波の有無は現在調査中です。" if domestic_tsunami == "Checking" else
        "この地震により若干の海面変動が予想されますが、被害の心配はありません。" if domestic_tsunami == "NonEffective" else
        "この地震により津波注意報が発表されています。" if domestic_tsunami == "Watch" else
        "この地震により津波警報が発表されています。" if domestic_tsunami == "Warning" else
        "情報なし"
    )
    foreign_tsunami_text = (
        "この地震による日本への津波の心配はありません。" if domestic_tsunami == "None" else
        "この地震による津波の有無は不明です。" if domestic_tsunami == "Unknown" else
        "日本への津波の有無については現在調査中です。" if domestic_tsunami == "Checking" else
        "この地震による日本への津波の心配はありませんが、若干の海面変動があるかもしれません。" if domestic_tsunami == "NonEffective" else
        "この地震により津波注意報が発表されています。" if domestic_tsunami == "Watch" else
        "この地震により津波警報が発表されています。" if domestic_tsunami == "Warning" else
        "情報なし"
    )

    if max_intensity >= 70:
        color = 0x9e00ff
        image = 'shindo7.png'
        formatted_intensity = '7'
    elif max_intensity >= 60:
        color = 0xff0000
        image = 'shindo6s.png'
        formatted_intensity = '6強'
    elif max_intensity >= 55:
        color = 0xe52020
        image = 'shindo6w.png'
        formatted_intensity = '6弱'
    elif max_intensity >= 50:
        color = 0xe58a20
        image = 'shindo5s.png'
        formatted_intensity = '5強'
    elif max_intensity >= 45:
        color = 0xe3a631
        image = 'shindo5w.png'
        formatted_intensity = '5弱'
    elif max_intensity >= 40:
        color = 0xe6d53c
        image = 'shindo4.png'
        formatted_intensity = '4'
    elif max_intensity >= 30:
        color = 0x41ab45
        image = 'shindo3.png'
        formatted_intensity = '3'
    elif max_intensity >= 20:
        color = 0x4178ab
        image = 'shindo2.png'
        formatted_intensity = '2'
    elif max_intensity >= 10:
        color = 0x515b63
        image = 'shindo1.png'
        formatted_intensity = '1'
    else:
        color = 0x515b63
        image = 'unknown.png'
        formatted_intensity = '不明'

    if quaketype == "ScalePrompt":  # 震度速報
        def intensity(scale):
            if scale == 10:
                return "1"
            elif scale == 20:
                return "2"
            elif scale == 30:
                return "3"
            elif scale == 40:
                return "4"
            elif scale == 45:
                return "5弱"
            elif scale == 50:
                return "5強"
            elif scale == 55:
                return "6弱"
            elif scale == 60:
                return "6強"
            elif scale == 70:
                return "7"
            else:
                return "不明"

        points_info = "\n".join([f"{point['addr']}: 震度{intensity(point['scale'])}" for point in data['points']])
        embed = discord.Embed(title="🌍 震度速報", description=f"{formatted_time}頃、\n**最大震度{formatted_intensity}**を観測する地震が発生しました。\n**{tsunami_text}** \n今後の情報に注意してください。", color=color)
        embed.add_field(name="震度情報", value=points_info, inline=False)

        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"震度速報: 最大震度{formatted_intensity}を観測する地震がありました"))
        await asyncio.sleep(20)
        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"CPU, RAM, Ping計測中"))

    elif quaketype == "Destination":  # 震源情報
        embed = discord.Embed(title="🌍 震源情報", description=f"{formatted_time}頃、地震がありました。\n**{tsunami_text}**", color=color)
        embed.add_field(name="震源", value=place, inline=True)
        embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
        embed.add_field(name="深さ", value=depth, inline=True)

        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"震源情報: {place}で地震がありました"))
        await asyncio.sleep(20)
        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"CPU, RAM, Ping計測中"))

    elif quaketype == "DetailScale":  # 地震情報
        embed = discord.Embed(title="🌍 地震情報", description=f"{formatted_time}頃、\n{place}で**最大震度{formatted_intensity}**の地震がありました。\n**{tsunami_text}**", color=color)
        embed.add_field(name="震央", value=place, inline=True)
        embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
        embed.add_field(name="深さ", value=depth, inline=True)

        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"地震情報: {place}で最大震度{formatted_intensity}の地震がありました"))
        await asyncio.sleep(20)
        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"CPU, RAM, Ping計測中"))

    elif quaketype == "Foreign":  # 遠地地震、噴火情報
        comments = data.get('comments', {}).get('freeFormComment', None)
        is_eruption = (
            data.get('earthquake', {}).get('hypocenter', {}).get('name') == '不明' or
            (comments and '大規模な噴火が発生しました' in comments)
        )
        embed = discord.Embed(
            title="🌋 遠地噴火情報" if is_eruption else "🌍 遠地地震情報",
            description=f"{formatted_time}頃、\n海外で大きな{'噴火' if is_eruption else '地震'}がありました。\n**{foreign_tsunami_text}**",
            color=color
        )
        embed.add_field(name="震源", value=place, inline=True)
        if is_eruption:
            embed.add_field(name="噴火情報", value="**大規模な噴火が発生しました**", inline=True)
            image = 'volcano.png'
        else:
            embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
            embed.add_field(name="深さ", value=depth, inline=True)
            image = 'foreign.png'

        if comments:
            embed.add_field(name="コメント", value=comments, inline=False)

        await client.change_presence(
            status=discord.Status.online,
            activity=discord.CustomActivity(name=f"遠地{'噴火' if is_eruption else '地震'}: {place}, M{formatted_mag}")
        )
        await asyncio.sleep(20)
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.CustomActivity(name=f"CPU, RAM, Ping計測中")
        )

    elif quaketype == "Other":  # その他の地震情報
        embed = discord.Embed(title="🌍 地震情報(その他)", description=f"{formatted_time}頃、\n地震がありました。", color=color)
        embed.add_field(name="data", value=data, inline=True)
    
    channel = client.get_channel(channel_id)
    embed.set_footer(text=f"{source} | Version {VER}")

    if quaketype != "Destination" and quaketype != "Other":
        file = discord.File(f"info/{image}", filename=image)
        embed.set_thumbnail(url=f"attachment://{image}")
        await channel.send(embed=embed, file=file)
    else:
        await channel.send(embed=embed)


# P2PQuake eew
async def process_p2pquake_eew(data):
    hypocenter_name = data.get('earthquake', {}).get('hypocenter', {}).get('name', '不明')
    magnitude = data.get('earthquake', {}).get('hypocenter', {}).get('magnitude', '不明')
    depth = data.get('earthquake', {}).get('hypocenter', {}).get('depth', '不明')
    condition = data.get('earthquake', {}).get('condition', '')
    cancelled = data.get('cancelled', 'False')
    channel = client.get_channel(channel_id)

    if cancelled:
        embed = discord.Embed(title="❌先程の緊急地震速報はキャンセルされました", description="", color=discord.Color.green)
        embed.set_footer(text=f"気象庁 | Version {VER}")
        await channel.send(embed=embed)
        return

    areas_info = []
    for area in data.get('areas', []):
        arrival_time = area.get('arrivalTime', '不明')
        try:
            arrival_time_obj = datetime.strptime(arrival_time, "%Y/%m/%d %H:%M:%S")
            formatted_arrival_time = arrival_time_obj.strftime("%H時%M分%S秒")
        except ValueError:
            formatted_arrival_time = '不明'
        areas_info.append(f"{area.get('name', '不明')}（{formatted_arrival_time}）")

    areas_text = "\n".join(areas_info)

    origin_time_str = data.get('earthquake', {}).get('originTime', '不明')
    formatted_origin_time = '不明'
    if origin_time_str != '不明':
        try:
            origin_time_obj = datetime.strptime(origin_time_str, "%Y/%m/%d %H:%M:%S")
            formatted_origin_time = origin_time_obj.strftime("%d日%H時%M分%S秒")
        except ValueError:
            formatted_origin_time = '不明'

    embed = discord.Embed(title="🚨緊急地震速報", description="緊急地震速報です。強い揺れに警戒して下さい。\n緊急地震速報が発令された地域では、震度5弱以上の揺れが来るかもしれません。\n落ち着いて、身の安全を図ってください。", color=0xff0000)
    embed.add_field(name="発震時間", value=formatted_origin_time, inline=True)
    embed.add_field(name="震源地", value=hypocenter_name, inline=True)
    embed.add_field(name="マグニチュード", value=f"M{magnitude}", inline=True)
    embed.add_field(name="深さ", value=f"{depth}km", inline=True)
    if condition == '仮定震源要素':
        embed.add_field(name="仮定震源要素", value="以上の情報は仮に割り振られた情報であり、地震学的な意味を持ちません", inline=True)
    embed.add_field(name="発表地域、到達予想時刻", value=areas_text if areas_text else "発表なし", inline=False)
    embed.set_footer(text=f"気象庁 | Version {VER}")

    await channel.send(embed=embed)

# P2PQuake tsunami
async def process_p2pquake_tsunami(data):
    issue_info = data.get('issue', {})
    issue_type = issue_info.get('type', '不明')
    issue_time_str = issue_info.get('time', '不明')
    source = issue_info.get('source', '不明')

    cancelled = data.get('cancelled', False)
    areas = data.get('areas', [])

    if issue_time_str != '不明':
        try:
            issue_time_obj = datetime.strptime(issue_time_str, "%Y/%m/%d %H:%M:%S")
            formatted_issue_time = issue_time_obj.strftime("%d日%H時%M分")
        except ValueError:
            formatted_issue_time = '不明'
    else:
        formatted_issue_time = '不明'

    if cancelled:
        description = f"津波情報が解除されました。"
        color = 0x00BFFF
        embed = discord.Embed(title="🌊 津波情報", description=description, color=color)
    else:
        description = f"津波情報が発表されました。"
        color = 0xFF4500
        embed = discord.Embed(title="🌊 津波情報", description=description, color=color)
        embed.add_field(name="発表時間", value=formatted_issue_time, inline=True)

        if areas:
            areas_info = []
            for area in areas:
                name = area.get('name', '不明')
                grade = area.get('grade', '不明')
                immediate = area.get('immediate', False)
                first_height = area.get('firstHeight', {})
                arrival_time_str = first_height.get('arrivalTime', '不明')
                condition = first_height.get('condition', '不明')

                if arrival_time_str != '不明':
                    try:
                        arrival_time_obj = datetime.strptime(arrival_time_str, "%Y/%m/%d %H:%M:%S")
                        formatted_arrival_time = arrival_time_obj.strftime("%d日%H時%M分")
                    except ValueError:
                        formatted_arrival_time = '不明'
                else:
                    formatted_arrival_time = '不明'

                max_height = area.get('maxHeight', {})
                max_height_desc = max_height.get('description', '不明')
                max_height_value = max_height.get('value', '不明')

                area_text = (
                    f"**{name}**\n"
                    f"予報種別: {grade}\n"
                    f"第1波到達予想時刻: {formatted_arrival_time}\n"
                    f"状況: {condition}\n"
                    f"予想高さ: {max_height_desc} ({max_height_value}m)\n"
                    f"{'直ちに津波来襲と予想されています。' if immediate else ''}"
                )
                areas_info.append(area_text)

            areas_text = "\n\n".join(areas_info)
            embed.add_field(name="対象地域", value=areas_text, inline=False)
        else:
            embed.add_field(name="対象地域", value="エリアなし", inline=False)

    embed.set_footer(text=f"{source} | Version {VER}")
    channel = client.get_channel(channel_id)
    await channel.send(embed=embed)

# Wolfx
async def process_eew_data(data, is_test=False):
    forecast_warning = os.getenv('ForecastWarning')
    accuracy_boolean = os.getenv('AccuracyBoolean', 'False').lower() == 'true'

    if forecast_warning == 'None':
        return
    elif forecast_warning == 'Warning' and not data.get('isWarn', False):
        return
    elif forecast_warning == 'Forecast' and data.get('isWarn', False):
        return

    report_number = data.get('Serial', '不明')
    is_final = data.get('isFinal', False)
    is_cancel = data.get('isCancel', False)
    is_assumption = data.get('isAssumption', False)
    warn_area = data.get('WarnArea', [])
    chiiki_list = [area.get('Chiiki', '不明') for area in warn_area]
    chiiki = ', '.join(chiiki_list) if chiiki_list else '不明'
    magnitude = data.get('Magunitude', '不明')
    formatted_mag = "{:.1f}".format(float(magnitude)) if magnitude != '不明' else '不明'
    max_intensity = data.get('MaxIntensity', '不明')
    ac_epicenter = data.get('Accuracy', {}).get('Epicenter', '不明')
    ac_depth = data.get('Accuracy', {}).get('Depth', '不明')
    ac_magnitude = data.get('Accuracy', {}).get('Magnitude', '不明')
    origin_time_str = data.get('OriginTime', '不明')
    hypocenter = data.get('Hypocenter', '不明')
    depth = data.get('Depth', '不明')
    channel = client.get_channel(channel_id)

    if is_cancel:
        embed = discord.Embed(title='緊急地震速報 キャンセル', description='先程の緊急地震速報はキャンセルされました', color=color)
        await channel.send(embed=embed)
        return

    try:
        origin_time_obj = datetime.strptime(origin_time_str, "%Y/%m/%d %H:%M:%S")
        formatted_origin_time = origin_time_obj.strftime("%d日%H時%M分")
    except ValueError:
        formatted_origin_time = '不明'

    title_type = "警報" if data.get('isWarn', False) else "予報"
    title = f"{'**テストデータです！**' if is_test else ''}{"🚨" if data.get('isWarn', False) else "⚠️"}緊急地震速報({title_type}) 第{report_number}報"
    description = f"**{formatted_origin_time}頃{hypocenter}で地震、推定最大震度{max_intensity}**"
    color = 0xff0000 if data.get('isWarn', False) else 0xffd700

    if max_intensity == '1':
        image = 'shindo1.png'
    elif max_intensity == '2':
        image = 'shindo2.png'
    elif max_intensity == '3':
        image = 'shindo3.png'
    elif max_intensity == '4':
        image = 'shindo4.png'
    elif max_intensity == '5弱':
        image = 'shindo5w.png'
    elif max_intensity == '5強':
        image = 'shindo5s.png'
    elif max_intensity == '6弱':
        image = 'shindo6w.png'
    elif max_intensity == '6強':
        image = 'shindo6s.png'
    elif max_intensity == '7':
        image = 'shindo7.png'
    elif int(depth) >= 150:
        image = 'deep.png'
    else:
        image = 'unknown.png'
    
    if is_final:
        title += "【最終報】"
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
    if accuracy_boolean:
        embed.add_field(name="震源の精度", value=ac_epicenter, inline=True)
        embed.add_field(name="深さの精度", value=ac_depth, inline=True)
        embed.add_field(name="マグニチュードの精度", value=ac_magnitude, inline=True)
    if chiiki:
        embed.add_field(name="警報区域", value=chiiki, inline=False)
    embed.set_footer(text=f"気象庁 | Version {VER}")

    file_path = "eew/warning" if data.get('isWarn', False) else "eew/forecast"
    file = discord.File(f"{file_path}/{image}", filename=image)
    embed.set_thumbnail(url=f"attachment://{image}")

    await channel.send(embed=embed, file=file, silent=is_test)
    await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"{data['Hypocenter']}最大震度{max_intensity}の地震"))
    if is_final:
        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"{data['Hypocenter']}最大震度{max_intensity}の地震"))
        await asyncio.sleep(20)
        await client.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name=f"CPU, RAM, Ping計測中"))

@tree.command(name="testdata", description="eewのテストをします")
async def testdata(interaction: discord.Interaction):
    await interaction.response.send_message("# 実際の地震ではありません \nテストデータの送信を開始します。")
    for data in test_data_list:
        await process_eew_data(data,is_test=True)
        await asyncio.sleep(random.uniform(0.5, 1))

async def run_speedtest():
    try:
        st = await asyncio.to_thread(speedtest.Speedtest)
        await asyncio.to_thread(st.get_best_server)
        download_speed = await asyncio.to_thread(lambda: int(st.download() / 10**6))
        upload_speed = await asyncio.to_thread(lambda: int(st.upload() / 10**6))
        server_info = st.results.server['name']
    except Exception as e:
        download_speed = "N/A"
        upload_speed = "N/A"
        server_info = "N/A"
        print(f"スピードテストに失敗しました: {e}")
    
    return server_info, download_speed, upload_speed

@tree.command(name="status", description="BOTのステータスを表示します")
async def status(interaction: discord.Interaction):
    await interaction.response.defer()

    embed_1 = discord.Embed(title=f"ステータス", description="基本情報", color=0x00ff00)
    embed_1.add_field(name="CPU使用率", value=f"{psutil.cpu_percent()}%", inline=True)
    embed_1.add_field(name="メモリ使用量", value=f"{psutil.virtual_memory().percent}%", inline=True)
    embed_1.add_field(name="Ping", value=f"{round(client.latency * 1000)}ms", inline=True)
    embed_1.add_field(name="P2PQuake(地震情報)", value=status_p2pquake, inline=True)
    embed_1.add_field(name="Wolfx(緊急地震速報)", value=status_wolfx, inline=True)
    embed_1.set_footer(text=f"1/2")

    await interaction.followup.send(embed=embed_1)

    speedtest_message = await interaction.followup.send("インターネット速度を計測中です...")

    server_info, download_speed, upload_speed = await run_speedtest()

    embed_2 = discord.Embed(title=f"インターネット速度", description="インターネット情報", color=0x00ff00)
    embed_2.add_field(name="サーバー", value=server_info, inline=True)
    embed_2.add_field(name="ダウンロード", value=f"{download_speed}Mbps", inline=True)
    embed_2.add_field(name="アップロード", value=f"{upload_speed}Mbps", inline=True)
    embed_2.set_footer(text=f"2/2")

    await speedtest_message.edit(content=None, embed=embed_2)

client.run(os.getenv('TOKEN'))