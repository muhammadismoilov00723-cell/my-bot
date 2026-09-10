import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import yt_dlp
from moviepy.editor import VideoFileClip

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8744392706:AAEQZwjML_5Sn5_Jt7tf7jBv4IuQQOsG_RQ"
ADMIN_ID = 51908858521

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

user_languages = {}
users_list = set()

TEXTS = {
    'uz': {
        'welcome': "👋 Assalomu alaykum! Botga xush kelibsiz.\n🌍 Iltimos, tilni tanlang:",
        'ask_link': "📥 Instagram video havolasini (link) yuboring:",
        'downloading': "⏳ Video yuklab olinyapti, iltimos kuting...",
        'error': "❌ Xatolik yuz berdi. Havola to'g'ri ekanligini tekshiring.",
        'music_recommend': "🎵 Videodagi musiqaga o'xshash TOP 10 ta qo'shiq tavsiyalari:\n(Eshitish uchun quyidagi raqamlarni bosing)",
        'admin_forward': "📣 Admindan yangi xabar:",
        'round_success': "⚪️ Videongiz dumaloq formatga o'tkazildi!"
    },
    'ru': {
        'welcome': "👋 Здравствуйте! Добро пожаловать в бот.\n🌍 Пожалуйста, выберите язык:",
        'ask_link': "📥 Отправьте ссылку на видео из Instagram:",
        'downloading': "⏳ Видео загружается, пожалуйста, подождите...",
        'error': "❌ Произошла ошибка. Проверьте правильность ссылки.",
        'music_recommend': "🎵 ТОП 10 похожих песен из этого видео:\n(Нажмите на цифры ниже, чтобы прослушать)",
        'admin_forward': "📣 Новое сообщение от админа:",
        'round_success': "⚪️ Ваше видео преобразовано в круглый формат!"
    },
    'en': {
        'welcome': "👋 Hello! Welcome to the bot.\n🌍 Please choose your language:",
        'ask_link': "📥 Send an Instagram video link:",
        'downloading': "⏳ Video is downloading, please wait...",
        'error': "❌ An error occurred. Please check if the link is correct.",
        'music_recommend': "🎵 TOP 10 similar songs from this video:\n(Click the numbers below to listen)",
        'admin_forward': "📣 New message from admin:",
        'round_success': "⚪️ Your video has been converted to round format!"
    }
}

class BotStates(StatesGroup):
    wait_admin_post = State()

@dp.message(F.from_user.id == ADMIN_ID)
async def admin_broadcast(message: types.Message):
    if message.text and message.text.startswith('/'):
        return
    
    sent_count = 0
    for user_id in users_list:
        try:
            await message.copy_to(chat_id=user_id)
            sent_count += 1
        except Exception:
            pass
    await message.reply(f"📢 Post {sent_count} ta obunachiga muvaffaqiyatli yuborildi! ✨")

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    users_list.add(message.from_user.id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇺🇸 English", callback_data="lang_en")
    builder.adjust(1)
    
    await message.answer(TEXTS['uz']['welcome'], reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang
    
    await callback.message.edit_text(TEXTS[lang]['ask_link'])
    await callback.answer()

def download_instagram_video(url: str, output_path: str = "video.mp4") -> bool:
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logging.error(f"YTDLP Error: {e}")
        return False

@dp.message(Command("raund"))
async def make_round_video(message: types.Message):
    lang = user_languages.get(message.from_user.id, 'uz')
    
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply("⚠️ Iltimos, ushbu buyruqni yuklab berilgan videoga reply (javob) qilib yozing! ⚪️")
        return
    
    status = await message.answer("🎬 Video qayta ishlanmoqda, kuting...")
    
    video_file = await bot.get_file(message.reply_to_message.video.file_id)
    input_path = "input_video.mp4"
    output_path = "round_video.mp4"
    await bot.download_file(video_file.file_path, input_path)
    
    try:
        clip = VideoFileClip(input_path)
        w, h = clip.size
        min_dim = min(w, h)
        cropped_clip = clip.crop(x_center=w/2, y_center=h/2, width=min_dim, height=min_dim)
        resized_clip = cropped_clip.resize(newsize=(360, 360))
        resized_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
        
        clip.close()
        cropped_clip.close()
        resized_clip.close()
        
        await bot.send_video_note(chat_id=message.chat.id, video_note=types.FSInputFile(output_path))
        await status.delete()
        
        os.remove(input_path)
        os.remove(output_path)
    except Exception as e:
        logging.error(f"Round error: {e}")
        await status.edit_text(TEXTS[lang]['error'])

@dp.message(F.text.contains("instagram.com"))
async def handle_instagram_links(message: types.Message):
    lang = user_languages.get(message.from_user.id, 'uz')
    url = message.text.strip()
    
    status_msg = await message.answer(TEXTS[lang]['downloading'])
    
    video_filename = f"vid_{message.from_user.id}.mp4"
    audio_filename = f"aud_{message.from_user.id}.mp3"
    
    success = download_instagram_video(url, video_filename)
    
    if success and os.path.exists(video_filename):
        try:
            await bot.send_video(chat_id=message.chat.id, video=types.FSInputFile(video_filename), caption="🎬 Yuklab olindi ✨")
            
            video_clip = VideoFileClip(video_filename)
            if video_clip.audio:
                video_clip.audio.write_audiofile(audio_filename, logger=None)
                video_clip.close()
                await bot.send_audio(chat_id=message.chat.id, audio=types.FSInputFile(audio_filename), caption="🎵 Videodagi musiqa 🔥")
                os.remove(audio_filename)
            else:
                video_clip.close()
            
            builder = InlineKeyboardBuilder()
            for i in range(1, 11):
                builder.button(text=f"🎵 {i}", callback_data=f"track_{i}")
            builder.adjust(5)
            
            await message.answer(TEXTS[lang]['music_recommend'], reply_markup=builder.as_markup())
            os.remove(video_filename)
            await status_msg.delete()
            
        except Exception as e:
            logging.error(f"Send error: {e}")
            await status_msg.edit_text(TEXTS[lang]['error'])
    else:
        await status_msg.edit_text(TEXTS[lang]['error'])

@dp.callback_query(F.data.startswith("track_"))
async def send_recommended_track(callback: types.CallbackQuery):
    track_num = callback.data.split("_")[1]
    await callback.message.answer(f"🎶 siz {track_num}-tavsiya etilgan qo'shiqni tanladingiz. ⚡️")
    await callback.answer()

async def main():
    print("🚀 Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
