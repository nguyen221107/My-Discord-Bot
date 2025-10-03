import discord
from discord.ext import commands
import os
import asyncio
import shutil
from yt_dlp import YoutubeDL
import json
import random
from discord.ext import tasks
from discord import app_commands
from discord import Embed
import subprocess
from datetime import datetime, timedelta


intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents = discord.Intents.default()
intents.message_content = True  # Cần nếu bot đọc nội dung tin nhắn

SAVE_DIR = "files"
os.makedirs(SAVE_DIR, exist_ok=True)

playlists = {}

now_playing: dict[int, dict[str, str]] = {}

if os.path.exists("playlists.json"):
    with open("playlists.json", "r", encoding="utf-8") as f:
        playlists = json.load(f)

# Ghi ra file
with open("playlists.json", "w", encoding="utf-8") as f:
    json.dump(playlists, f, ensure_ascii=False, indent=4)

# Đọc lại khi khởi động bot
try:
    with open("playlists.json", "r", encoding="utf-8") as f:
        playlists = json.load(f)
except FileNotFoundError:
    playlists = {}


# Helper để lấy danh sách file MP3 đã lưu
def get_mp3_list():
    return [f for f in os.listdir(SAVE_DIR) if f.endswith(".mp3")]


class MyBot(commands.Bot):

    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands đã được đồng bộ!")


bot = MyBot()

# ========================== EVENTS ===========================


