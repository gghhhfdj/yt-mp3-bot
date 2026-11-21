#!/usr/bin/env python3
"""YouTube -> আসল MP3 Telegram Bot — Koyeb ফ্রি Nano-তে চলে (Cobalt ছাড়া)
yt-dlp + ffmpeg দিয়ে সত্যিকারের .mp3 (192kbps) বানায়, Telegram-এ পাঠায়।
Koyeb ফ্রি: 1 সার্ভিস, 512MB RAM, ঘুমায় না, কার্ড লাগে না।
Env: BOT_TOKEN (BotFather টোকেন), MAX_MINUTES=20 (ঐচ্ছিক)
"""
import os, re, asyncio, tempfile, logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ytmp3bot")
TOKEN = os.environ["BOT_TOKEN"]
MAX_MINUTES = int(os.environ.get("MAX_MINUTES", "20"))
MAX_BYTES = 48 * 1024 * 1024  # Telegram সীমা 50MB, নিরাপত্তায় 48MB

YT_RE = re.compile(r"(?:youtube\.com/(?:watch\?[^ ]*v=|shorts/|embed/|v/)|youtu\.be/|music\.youtube\.com/watch\?[^ ]*v=)([A-Za-z0-9_-]{11})")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 YouTube MP3 বট\n\nYouTube মিউজিক ভিডিওর লিংক পাঠাও, আমি আসল MP3 (192kbps) বানিয়ে পাঠিয়ে দেবো।\n\nযেমন:\nhttps://www.youtube.com/watch?v=xxxxx\n\nসীমা: 20 মিনিট পর্যন্ত, 48MB পর্যন্ত।"
    )

async def handle_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    m = YT_RE.search(text)
    if not m:
        await update.message.reply_text("❌ এটা YouTube লিংক মনে হচ্ছে না। একটা YouTube ভিডিওর লিংক পাঠাও।")
        return
    url = f"https://www.youtube.com/watch?v={m.group(1)}"
    status = await update.message.reply_text("⏳ গানটা নামাচ্ছি আর MP3 বানাচ্ছি, একটু অপেক্ষা করো…")
    tmp = Path(tempfile.mkdtemp(prefix="ytmp3_"))
    try:
        def run_ydl():
            opts = {
                "format": "bestaudio/best",
                "outtmpl": str(tmp / "%(title).80s.%(ext)s"),
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
                "quiet": True, "no_warnings": True, "noplaylist": True,
                # YouTube বট-চেক এড়াতে Android ক্লায়েন্ট (ClipCut-এ প্রমাণিত)
                "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
                "http_headers": {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"},
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info
        info = await asyncio.to_thread(run_ydl)
        title = (info.get("title") or "song")[:100]
        duration = info.get("duration") or 0
        if duration > MAX_MINUTES * 60:
            await status.edit_text(f"⚠️ গানটা {duration//60} মিনিটের — {MAX_MINUTES} মিনিটের বেশি লম্বা গান পাঠানো যাবে না (Telegram 50MB সীমা)।")
            return
        mp3s = sorted(tmp.glob("*.mp3"))
        if not mp3s:
            await status.edit_text("❌ MP3 বানানো যায়নি। অন্য লিংক চেষ্টা করো।")
            return
        f = mp3s[0]
        if f.stat().st_size > MAX_BYTES:
            await status.edit_text("⚠️ MP3 ফাইল 48MB-এর বেশি — Telegram পাঠাতে পারবে না। ছোট গান চেষ্টা করো।")
            return
        await status.edit_text("📤 MP3 পাঠাচ্ছি…")
        await update.message.reply_audio(
            audio=f.open("rb"), filename=f.name, title=title,
            performer=(info.get("uploader") or "YouTube")[:100],
            caption=f"🎵 {title}",
        )
        await status.delete()
    except Exception as e:
        log.exception("failed %s", url)
        msg = str(e)
        if "403" in msg or "Forbidden" in msg:
            msg = "YouTube 403 দিয়েছে — কিছুক্ষণ পরে আবার চেষ্টা করো।"
        elif "Private" in msg or "unavailable" in msg.lower():
            msg = "ভিডিওটা প্রাইভেট বা পাওয়া যাচ্ছে না।"
        await status.edit_text(f"❌ হয়নি: {msg[:300]}")
    finally:
        for p in tmp.glob("*"):
            try: p.unlink()
            except Exception: pass
        try: tmp.rmdir()
        except Exception: pass

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    log.info("Bot starting (polling)…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
