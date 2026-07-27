import os
import re
import asyncio
import aiohttp
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault

API_ID = int(os.getenv("API_ID", 37089928))
API_HASH = os.getenv("API_HASH", "2a6ae5292824b4ba9c2cbb424529d5f0")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8902842486:AAGuCEWwDt-PMR4uSkkmZGN-l95QSbFWVmo")
GROUP_ID = int(os.getenv("GROUP_ID", -1004353229609))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "ghostxdown")

# استخدام bot token مباشرة بدون session file
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

pending_urls = {}
TIKTOK_REGEX = r'https?://\S*tiktok\.com\S*'

async def fetch_tiktok_data(url):
    api_url = "https://www.tikwm.com/api/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }
    data = {'url': url, 'hd': '1'}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, data=data, headers=headers, timeout=30) as response:
                result = await response.json()
                if result.get('code') == 0:
                    return {
                        'success': True,
                        'video_url': result['data']['play'],
                        'audio_url': result['data']['music'],
                        'title': result['data']['title'],
                        'author': result['data']['author']['nickname'],
                    }
                return {'success': False, 'error': 'فشل في جلب البيانات'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def download_file(url, filename):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                if response.status == 200:
                    with open(filename, 'wb') as f:
                        f.write(await response.read())
                    return True
                return False
    except:
        return False

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    is_joined = await check_user_joined(event.sender_id)
    if not is_joined:
        buttons = [[Button.url("📢 قناة التحديثات", f"https://t.me/{CHANNEL_USERNAME}")]]
        await event.respond("أنت غير مشترك بالقناة.\nيرجى الاشتراك ثم إرسال /start", buttons=buttons)
        return
    welcome_text = (
        "👋 أهلاً بك في بوت تحميل تيك توك\n\n"
        "🚀 أرسل أي رابط تيك توك وسأحمله لك كفيديو أو صوت"
    )
    await event.respond(welcome_text, link_preview=False)

@bot.on(events.NewMessage)
async def message_handler(event):
    if not event.text or event.text.startswith('/'):
        return
    match = re.search(TIKTOK_REGEX, event.text)
    if not match:
        return
    is_joined = await check_user_joined(event.sender_id)
    if not is_joined:
        buttons = [[Button.url("📢 قناة التحديثات", f"https://t.me/{CHANNEL_USERNAME}")]]
        await event.respond("أنت غير مشترك بالقناة.\nيرجى الاشتراك ثم أرسل الرابط", buttons=buttons)
        return
    tiktok_url = match.group(0).rstrip('.,!?;:')
    try:
        await event.react('')
    except:
        pass
    temp_msg = await event.respond("⏳ جاري جلب المعلومات...")
    data = await fetch_tiktok_data(tiktok_url)
    if not data['success']:
        await temp_msg.edit(f"❌ خطأ: {data['error']}")
        return
    pending_urls[temp_msg.id] = {'data': data, 'original_msg_id': event.id}
    buttons = [
        [Button.inline("🎬 فيديو", data=f"vid_{temp_msg.id}"),
         Button.inline("🎵 صوت", data=f"aud_{temp_msg.id}")]
    ]
    caption = f" {data['title'][:50]}...\n👤 {data['author']}\n\nاختر:"
    await temp_msg.edit(caption, buttons=buttons)

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    is_joined = await check_user_joined(event.sender_id)
    if not is_joined:
        await event.answer("️ يجب الاشتراك أولاً!", alert=True)
        return
    data = event.data.decode('utf-8')
    if data.startswith("vid_"):
        download_type = "video"
        msg_id = int(data.replace("vid_", ""))
        action_text = "🚀 جاري التحميل..."
    elif data.startswith("aud_"):
        download_type = "audio"
        msg_id = int(data.replace("aud_", ""))
        action_text = " جاري التحميل..."
    else:
        return
    saved_data = pending_urls.get(msg_id)
    if not saved_data:
        await event.answer("انتهت الصلاحية", alert=True)
        return
    tiktok_data = saved_data['data']
    original_msg_id = saved_data.get('original_msg_id')
    await event.edit(action_text)
    base_filename = f"tiktok_{event.sender_id}_{msg_id}"
    try:
        if download_type == "video":
            filename = f"{base_filename}.mp4"
            url = tiktok_data['video_url']
            caption = f"🎬 {tiktok_data['title'][:50]}...\n👤 {tiktok_data['author']}"
        else:
            filename = f"{base_filename}.mp3"
            url = tiktok_data['audio_url']
            caption = f"🎵 {tiktok_data['title'][:50]}...\n👤 {tiktok_data['author']}"
        if await download_file(url, filename):
            await event.edit("📤 جاري الرفع...")
            if download_type == "audio":
                await bot.send_file(event.chat_id, filename, voice=True, caption=caption)
            else:
                await bot.send_file(event.chat_id, filename, caption=caption)
            await event.delete()
            if original_msg_id:
                try:
                    await bot.delete_messages(event.chat_id, [original_msg_id])
                except:
                    pass
        else:
            await event.edit("❌ فشل التحميل")
    except Exception as e:
        await event.edit(f"❌ خطأ: {str(e)[:100]}")
    finally:
        pending_urls.pop(msg_id, None)
        for ext in ['mp4', 'mp3']:
            f = f"{base_filename}.{ext}"
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

async def check_user_joined(user_id):
    try:
        await bot(GetParticipantRequest(channel=GROUP_ID, participant=user_id))
        return True
    except:
        return True

async def set_commands():
    try:
        await bot(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='ar',
            commands=[BotCommand(command='start', description='بدء البوت 🚀')]
        ))
        print("✅ تم تفعيل الأوامر")
    except:
        pass

if __name__ == "__main__":
    print("🚀 البوت يعمل!")
    bot.loop.run_until_complete(set_commands())
    bot.run_until_disconnected()