@bot.event
async def on_ready():
    print(f"🚀 Bot đã sẵn sàng: {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user or not message.attachments:
        return

    for attachment in message.attachments:
        if attachment.filename.endswith(".mp3"):

            class SaveOrNot(discord.ui.View):

                def __init__(self, filename):
                    super().__init__(timeout=60)
                    self.filename = filename

                @discord.ui.button(label="✅ Lưu",
                                   style=discord.ButtonStyle.success)
                async def save(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
                    path = os.path.join(SAVE_DIR, self.filename)
                    await attachment.save(path)
                    await interaction.response.send_message(
                        f"💾 Đã lưu `{self.filename}`", ephemeral=True)

                @discord.ui.button(label="❌ Không lưu",
                                   style=discord.ButtonStyle.danger)
                async def cancel(self, interaction: discord.Interaction,
                                 button: discord.ui.Button):
                    await interaction.response.send_message(
                        "🚫 Không lưu file.", ephemeral=True)

            view = SaveOrNot(attachment.filename)
            files = get_mp3_list()
            msg = "**🎵 File đã lưu:**\n" + "\n".join(
                files) if files else "📁 Chưa có file nào."
            await message.channel.send(
                f"📥 Bạn muốn lưu file `{attachment.filename}`?\n\n{msg}",
                view=view)


# ========================== SLASH COMMANDS ===========================


@bot.tree.command(name="list", description="📜 Hiển thị danh sách file đã lưu")
async def list_files(interaction: discord.Interaction):
    files = get_mp3_list()
    msg = "**🎵 Danh sách file đã lưu:**\n" + "\n".join(
        files) if files else "📁 Chưa có file nào được lưu."
    await interaction.response.send_message(msg)


@bot.tree.command(name="delete", description="🗑️ Xóa một file hoặc tất cả")
@discord.app_commands.describe(name="Tên file hoặc gõ 'all' để xóa tất cả")
async def delete_file(interaction: discord.Interaction, name: str):
    if name.lower() == "all":
        shutil.rmtree(SAVE_DIR)
        os.makedirs(SAVE_DIR)
        await interaction.response.send_message("🗑️ Đã xóa tất cả file.")
    else:
        path = os.path.join(SAVE_DIR, name)
        if os.path.exists(path):
            os.remove(path)
            await interaction.response.send_message(f"🗑️ Đã xóa `{name}`.")
        else:
            await interaction.response.send_message(
                f"❌ Không tìm thấy file `{name}`.")


@bot.tree.command(name="play", description="🎶 Phát một file nhạc MP3")
@discord.app_commands.describe(name="Tên file cần phát")
async def play_audio(interaction: discord.Interaction, name: str):
    path = os.path.join(SAVE_DIR, name)
    if not os.path.exists(path):
        await interaction.response.send_message("❌ File không tồn tại!")
        return

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "⚠️ Bạn cần vào voice channel trước!")
        return

    voice_channel = interaction.user.voice.channel
    vc = await voice_channel.connect()

    class AudioPlayer(discord.ui.View):

        def __init__(self, vc):
            super().__init__()
            self.vc = vc

        @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.primary)
        async def pause(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
            if self.vc.is_playing():
                self.vc.pause()
                await interaction.response.send_message("⏸ Đã dừng",
                                                        ephemeral=True)

        @discord.ui.button(label="▶️ Resume",
                           style=discord.ButtonStyle.success)
        async def resume(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
            if self.vc.is_paused():
                self.vc.resume()
                await interaction.response.send_message("▶️ Đã tiếp tục",
                                                        ephemeral=True)

        @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
        async def stop(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
            self.vc.stop()
            await interaction.response.send_message("⏹ Đã dừng phát",
                                                    ephemeral=True)
            await self.vc.disconnect()

    vc.play(discord.FFmpegPCMAudio(path, executable="ffmpeg"),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                vc.disconnect(), bot.loop))
    await interaction.response.send_message(f"🎶 Đang phát `{name}`",
                                            ephemeral=True,
                                            view=AudioPlayer(vc))


@bot.tree.command(name="clear", description="🧹 Xóa tin nhắn trong kênh")
@discord.app_commands.describe(arg="Nhập số lượng hoặc 'all'")
async def clear(interaction: discord.Interaction, arg: str):
    channel = interaction.channel
    if arg.lower() == "all":
        await interaction.response.send_message("💣 Đã xóa rất nhiều tin nhắn!",
                                                ephemeral=True)
        await channel.purge()
    elif arg.isdigit():
        amount = int(arg)
        await interaction.response.send_message(f"🧹 Đã xóa {amount} tin nhắn!",
                                                ephemeral=True)
        await channel.purge(limit=amount + 1)
    else:
        await interaction.response.send_message(
            "❌ Giá trị không hợp lệ! Dùng `/clear <số>` hoặc `/clear all`",
            ephemeral=True)


# ========================== YOUTUBE ===========================

song_queue = {}
# Lưu lại playlist gốc cho mỗi guild khi phát playlist
original_playlist = {}
loop_mode = {}  # key: guild_id, value: "off", "one", hoặc "all"


def get_audio_info(url):
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'forceurl': True,
        'default_search': 'ytsearch',
        'skip_download': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'url': info['url'],
            'title': info['title'],
            'page': info['webpage_url'],
            'thumbnail': info.get('thumbnail', '')
        }

def get_playlist_items(url, limit=None):
    opts = {
        'extract_flat': True,
        'quiet': True,
        'default_search': 'ytsearch',
        'skip_download': True,
    }
    with YoutubeDL(opts) as ydl:
        playlist = ydl.extract_info(url, download=False)
        entries = playlist.get('entries', [])
        urls = [entry['url'] for entry in entries]
        return urls[:limit] if limit else urls

# === 🎵 BACKGROUND TASK ===
async def process_playlist_background(gid, vc, inter, urls):
    song_queue.setdefault(gid, [])
    original_playlist[gid] = []

    for idx, url in enumerate(urls):
        try:
            info = await asyncio.to_thread(get_audio_info, url)
            original_playlist[gid].append(info)

            if not now_playing.get(gid):
                now_playing[gid] = info
                vc.play(discord.FFmpegPCMAudio(
                    info['url'],
                    executable='ffmpeg',
                    before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'),
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        play_next(gid, inter.channel), bot.loop))
                
                embed = Embed(title=f"🎶 Đang phát playlist: {info['title']}",
                              url=info['page'],
                              color=0x1DB954)
                embed.set_thumbnail(url=info['thumbnail'])

                # Gửi ephemeral embed + UI
                await inter.followup.send(embed=embed, view=YouTubeControls(vc, gid), ephemeral=True)

            else:
                song_queue[gid].append(info)
                if idx % 5 == 0:
                    await inter.followup.send(f"📥 Đã thêm {idx + 1}/{len(urls)} bài vào hàng đợi.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"⚠️ Lỗi khi xử lý bài số {idx + 1}: {e}", ephemeral=True)

        await asyncio.sleep(0.3)

    await inter.followup.send(f"✅ Đã xử lý xong **{len(urls)}** bài trong playlist!", ephemeral=True)


# === 🎧 Slash command playlist ===
@bot.tree.command(name="playlist", description="Phát playlist YouTube")
@discord.app_commands.describe(url="Link playlist YouTube")
async def playlist(inter: discord.Interaction, url: str):
    await inter.response.defer(ephemeral=True)

    if not inter.user.voice or not inter.user.voice.channel:
        return await inter.followup.send("⚠️ Bạn phải vào voice channel!", ephemeral=True)

    vc = discord.utils.get(bot.voice_clients, guild=inter.guild)
    if not vc:
        vc = await inter.user.voice.channel.connect()

    if not vc or not vc.is_connected():
        return await inter.followup.send("❌ Bot đã mất kết nối voice!", ephemeral=True)

    try:
        urls = await asyncio.to_thread(get_playlist_items, url)
    except Exception as e:
        return await inter.followup.send(f"❌ Không thể lấy playlist: {e}", ephemeral=True)

    await inter.followup.send(f"🔄 Đang xử lý playlist gồm **{len(urls)}** bài...", ephemeral=True)

    asyncio.create_task(process_playlist_background(
        inter.guild.id, vc, inter, urls))


# === 🔁 Phát bài tiếp theo trong hàng đợi ===
async def play_next(gid, channel):
    if not song_queue.get(gid):
        now_playing.pop(gid, None)
        return

    # Lấy mode loop
    mode = loop_mode.get(gid, "off")
    current_song = now_playing.get(gid)

    # Xử lý loop
    if mode == "one" and current_song:
        song_queue[gid].insert(0, current_song)
    elif mode == "all" and current_song:
        song_queue[gid].append(current_song)

    # Lấy bài kế tiếp
    if not song_queue[gid]:
        now_playing.pop(gid, None)
        return

    raw_info = song_queue[gid].pop(0)
    info = get_audio_info(raw_info['page'])  # Lấy lại URL hợp lệ
    now_playing[gid] = info

    vc = discord.utils.get(bot.voice_clients, guild__id=gid)
    vc.play(discord.FFmpegPCMAudio(
        info['url'],
        executable='ffmpeg',
        before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'),
        after=lambda e: asyncio.run_coroutine_threadsafe(
            play_next(gid, channel), bot.loop))

    embed = discord.Embed(title=f"🎶 Phát: {info['title']}",
                          url=info['page'],
                          color=0x1DB954)
    embed.set_thumbnail(url=info['thumbnail'])

    await channel.send(embed=embed)



# === 🔁 Bật/tắt chế độ lặp queue ===


@bot.tree.command(name="loop", description="Chọn chế độ lặp")
@app_commands.describe(
    mode="Chế độ lặp: one (1 bài), all (toàn queue), off (tắt)")
@app_commands.choices(mode=[
    app_commands.Choice(name="one", value="one"),
    app_commands.Choice(name="all", value="all"),
    app_commands.Choice(name="off", value="off")
])
async def loop(interaction: discord.Interaction,
               mode: app_commands.Choice[str]):
    gid = interaction.guild.id
    loop_mode[gid] = mode.value

    msg = {
        "one": "🔂 Đã bật **loop 1 bài**.",
        "all": "🔁 Đã bật **loop toàn queue**.",
        "off": "⏹️ Đã **tắt** loop."
    }
    await interaction.response.send_message(msg[mode.value], ephemeral=True)


# === 🔁 Kiểm tra trạng thái chế độ lặp ===


@bot.tree.command(name="loop_status", description="Xem chế độ lặp hiện tại")
async def loop_status(interaction: discord.Interaction):
    mode = loop_mode.get(interaction.guild.id, "off")
    msg = {
        "one": "🔂 Đang bật **loop 1 bài**.",
        "all": "🔁 Đang bật **loop toàn queue**.",
        "off": "⏹️ Loop đang **tắt**."
    }
    await interaction.response.send_message(msg[mode], ephemeral=True)


# === 🎛️ UI Điều khiển nhạc ===
loop_mode = {}  # dict lưu trạng thái loop theo guild: 'off', 'one', 'all'


class YouTubeControls(discord.ui.View):

    def __init__(self, vc: discord.VoiceClient, gid: int):
        super().__init__(timeout=None)
        self.vc = vc
        self.gid = gid

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.primary)
    async def skip(self, i: discord.Interaction, b: discord.ui.Button):
        self.vc.stop()
        now_playing.pop(self.gid, None)
        await i.response.send_message("⏭ Đã bỏ qua!", ephemeral=True)

    @discord.ui.button(label="🔁 Loop One", style=discord.ButtonStyle.success)
    async def loop_one(self, i: discord.Interaction, b: discord.ui.Button):
        loop_mode[self.gid] = "one"
        await i.response.send_message("🔁 Đã bật loop 1 bài!", ephemeral=True)

    @discord.ui.button(label="🔂 Loop All", style=discord.ButtonStyle.success)
    async def loop_all(self, i: discord.Interaction, b: discord.ui.Button):
        loop_mode[self.gid] = "all"
        await i.response.send_message("🔂 Đã bật loop toàn bộ hàng đợi!",
                                      ephemeral=True)

    @discord.ui.button(label="⏹ Loop Off", style=discord.ButtonStyle.danger)
    async def loop_off(self, i: discord.Interaction, b: discord.ui.Button):
        loop_mode[self.gid] = "off"
        await i.response.send_message("⏹ Đã tắt chế độ lặp!", ephemeral=True)

    @discord.ui.button(label="🔀 Shuffle", style=discord.ButtonStyle.secondary)
    async def shuffle(self, i: discord.Interaction, b: discord.ui.Button):
        if not song_queue.get(self.gid) or len(song_queue[self.gid]) < 2:
            return await i.response.send_message("📭 Không đủ bài để trộn!",
                                                 ephemeral=True)
        random.shuffle(song_queue[self.gid])
        await i.response.send_message("🔀 Đã trộn hàng đợi!", ephemeral=True)

    @discord.ui.button(label="📑 Queue", style=discord.ButtonStyle.secondary)
    async def queue(self, i: discord.Interaction, b: discord.ui.Button):
        if not song_queue.get(self.gid):
            return await i.response.send_message(
                "📭 Không có bài nào trong hàng đợi!", ephemeral=True)
        lines = [
            f"{i+1}. [{s['title']}]({s['page']})"
            for i, s in enumerate(song_queue[self.gid])
        ]
        await i.response.send_message("**🔜 Hàng đợi:**\n" + "\n".join(lines),
                                      ephemeral=True)

    @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.secondary)
    async def pause(self, i: discord.Interaction, b: discord.ui.Button):
        if self.vc.is_playing():
            self.vc.pause()
            await i.response.send_message("⏸ Đã tạm dừng!", ephemeral=True)
        else:
            await i.response.send_message("⚠️ Không có bài nào đang phát.",
                                          ephemeral=True)

    @discord.ui.button(label="▶️ Resume", style=discord.ButtonStyle.success)
    async def resume(self, i: discord.Interaction, b: discord.ui.Button):
        if self.vc.is_paused():
            self.vc.resume()
            await i.response.send_message("▶️ Tiếp tục!", ephemeral=True)
        else:
            await i.response.send_message("⚠️ Không có bài nào bị tạm dừng.",
                                          ephemeral=True)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, i: discord.Interaction, b: discord.ui.Button):
        try:
        # Kiểm tra nếu interaction chưa được respond
            if not i.response.is_done():
                await i.response.defer(ephemeral=True)
        
        # Thực hiện các thao tác dừng
            self.vc.stop()
            await self.vc.disconnect()
        
        # Gửi thông báo sau khi hoàn thành
            try:
                await i.followup.send("⏹ Đã ngắt kết nối!", ephemeral=True)
            except discord.errors.NotFound:
                print("Interaction đã hết hạn, không thể gửi thông báo")
            
        except Exception as e:
            print(f"Lỗi trong stop button: {e}")
            try:
                await i.followup.send(f"❌ Lỗi khi ngắt kết nối: {e}", ephemeral=True)
            except:
                pass  # Fallback nếu không thể gửi thông báo lỗi

    @discord.ui.button(label="▶️ Continue", style=discord.ButtonStyle.success)
    async def continue_playing(self, i: discord.Interaction,
                               b: discord.ui.Button):
        gid = self.gid
        if not song_queue.get(gid):
            return await i.response.send_message("📭 Hàng đợi đang trống!",
                                                 ephemeral=True)

        if not i.user.voice or not i.user.voice.channel:
            return await i.response.send_message(
                "⚠️ Bạn cần vào voice channel!", ephemeral=True)

        vc = discord.utils.get(bot.voice_clients, guild=i.guild)
        if not vc or not vc.is_connected():
            vc = await i.user.voice.channel.connect()

        if vc.is_playing() or vc.is_paused():
            return await i.response.send_message("⚠️ Đã có bài đang phát!",
                                                 ephemeral=True)

        first = song_queue[gid].pop(0)
        now_playing[gid] = first

        vc.play(discord.FFmpegPCMAudio(
            first['url'],
            executable='ffmpeg',
            before_options=
            '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'),
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    play_next(gid, i.channel), bot.loop))

        embed = discord.Embed(title=f"🎶 Tiếp tục phát: {first['title']}",
                              url=first['page'],
                              color=0x1DB954)
        embed.set_thumbnail(url=first['thumbnail'])
        await i.response.send_message(embed=embed,
                                      view=YouTubeControls(vc, gid),
                                      ephemeral=True)


