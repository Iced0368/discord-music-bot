import discord

from discord.ext import commands
from ytdlsource import YTDLSource
from discord.ext.commands import Context
from pytube import Playlist

import asyncio, random, os
from asyncq import AsyncDeque

f = open('token.txt', 'r')
TOKEN = f.readline().strip()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='?', intents=intents)

# 재생 대기열 (URL만 저장)
song_queue = AsyncDeque()
current_song = None
control_message = None

async def update_control_message(ctx):
    """상태 메시지 및 UI를 업데이트"""
    global control_message

    if current_song:
        description = f"🎵 **지금 재생 중:** {current_song['title']}\n**현재 대기열:** {len(song_queue._queue)}개"
    else:
        description = "🎵 **현재 대기열:** (비어있음)\n"

    embed = discord.Embed(title="🎶 음악 컨트롤", description=description, color=discord.Color.blurple())

     # 기존 메시지가 있으면 삭제
    if control_message:
        await control_message.delete()

    # 새로운 메시지 전송 (최하단에 위치)
    control_message = await ctx.send(embed=embed, view=MusicButtons())


async def play_next(ctx):
    global current_song

    if song_queue.empty():
        current_song = None
        await update_control_message(ctx)
        return

    try:
        # 대기열에서 URL 가져오기
        url = await song_queue.get()

        # URL을 기반으로 player 생성
        async with ctx.typing():
            player = await YTDLSource.from_url(url, stream=True)
            song = {"player": player, "title": player.title}

            # 곡 재생
            ctx.voice_client.play(
                song["player"],
                after=lambda e: bot.loop.create_task(play_next(ctx)) if e is None else print(f"Error in play_next: {e}"),
            )
            current_song = song  # 현재 곡을 기록
            await update_control_message(ctx)

    except Exception as e:
        print(f"Error while playing song: {e}")
        await play_next(ctx)  # 다음 곡으로 넘어감


class MusicButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_buttons(self, interaction: discord.Interaction):
        """현재 상태에 따라 Play/Pause 버튼 라벨 변경"""
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "play_pause":
                child.label = "⏸️ 정지" if is_playing else "▶️ 재생"
        await interaction.message.edit(view=self)

    @discord.ui.button(label="⏸️ 정지", style=discord.ButtonStyle.blurple, custom_id="play_pause")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        global is_playing
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            is_playing = False
        else:
            vc.resume()
            is_playing = True

        await self.update_buttons(interaction)
        await interaction.response.defer()


    @discord.ui.button(label="⏭️ 스킵", style=discord.ButtonStyle.blurple)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ 곡을 스킵했습니다!", ephemeral=True)
        else:
            await interaction.response.send_message("스킵할 곡이 없습니다!", ephemeral=True)

    @discord.ui.button(label="🛑 중지", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
            await interaction.response.send_message("🛑 음악 재생을 중단하고 음성 채널에서 나갔습니다!", ephemeral=True)
            song_queue._queue.clear()  # 대기열 초기화
            vc.disconnect()
        else:
            await interaction.response.send_message("봇이 음성 채널에 있지 않습니다!", ephemeral=True)

    @discord.ui.button(label="🔀 셔플", style=discord.ButtonStyle.green)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue_list = list(song_queue._queue)
        random.shuffle(queue_list)
        song_queue._queue.clear()
        for item in queue_list:
            await song_queue.put(item)

        await interaction.response.send_message("🔀 대기열이 셔플되었습니다!", ephemeral=True)


@bot.command(name='play')
async def play(ctx: Context, url):
    global current_song

    if not ctx.author.voice:
        await ctx.send("음성 채널에 먼저 들어가주세요!")
        return

    channel = ctx.author.voice.channel

    if not ctx.voice_client:
        await channel.connect()

    if '&list=' in url or 'playlist' in url:
        playlist = Playlist(url)

        for url in playlist:
            await song_queue.put(url)

        await ctx.send(f"대기열에 추가됨: {len(playlist.video_urls)}개의 음악")

    else:
        # URL을 대기열에 추가
        await song_queue.put(url)
        await ctx.send(f"대기열에 추가됨: {url}")

    # 대기열에서 자동 재생
    if not ctx.voice_client.is_playing() and current_song is None:
        await play_next(ctx)

@bot.command(name='play_first')
async def play_first(ctx: Context, url):
    global current_song

    if not ctx.author.voice:
        await ctx.send("음성 채널에 먼저 들어가주세요!")
        return

    channel = ctx.author.voice.channel

    if not ctx.voice_client:
        await channel.connect()

    if '&list=' in url or 'playlist' in url:
        playlist = Playlist(url)

        for url in playlist[::-1]:
            await song_queue.put_first(url)

        await ctx.send(f"대기열에 추가됨: {len(playlist.video_urls)}개의 음악")

    else:
        # URL을 대기열에 추가
        await song_queue.put_first(url)
        await ctx.send(f"대기열에 추가됨: {url}")

    # 대기열에서 자동 재생
    if not ctx.voice_client.is_playing() and current_song is None:
        await play_next(ctx)



@bot.command(name='skip')
async def skip(ctx: Context):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("현재 곡을 스킵합니다.")
        await update_control_message(ctx)


@bot.command(name='queue')
async def queue(ctx: Context):
    if song_queue.empty():
        await ctx.send("대기열이 비어있습니다.")
    else:
        queue_list = list(song_queue._queue)  # asyncio.Queue 내부 접근

        if len(queue_list) < 5:
            await ctx.send("현재 대기열:\n" + "\n".join(queue_list))
        else:
            await ctx.send(f"현재 대기열:\n" + "\n".join(queue_list[:5]) + "\n 외 " + str(len(queue_list) - 5) + " 개의 음악")

    await update_control_message(ctx)


@bot.command(name='stop')
async def stop(ctx: Context):
    global current_song, control_message

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("재생 중지 및 음성 채널에서 나왔습니다.")
        current_song = None
        control_message = None
        song_queue._queue.clear()  # 대기열 초기화
    
    await update_control_message(ctx)


@bot.command(name='shuffle')
async def shuffle(ctx: Context):
    # 대기열에서 곡들을 리스트로 변환하여 섞음
    queue_list = list(song_queue._queue)
    random.shuffle(queue_list)

    song_queue._queue.clear()

    # 섞인 리스트를 다시 대기열에 넣음
    for song in queue_list:
        await song_queue.put(song)

    await ctx.send("대기열을 섞었습니다!")
    await update_control_message(ctx)


@bot.command(name='clear')
async def clear(ctx: Context):
    song_queue._queue.clear()
    await ctx.send("대기열을 초기화 했습니다!")
    await update_control_message(ctx)


@bot.event
async def on_ready():
    print(f'{bot.user} 에 로그인하였습니다!')


@bot.event
async def on_voice_state_update(member, before, after):
    # 유저가 음성 채널에서 나갔을 때, 봇 외에 아무도 남지 않으면 봇이 나가도록 설정
    if before.channel is not None and after.channel is None:
        # 현재 채널에 봇만 남아있는지 확인
        if len(before.channel.members) == 1:  # 봇만 남아있을 경우
            await before.channel.guild.voice_client.disconnect()
            song_queue._queue.clear()  # 대기열 초기화
            print(f'{bot.user} 음성 채널에서 나갔습니다.')


# 봇 실행
bot.run(TOKEN)
