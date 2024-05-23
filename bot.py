import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiohttp
import asyncio
import requests
import json
import random
import os

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

load_dotenv()

VER = "beta 0.0.9"
EEW_WS_URL = 'wss://ws-api.wolfx.jp/jma_eew'
QUAKE_WS_URL = 'https://api.p2pquake.net/v2/ws'
channel_id = int(os.getenv('ChannelID'))

with open('testdata.json', 'r', encoding='utf-8') as f:
    test_data_list = json.load(f)

@client.event
async def on_ready():
    print("Bot起動完了！")
    await tree.sync()
    await client.change_presence(activity=discord.Game(name=f"{VER}"))
    asyncio.create_task(send_eew_info())
    client.loop.create_task(fetch_earthquake_info())

#info
async def fetch_earthquake_info():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(QUAKE_WS_URL) as ws:
            print("地震情報WebSocketへ接続しました。")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data['code'] == 551:
                        quaketype = data['issue']['type']
                        source = data['issue']['source']
                        details = data['earthquake']
                        place = details['hypocenter']['name']
                        magnitude = details['hypocenter']['magnitude']
                        formatted_mag = "{:.1f}".format(magnitude)
                        depth = details['hypocenter']['depth']
                        if depth == 0:
                            depth = "ごく浅い"
                        else:
                            depth = f"{depth}km"
                        max_intensity = details['maxScale']
                        tsunami_info = data.get("earthquake", {}).get("domesticTsunami")
                        occurrence_time = data.get("earthquake", {}).get("time")

                        if max_intensity >= 70: #7
                            color = 0x9e00ff
                            image = 'shindo7.png'
  
                        elif max_intensity >= 60: #6+
                            color = 0xff0000
                            image = 'shindo6.png'
                        
                        elif max_intensity >= 55: #6-
                            color = 0xe52020
                            image = 'shindo55.png'

                        elif max_intensity >= 50: #5+
                            color = 0xe58a20
                            image = 'shindo5.png'
                        
                        elif max_intensity >= 45: #5-
                            color = 0xe3a631
                            image = 'shindo45.png'

                        elif max_intensity >= 40: #4
                            color = 0xe6d53c
                            image = 'shindo4.png'

                        elif max_intensity >= 30: #3
                            color = 0x41ab45
                            image = 'shindo3.png'
  
                        elif max_intensity >= 20: #2
                            color = 0x4178ab
                            image = 'shindo2.png'

                        elif max_intensity >= 10: #1
                            color = 0x515b63
                            image = 'shindo1.png'
                        else: #不明
                            color = 0x515b63
                            image = 'unknown.png'

                      
                        if quaketype == "ScalePrompt": #震度速報
                            points_info = "\n".join([f"{point['addr']}: 震度{int(point['scale'] / 10)}" for point in data['points']])
                            embed = discord.Embed(title="🌍 震度速報", color=color)
                            embed.add_field(name="", value=f"{occurrence_time}ごろ、\n最大震度{int(max_intensity / 10)}を観測する地震が発生しました。\n津波の有無については、現在調査中です。\n今後の情報に注意してください。", inline=False)
                            embed.add_field(name="震度情報", value=points_info, inline=False)
                            embed.set_footer(text=f"{client.user.name}・{source} | Version {VER}", icon_url=f"{client.user.avatar}")

                            file = discord.File(image, filename=image)
                            embed.set_thumbnail(url=f"attachment://{image}")

                            channel = client.get_channel(channel_id)
                            await channel.send(embed=embed, file=file)

                        elif quaketype == "Destination": #震源情報
                            embed = discord.Embed(title="🌍 震源情報", color=color)
                            if tsunami_info == "None":
                                embed.add_field(name="", value=f"{occurrence_time}ごろ、地震がありました。\nこの地震による津波の心配はありません。", inline=False)
                            else:
                                embed.add_field(name="", value=f"{occurrence_time}ごろ、地震がありました。\n現在、この地震による津波予報等を発表中です。", inline=False)
                            embed.add_field(name="震源", value=place, inline=True)
                            embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
                            embed.add_field(name="深さ", value=depth, inline=True)
                            embed.set_footer(text=f"{client.user.name}・{source} | Version {VER}", icon_url=f"{client.user.avatar}")

                            channel = client.get_channel(channel_id)
                            await channel.send(embed=embed, file=file)

                        elif quaketype == "DetailScale": #地震情報
                            embed = discord.Embed(title="🌍 地震情報", color=color)
                            if tsunami_info == "None":
                                embed.add_field(name="", value=f"{occurrence_time}ごろ、\n{place}で最大震度{int(max_intensity / 10)}の地震がありました。\nこの地震による津波の心配はありません。", inline=False)
                            else:
                                embed.add_field(name="", value=f"{occurrence_time}ごろ、\n{place}で最大震度{int(max_intensity / 10)}の地震がありました。\n現在、この地震による津波予報等を発表中です。", inline=False)
                            embed.add_field(name="震央", value=place, inline=True)
                            embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
                            embed.add_field(name="深さ", value=depth, inline=True)
                            embed.set_footer(text=f"{client.user.name}・{source} | Version {VER}", icon_url=f"{client.user.avatar}")

                            file = discord.File(image, filename=image)
                            embed.set_thumbnail(url=f"attachment://{image}")

                            channel = client.get_channel(channel_id)
                            await channel.send(embed=embed, file=file)
                        
                        elif quaketype == "Foreign": #遠地地震情報
                            embed = discord.Embed(title="🌍 遠地地震情報", color=color)
                            embed.add_field(name="", value=f"{occurrence_time}ごろ、\n遠地で地震がありました。", inline=False)
                            embed.add_field(name="震央", value=place, inline=True)
                            embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
                            embed.add_field(name="深さ", value=depth, inline=True)
                            embed.set_footer(text=f"{client.user.name}・{source} | Version {VER}", icon_url=f"{client.user.avatar}")

                            file = discord.File(image, filename=image)
                            embed.set_thumbnail(url=f"attachment://{image}")

                            channel = client.get_channel(channel_id)
                            await channel.send(embed=embed, file=file)

                        elif quaketype == "Other": #その他の地震情報
                            embed = discord.Embed(title="🌍 地震情報", color=color)
                            embed.add_field(name="", value=f"{occurrence_time}ごろ、\n地震がありました。", inline=False)
                            embed.set_footer(text=f"{client.user.name}・{source} | Version {VER}", icon_url=f"{client.user.avatar}")

                            file = discord.File(image, filename=image)
                            embed.set_thumbnail(url=f"attachment://{image}")

                            channel = client.get_channel(channel_id)
                            await channel.send(embed=embed, file=file)