# === 🔄 Gửi lại giao diện điều khiển ===
@bot.tree.command(name="resentui",
                  description="🔄 Gửi lại giao diện điều khiển bài đang phát")
async def resent_ui(inter: discord.Interaction):
    gid = inter.guild.id
    info = now_playing.get(gid)

    if not info:
        return await inter.response.send_message(
            "❌ Không có bài nào đang phát!", ephemeral=True)

    vc = discord.utils.get(bot.voice_clients, guild=inter.guild)
    if not vc or not vc.is_connected():
        return await inter.response.send_message(
            "⚠️ Bot không còn ở trong voice channel!", ephemeral=True)

    embed = discord.Embed(title=f"🎶 Đang phát: {info['title']}",
                          url=info['page'],
                          color=0x1DB954)
    embed.set_thumbnail(url=info['thumbnail'])

    await inter.response.send_message(embed=embed,
                                      view=YouTubeControls(vc, gid),
                                      ephemeral=True)


# === 🎧 Slash command phát bài ===
@bot.tree.command(name="playyoutube", description="Phát bài từ YouTube")
@discord.app_commands.describe(url="Link hoặc tên bài hát")
async def playyoutube(inter: discord.Interaction, url: str):
    await inter.response.defer(ephemeral=True)
    if not inter.user.voice or not inter.user.voice.channel:
        return await inter.followup.send("⚠️ Bạn phải vào voice channel!",
                                         ephemeral=True)

    vc = discord.utils.get(bot.voice_clients, guild=inter.guild)
    if not vc:
        vc = await inter.user.voice.channel.connect()

    gid = inter.guild.id
    song_queue.setdefault(gid, [])
    info = get_audio_info(url)
    chan = inter.channel

    if vc.is_playing() or vc.is_paused():
        song_queue[gid].append(info)
        return await inter.followup.send(
            f"📥 Đã thêm **{info['title']}** vào hàng đợi.", ephemeral=True)

    now_playing[gid] = {
        "title": info["title"],
        "url": info["url"],
        "page": info["page"],
        "thumbnail": info["thumbnail"]
    }

    vc.play(discord.FFmpegPCMAudio(
        info['url'],
        executable='ffmpeg',
        before_options=
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(gid, chan), bot.loop))
    embed = discord.Embed(title=f"🎶 Đang phát: {info['title']}",
                          url=info['page'],
                          color=0x1DB954)
    embed.set_thumbnail(url=info['thumbnail'])
    await inter.followup.send(embed=embed,
                              view=YouTubeControls(vc, gid),
                              ephemeral=True)


# === 📂 Lưu playlist ===
@bot.tree.command(name="addplaylist",
                  description="Lưu playlist đang phát vào tên đã chọn")
@discord.app_commands.describe(name="Tên playlist muốn lưu")
async def addplaylist(inter: discord.Interaction, name: str):
    gid = str(inter.guild.id)
    playlists.setdefault(gid, {})
    playlists[gid][name] = []

    # Bài đang phát → đặt thành phần tử đầu tiên
    queue = song_queue.get(inter.guild.id, []).copy()
    current = now_playing.get(inter.guild.id)
    if current:
        queue.insert(0, current)

    # Lưu playlist vào file
    playlists[gid][name].extend(queue)

    with open("playlists.json", "w", encoding="utf-8") as f:
        json.dump(playlists, f, ensure_ascii=False, indent=2)

    msg = f"✅ Đã lưu playlist **{name}** với {len(queue)} bài!"
    await inter.response.send_message(msg, ephemeral=True)


# === 📥 Thêm bài đang phát vào playlist ===
@bot.tree.command(name="addcurrenttoplaylist",
                  description="Thêm bài đang phát vào playlist")
@discord.app_commands.describe(name="Tên playlist muốn thêm bài vào")
async def addcurrenttoplaylist(inter: discord.Interaction, name: str):
    gid = str(inter.guild.id)
    vc = discord.utils.get(bot.voice_clients, guild=inter.guild)

    if not vc or not vc.is_playing():
        return await inter.response.send_message(
            "⚠️ Hiện tại không có bài nào đang phát!", ephemeral=True)

    current = now_playing.get(inter.guild.id)
    if not current:
        return await inter.response.send_message(
            "⚠️ Không lấy được thông tin bài đang phát!", ephemeral=True)

    playlists.setdefault(gid, {})
    playlists[gid].setdefault(name, [])

    playlists[gid][name].append(current)

    with open("playlists.json", "w", encoding="utf-8") as f:
        json.dump(playlists, f, ensure_ascii=False, indent=2)

    await inter.response.send_message(
        f"✅ Đã thêm bài **{current['title']}** vào playlist **{name}**!",
        ephemeral=True)