#eew
async def send_eew_info(data=None):
    async with aiohttp.ClientSession() as session:
        if data:
            report_number = data.get('Serial', '不明')
            is_final = data.get('isFinal', False)
            is_cancel = data.get('isCancel', False)
            is_assumption = data.get('isAssumption', False)
            warn_area = data.get('WarnArea', [])
            chiiki_list = [area['Chiiki'] for area in warn_area]
            chiiki = ', '.join(chiiki_list) if chiiki_list else '発表なし'
            magnitude = data.get('Magunitude', '不明')
            formatted_mag = "{:.1f}".format(float(magnitude)) if magnitude != '不明' else '不明'
            max_intensity = float(data['MaxIntensity'])

            if max_intensity >= 1:
                if max_intensity < 2:
                    image = 'shindo1.png'
                    formatshindo = '1'
                elif max_intensity < 3:
                    image = 'shindo2.png'
                    formatshindo = '2'
                elif max_intensity < 4:
                    image = 'shindo3.png'
                    formatshindo = '3'
                elif max_intensity < 4.5:
                    image = 'shindo4.png'
                    formatshindo = '4'
                elif max_intensity < 5:
                    image = 'shindo45.png'
                    formatshindo = '5弱'
                elif max_intensity < 5.5:
                    image = 'shindo5.png'
                    formatshindo = '5強'
                elif max_intensity < 6:
                    image = 'shindo55.png'
                    formatshindo = '6弱'
                elif max_intensity < 7:
                    image = 'shindo6.png'
                    formatshindo = '6強'
                else:
                    image = 'shindo7.png'
                    formatshindo = '7'
            else:
                image = 'unknown.png'
                formatshindo = '不明'


            title_type = "警報" if data.get('isWarn', False) else "予報"
            title = f"**テストデータです！**緊急地震速報（{title_type}）第{report_number}報"
            if is_final:
                title += "【最終報】"
            if is_cancel:
                title += "【キャンセル】"
            if is_assumption:
                title += f"【推定法: {is_assumption}】"

            color = 0xff0000 if data.get('isWarn', False) else 0xffd700
            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="発震時間", value=data['OriginTime'], inline=False)
            embed.add_field(name="予想最大震度", value=formatshindo, inline=True)
            embed.add_field(name="推定震源地", value=data['Hypocenter'], inline=True)
            embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
            embed.add_field(name="深さ", value=f"{data['Depth']}km", inline=True)
            embed.add_field(name="警報区域", value=chiiki, inline=False)
            embed.set_footer(text=f"{client.user.name}・気象庁 | Version {VER}", icon_url=f"{client.user.avatar}")

            file = discord.File(image, filename=image)
            embed.set_thumbnail(url=f"attachment://{image}")

            channel = client.get_channel(channel_id)
            await channel.send(embed=embed, file=file)
        else:
            while True:
                try:
                    async with session.ws_connect(EEW_WS_URL) as ws:
                        print("緊急地震WebSocketへ接続しました。")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data['type'] == 'jma_eew':
                                    report_number = data.get('Serial', '不明')
                                    is_final = data.get('isFinal', False)
                                    is_cancel = data.get('isCancel', False)
                                    is_assumption = data.get('isAssumption', False)
                                    warn_area = data.get('WarnArea', [])
                                    chiiki_list = [area['Chiiki'] for area in warn_area]
                                    chiiki = ', '.join(chiiki_list) if chiiki_list else '発表なし'
                                    magnitude = data.get('Magunitude', '不明')
                                    formatted_mag = "{:.1f}".format(float(magnitude)) if magnitude != '不明' else '不明'
                                    max_intensity = float(data['MaxIntensity'])

                                    if max_intensity >= 1:
                                        if max_intensity < 2:
                                            image = 'shindo1.png'
                                            formatshindo = '1'
                                        elif max_intensity < 3:
                                            image = 'shindo2.png'
                                            formatshindo = '2'
                                        elif max_intensity < 4:
                                            image = 'shindo3.png'
                                            formatshindo = '3'
                                        elif max_intensity < 4.5:
                                            image = 'shindo4.png'
                                            formatshindo = '4'
                                        elif max_intensity < 5:
                                            image = 'shindo45.png'
                                            formatshindo = '5弱'
                                        elif max_intensity < 5.5:
                                            image = 'shindo5.png'
                                            formatshindo = '5強'
                                        elif max_intensity < 6:
                                            image = 'shindo55.png'
                                            formatshindo = '6弱'
                                        elif max_intensity < 7:
                                            image = 'shindo6.png'
                                            formatshindo = '6強'
                                        else:
                                            image = 'shindo7.png'
                                            formatshindo = '7'
                                    else:
                                        image = 'unknown.png'
                                        formatshindo = '不明'


                                    title_type = "警報" if data.get('isWarn', False) else "予報"
                                    title = f"緊急地震速報（{title_type}）第{report_number}報"
                                    if is_final:
                                        title += "【最終報】"
                                    if is_cancel:
                                        title += "【キャンセル】"
                                    if is_assumption:
                                        title += f"【推定法: {is_assumption}】"

                                    color = 0xff0000 if data.get('isWarn', False) else 0xffd700
                                    embed = discord.Embed(title=title, color=color)
                                    embed.add_field(name="発震時間", value=data['OriginTime'], inline=False)
                                    embed.add_field(name="予想最大震度", value=formatshindo, inline=True)
                                    embed.add_field(name="推定震源地", value=data['Hypocenter'], inline=True)
                                    embed.add_field(name="マグニチュード", value=f"M{formatted_mag}", inline=True)
                                    embed.add_field(name="深さ", value=f"{data['Depth']}km", inline=True)
                                    embed.add_field(name="警報区域", value=chiiki, inline=False)
                                    embed.set_footer(text=f"{client.user.name}・気象庁 | Version {VER}", icon_url=f"{client.user.avatar}")

                                    file = discord.File(image, filename=image)
                                    embed.set_thumbnail(url=f"attachment://{image}")

                                    channel = client.get_channel(channel_id)
                                    await channel.send(embed=embed, file=file)

                            elif msg.type == aiohttp.WSMsgType.CLOSED or msg.type == aiohttp.WSMsgType.ERROR:
                                print("WebSocketがクローズしました。再接続します。")
                                break
                except aiohttp.ClientError as e:
                    print(f"WebSocket接続エラー: {e}")
                    await asyncio.sleep(10)

@tree.command(name="testdata", description="eewのテストをします")
async def testdata(interaction: discord.Interaction):
    await interaction.response.send_message("# 実際の地震ではありません \nテストデータの送信を開始します。")
    for data in test_data_list:
        await send_eew_info(data)
        await asyncio.sleep(random.uniform(0.5, 1))


client.run(os.getenv('TOKEN'))