# === 🎶 Phát playlist đã lưu ===
@bot.tree.command(name="playplaylist", description="Phát playlist đã lưu")
@discord.app_commands.describe(name="Tên playlist đã lưu")
async def playplaylist(inter: discord.Interaction, name: str):
    await inter.response.defer(ephemeral=True)
    
    # Kiểm tra người dùng trong voice channel
    if not inter.user.voice or not inter.user.voice.channel:
        return await inter.followup.send("⚠️ Bạn phải vào voice channel!", ephemeral=True)

    gid = str(inter.guild.id)  # Chuyển sang string để phù hợp với cách lưu
    
    # Kiểm tra playlist tồn tại
    if gid not in playlists or name not in playlists[gid]:
        # Gợi ý các playlist tương tự nếu có
        suggestions = []
        if gid in playlists:
            suggestions = [n for n in playlists[gid].keys() if name.lower() in n.lower()]
        
        if suggestions:
            msg = f"❌ Không tìm thấy playlist '{name}'! Gợi ý:\n" + "\n".join(f"- {n}" for n in suggestions[:3])  # Giới hạn 3 gợi ý
        else:
            msg = f"❌ Không tìm thấy playlist '{name}'! Dùng `/listplaylist` để xem danh sách"
        
        return await inter.followup.send(msg, ephemeral=True)

    # Kết nối voice
    vc = discord.utils.get(bot.voice_clients, guild=inter.guild)
    if not vc:
        try:
            vc = await inter.user.voice.channel.connect()
        except Exception as e:
            return await inter.followup.send(f"❌ Lỗi khi kết nối voice: {str(e)}", ephemeral=True)

    # Lấy playlist và kiểm tra
    queue = playlists[gid][name]
    if not queue:
        return await inter.followup.send("❌ Playlist rỗng!", ephemeral=True)

    # Làm mới URL bài đầu tiên
    try:
        first = get_audio_info(queue[0]['page'])
        first['requester'] = inter.user  # Thêm người yêu cầu
    except Exception as e:
        return await inter.followup.send(f"❌ Lỗi khi tải bài đầu tiên: {str(e)}", ephemeral=True)

    # Thêm các bài còn lại vào hàng đợi
    song_queue.setdefault(inter.guild.id, [])
    for song in queue[1:]:
        try:
            new_song = song.copy()
            new_song['requester'] = inter.user
            song_queue[inter.guild.id].append(new_song)
        except Exception as e:
            print(f"Lỗi khi thêm bài vào hàng đợi: {str(e)}")
            continue

    now_playing[inter.guild.id] = first

    # Phát nhạc
    try:
        vc.play(discord.FFmpegPCMAudio(
            first['url'],
            executable='ffmpeg',
            before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(inter.guild.id, inter.channel), bot.loop))
    except Exception as e:
        return await inter.followup.send(f"❌ Lỗi khi phát nhạc: {str(e)}", ephemeral=True)

    # Gửi thông báo
    embed = discord.Embed(
        title=f"🎶 Đang phát playlist: {first['title']}",
        description=f"Playlist: {name} | {len(queue)} bài",
        url=first['page'],
        color=0x1DB954
    )
    embed.set_thumbnail(url=first['thumbnail'])
    embed.set_footer(text=f"Yêu cầu bởi {inter.user.display_name}", icon_url=inter.user.avatar.url)

    await inter.followup.send(embed=embed, view=YouTubeControls(vc, inter.guild.id), ephemeral=True)


# === 📂 Xem danh sách playlist đã lưu ===
@bot.tree.command(name="listplaylist",
                  description="Xem danh sách playlist đã lưu")
async def listplaylist(inter: discord.Interaction):
    gid = str(inter.guild.id)
    playlists.setdefault(gid, {})

    names = list(playlists[gid].keys())
    if not names:
        return await inter.response.send_message(
            "📭 Không có playlist nào được lưu!", ephemeral=True)

    msg = "\n".join(f"• {name} ({len(playlists[gid][name])} bài)"
                    for name in names)
    await inter.response.send_message(f"📂 Playlist đã lưu:\n{msg}",
                                      ephemeral=True)


# === 🗑️ Xoá playlist đã lưu ===
@bot.tree.command(name="removeplaylist", description="Xoá playlist đã lưu")
@discord.app_commands.describe(name="Tên playlist cần xoá")
async def removeplaylist(inter: discord.Interaction, name: str):
    gid = str(inter.guild.id)
    if gid not in playlists or name not in playlists[gid]:
        return await inter.response.send_message(
            "❌ Không tìm thấy playlist này!", ephemeral=True)

    del playlists[gid][name]

    with open("playlists.json", "w", encoding="utf-8") as f:
        json.dump(playlists, f, ensure_ascii=False, indent=2)

    await inter.response.send_message(f"🗑️ Đã xoá playlist **{name}**!",
                                      ephemeral=True)


# === 📑 Xem hàng đợi ===
@bot.tree.command(name="queue", description="Xem hàng đợi")
async def queue(inter: discord.Interaction):
    gid = inter.guild.id
    if not song_queue.get(gid):
        return await inter.response.send_message(
            "📭 Không có bài nào trong hàng đợi!", ephemeral=True)
    lines = [
        f"{i+1}. [{s['title']}]({s['page']})"
        for i, s in enumerate(song_queue[gid])
    ]
    await inter.response.send_message("**🔜 Hàng đợi:**\n" + "\n".join(lines),
                                      ephemeral=True)


# === 🗑️ Xóa hàng đợi ===
@bot.tree.command(name="delqueue", description="Xóa hàng đợi")
async def delqueue(inter: discord.Interaction):
    gid = inter.guild.id
    song_queue[gid] = []
    await inter.response.send_message("🧹 Đã xóa hàng đợi!", ephemeral=True)


# === 🔀 Trộn hàng đợi ===
@bot.tree.command(name="shuffle", description="Trộn hàng đợi")
async def shuffle(inter: discord.Interaction):
    gid = inter.guild.id
    if not song_queue.get(gid) or len(song_queue[gid]) < 2:
        return await inter.response.send_message("📭 Không đủ bài để trộn!",
                                                 ephemeral=True)
    random.shuffle(song_queue[gid])
    await inter.response.send_message("🔀 Đã trộn hàng đợi!", ephemeral=True)


# === ⏭ Bỏ qua bài hiện tại ===
@bot.tree.command(name="skip", description="Bỏ qua bài hiện tại")
async def skip(inter: discord.Interaction):
    gid = inter.guild.id
    vc = discord.utils.get(bot.voice_clients, guild__id=gid)
    if not vc or not vc.is_connected():
        return await inter.response.send_message("⚠️ Bot chưa kết nối voice!",
                                                 ephemeral=True)
    vc.stop()
    now_playing.pop(gid, None)
    await inter.response.send_message("⏭ Đã bỏ qua!", ephemeral=True)


# === 🔎 Tìm kiếm bài hát ===
@bot.tree.command(name="search",
                  description="🔎 Tìm bài hát trên YouTube và chọn để phát")
@discord.app_commands.describe(keyword="Từ khóa bài hát")
async def search(inter: discord.Interaction, keyword: str):
    await inter.response.defer(ephemeral=True)
    gid = inter.guild.id

    # 💡 Tìm 10 kết quả từ YouTube
    opts = {
        'format': 'bestaudio',
        'default_search': 'ytsearch4',  # 🔄 Từ 10 còn 4 kết quả
        'quiet': True,
        'skip_download': True
    }

    try:
        with YoutubeDL(opts) as ydl:
            results = ydl.extract_info(keyword, download=False)['entries']
    except Exception as e:
        return await inter.followup.send(f"❌ Lỗi khi tìm kiếm: `{str(e)}`",
                                         ephemeral=True)

    if not results:
        return await inter.followup.send("🚫 Không tìm thấy bài hát nào!",
                                         ephemeral=True)

    # 🎧 Hiện ra danh sách chọn bài
    class SongSelector(discord.ui.Select):

        def __init__(self, entries):
            self.entries = entries
            options = [
                discord.SelectOption(label=entry['title'][:100], value=str(i))
                for i, entry in enumerate(entries)
            ]
            super().__init__(placeholder="🎶 Chọn bài hát để phát",
                             options=options)

        async def callback(self, i: discord.Interaction):
            idx = int(self.values[0])
            chosen = self.entries[idx]

            if not i.user.voice or not i.user.voice.channel:
                return await i.response.send_message(
                    "⚠️ Bạn phải vào voice channel!", ephemeral=True)

            vc = discord.utils.get(bot.voice_clients, guild=i.guild)
            if not vc:
                vc = await i.user.voice.channel.connect()

            info = get_audio_info(chosen['url'])
            chan = i.channel
            song_queue.setdefault(gid, [])
            now_playing[gid] = info

            if vc.is_playing() or vc.is_paused():
                song_queue[gid].append(info)
                return await i.response.send_message(
                    f"📥 Đã thêm **{info['title']}** vào hàng đợi!")

            vc.play(discord.FFmpegPCMAudio(
                info['url'],
                executable='ffmpeg',
                before_options=
                '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'),
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        play_next(gid, chan), bot.loop))

            embed = discord.Embed(title=f"🎶 Đang phát: {info['title']}",
                                  url=info['page'],
                                  color=0x1DB954)
            embed.set_thumbnail(url=info['thumbnail'])

            # 🎛️ Thêm điều khiển vào UI
            view = YouTubeControls(vc, i.guild.id)
            await i.response.send_message(embed=embed,
                                          view=view,
                                          ephemeral=True)

    class ResultView(discord.ui.View):

        def __init__(self, entries):
            super().__init__(timeout=600)
            self.add_item(SongSelector(entries))

    await inter.followup.send("🔍 Kết quả tìm kiếm:",
                              view=ResultView(results),
                              ephemeral=True)


# ========================== CHAT ===========================


@bot.tree.command(name="say",
                  description="📢 Cho bot nói lại nội dung, có thể kèm ping")
@discord.app_commands.describe(message="Nội dung bạn muốn bot nói lại",
                               ping_user="(Tùy chọn) Thành viên bạn muốn ping")
async def say(inter: discord.Interaction,
              message: str,
              ping_user: discord.Member = None):
    await inter.response.defer(ephemeral=True)  # Ẩn xác nhận người gửi

    content = message
    if ping_user:
        content = f"{ping_user.mention} {message}"

    await inter.channel.send(content)
    await inter.followup.send("✅ Đã gửi!", ephemeral=True)


# ========================== PING COMMAND ===========================

@bot.tree.command(name="pingpp", description="Ping một người nhiều lần")
@discord.app_commands.describe(
    someone="Người bạn muốn ping",
    amount="Số lần ping (tối đa 10 lần)",
    delay="Thời gian giữa các lần ping (giây)"
)
async def pingpp(inter: discord.Interaction, 
                 someone: discord.Member, 
                 amount: int = 3, 
                 delay: float = 1.0):
    # Giới hạn số lần ping để tránh spam
    if amount > 10:
        amount = 10
    
    # Giới hạn thời gian delay
    if delay < 0.5:
        delay = 0.5
    elif delay > 5:
        delay = 5

    # Thông báo bắt đầu
    await inter.response.send_message(
        f"🔔 Sẽ ping {someone.mention} {amount} lần, mỗi lần cách nhau {delay} giây...",
        ephemeral=True
    )

    # Thực hiện ping nhiều lần
    for i in range(amount):
        # Tạo nội dung ping với số thứ tự
        content = f"{someone.mention} ({i+1}/{amount})"
        
        # Gửi ping
        await inter.channel.send(content)
        
        # Đợi trước khi ping lần tiếp theo
        if i < amount - 1:  # Không đợi sau lần cuối
            await asyncio.sleep(delay)
    
    # Thông báo hoàn thành
    await inter.followup.send("✅ Đã hoàn thành ping!", ephemeral=True)

# ========================== REWARDS ===========================

# ========================== REWARDS SYSTEM ===========================
class RewardsSystem:
    _instance = None
    is_running = False
    last_execution = None
    timeout_minutes = 5
    notification_channel = None  # Lưu kênh để gửi thông báo
    process = None  # Giữ process để có thể dừng

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RewardsSystem, cls).__new__(cls)
        return cls._instance

    @classmethod
    def can_execute(cls):
        if not cls.is_running:
            return True
        
        if cls.last_execution and (datetime.now() - cls.last_execution) > timedelta(minutes=cls.timeout_minutes):
            cls.is_running = False
            return True

        return False

    @classmethod
    async def stop_process(cls):
        if cls.process:
            try:
                cls.process.terminate()
                await asyncio.sleep(1)  # Đợi tiến trình phản hồi

                if cls.process.returncode is None:
                    cls.process.kill()  # Nếu vẫn chưa chết, kill hẳn
                await cls.process.wait()
            except Exception as e:
                print(f"[STOP ERROR] {e}")
        cls.is_running = False
        cls.process = None



# ========================== REWARDS COMMAND ===========================
@bot.tree.command(name="rewards", description="Chạy script Microsoft Rewards")
async def rewards(interaction: discord.Interaction):
    # Kiểm tra trạng thái
    if not RewardsSystem.can_execute():
        cooldown = RewardsSystem.last_execution + timedelta(minutes=RewardsSystem.timeout_minutes)
        remaining = cooldown - datetime.now()
        minutes = int(remaining.total_seconds() // 60)
        seconds = int(remaining.total_seconds() % 60)
        
        await interaction.response.send_message(
            f"⏳ Script đang chạy hoặc vừa chạy xong. Vui lòng đợi {minutes} phút {seconds} giây nữa.",
            ephemeral=True
        )
        return

    # Đánh dấu đang chạy
    RewardsSystem.is_running = True
    RewardsSystem.last_execution = datetime.now()
    
    await interaction.response.defer(ephemeral=True)
    
    async def execute_commands():
        WORKING_DIR = r"D:\Microsoft-Rewards-Script-main"
        
        try:
            # Thông báo bắt đầu (chỉ gửi cho người dùng)
            await interaction.followup.send("🔄 Đang bắt đầu chạy script...", ephemeral=True)
            
            # Chạy build
            build_process = await asyncio.create_subprocess_shell(
                "npm run build",
                cwd=WORKING_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await build_process.communicate()
            
            # Gửi kết quả build (chỉ cho người dùng)
            output = stdout.decode() + stderr.decode()
            if output.strip():
                await interaction.followup.send(f"📦 Build output:\n```{output[:1900]}```", ephemeral=True)
            
            # Chạy start
            RewardsSystem.process = await asyncio.create_subprocess_shell(
                "npm run start",
                cwd=WORKING_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Theo dõi output real-time (chỉ gửi cho người dùng)
            while True:
                line = await RewardsSystem.process.stdout.readline()
                if not line:
                    break
                    
                output = line.decode().strip()
                if output:
                    message_to_send = None

                    if "Completed tasks for account" in output:
                        email = output.split("account")[-1].strip()
                        message_to_send = f"✅ Hoàn thành tasks cho: {email}"
                    elif "error" in output.lower():
                        message_to_send = f"⚠️ Lỗi:\n```{output[:1900]}```"
                    else:
                        message_to_send = f"📝 Log: ```{output[:1900]}```"

                    try:
                        await interaction.followup.send(message_to_send, ephemeral=True)
                    except discord.HTTPException:
                        # Nếu không gửi được qua followup (do hết hạn hoặc lỗi), gửi qua channel
                        await interaction.channel.send(f"{message_to_send}")

            
            # Thông báo hoàn thành (chỉ cho người dùng)
            await interaction.followup.send("✅ Đã hoàn thành chạy script!", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Lỗi khi chạy script: {str(e)}",
                ephemeral=True
            )
        finally:
            RewardsSystem.is_running = False

    # Chạy trong background
    asyncio.create_task(execute_commands())

# ========================== STOP REWARDS ===========================
@bot.tree.command(name="stoprewards", description="Dừng tiến trình Microsoft Rewards đang chạy")
async def stop_rewards(interaction: discord.Interaction):
    if not RewardsSystem.is_running or RewardsSystem.process is None:
        await interaction.response.send_message("⚠️ Hiện tại không có tiến trình nào đang chạy.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        await RewardsSystem.stop_process()
        await interaction.followup.send("🛑 Đã dừng script Rewards.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Không thể dừng script: {str(e)}", ephemeral=True)


# ========================== TEST REWARDS ===========================
@bot.tree.command(name="testrewards", description="Chạy thử nghiệm script trong cửa sổ CMD riêng")
async def testrewards(interaction: discord.Interaction):
    WORKING_DIR = r"D:\Microsoft-Rewards-Script-main"
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Tạo file batch cải tiến
        batch_content = f"""@echo off
cd /d "{WORKING_DIR}"
echo [1/2] Đang chạy npm run build...
call npm run build
if %errorlevel% neq 0 (
    echo LỖI: Build thất bại với mã %errorlevel%
    pause
    exit /b
)
echo [2/2] Đang chạy npm run start...
call npm run start
if %errorlevel% neq 0 (
    echo LỖI: Start thất bại với mã %errorlevel%
    pause
    exit /b
)
echo HOÀN THÀNH: Tất cả tasks đã chạy xong
pause
"""
        
        batch_file = os.path.join(WORKING_DIR, "run_rewards.bat")
        
        with open(batch_file, "w", encoding="utf-8") as f:
            f.write(batch_content)
        
        # Chạy với cmd riêng biệt
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "cmd.exe", "/k", batch_file],
            shell=True
        )
        
        await interaction.followup.send(
            f"✅ Đã mở cửa sổ CMD mới\n"
            f"📂 Thư mục: {WORKING_DIR}\n"
            f"🔄 Đang chạy script...",
            ephemeral=True
        )
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Lỗi khi khởi chạy:\n```{str(e)}```",
            ephemeral=True
        )

# ========================== ADD ACCOUNT ===========================

ACCOUNTS_FILE = r"D:\Microsoft-Rewards-Script-main\src\accounts.json"

@bot.tree.command(name="addaccount", description="Thêm tài khoản vào file accounts.json")
@app_commands.describe(
    email="Email tài khoản", 
    password="Mật khẩu",
    proxy_url="Proxy URL (tuỳ chọn)",
    proxy_port="Proxy port (tuỳ chọn, dạng số)",
    proxy_username="Proxy username (tuỳ chọn)",
    proxy_password="Proxy password (tuỳ chọn)"
)
async def addaccount(
    interaction: discord.Interaction,
    email: str, 
    password: str,
    proxy_url: str = "", 
    proxy_port: int = 0, 
    proxy_username: str = "", 
    proxy_password: str = ""
):
    await interaction.response.defer(ephemeral=True)
    try:
        # Đảm bảo file tồn tại
        if not os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=4)

        # Đọc dữ liệu hiện tại
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)

        # Tạo đối tượng tài khoản
        account = {
            "email": email,
            "password": password,
            "proxy": {
                "proxyAxios": True,
                "url": proxy_url or "",
                "port": proxy_port or 0,
                "username": proxy_username or "",
                "password": proxy_password or ""
            }
        }


        # Thêm vào danh sách
        accounts.append(account)

        # Ghi lại file
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=4)

        await interaction.followup.send("✅ Tài khoản đã được thêm thành công!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

# ========================== LIST ACCOUNT ===========================
@bot.tree.command(name="listaccount", description="Hiển thị danh sách tài khoản")
async def listaccount(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        # Kiểm tra file tồn tại
        if not os.path.exists(ACCOUNTS_FILE):
            await interaction.followup.send("❌ Không tìm thấy file accounts.json", ephemeral=True)
            return

        # Đọc dữ liệu
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)

        # Tạo message hiển thị
        if not accounts:
            await interaction.followup.send("❌ Danh sách tài khoản trống", ephemeral=True)
            return

        message = "📋 Danh sách tài khoản:\n\n"
        for index, account in enumerate(accounts, start=1):
            message += f"{index}. {account['email']}\n"
            
            # Thêm thông tin proxy nếu có
            if account.get('proxy') and account['proxy'].get('url'):
                proxy = account['proxy']
                message += f"   🔹 Proxy: {proxy['url']}:{proxy['port']}"
                if proxy['username']:
                    message += f" (Auth: {proxy['username']})"
                message += "\n"

        await interaction.followup.send(message, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

# ========================== DELETE ACCOUNT ===========================
@bot.tree.command(name="delaccount", description="Xóa tài khoản theo số thứ tự")
@app_commands.describe(index="Số thứ tự tài khoản cần xóa")
async def delaccount(interaction: discord.Interaction, index: int):
    await interaction.response.defer(ephemeral=True)
    try:
        # Kiểm tra file tồn tại
        if not os.path.exists(ACCOUNTS_FILE):
            await interaction.followup.send("❌ Không tìm thấy file accounts.json", ephemeral=True)
            return

        # Đọc dữ liệu
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)

        # Kiểm tra index hợp lệ
        if index < 1 or index > len(accounts):
            await interaction.followup.send(f"❌ Số thứ tự không hợp lệ. Vui lòng chọn từ 1 đến {len(accounts)}", ephemeral=True)
            return

        # Xóa tài khoản
        deleted_account = accounts.pop(index - 1)

        # Ghi lại file
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=4)

        await interaction.followup.send(f"✅ Đã xóa tài khoản {index}: {deleted_account['email']}", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

# ========================== CHẠY BOT ===========================


with open("token.txt") as f:
    TOKEN = f.read().strip()

bot.run(TOKEN)
