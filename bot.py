# -*- coding: utf-8 -*-
"""
بوت تليجرام لصناع المحتوى التاريخي بالعامية المصرية
- يكتب سكريبتات كلامية صرفة للمحتوى بدون أي كلام عن الموسيقى أو المونتاج
- مفتوح بالكامل: تقدر تسأله عن أي حاجة في التاريخ يجاوبك ويدردش معاك
- لما تقوله اكتبلي سكريبت عن كذا يكتبهولك فوراً
- كلمة 'جديد' تجيبلك فكرة حصرية مختلفة تماماً عن اللي فات بدون تكرار
"""

import sys
import os
import io
import re
import tempfile
import logging
from typing import Optional
from dotenv import load_dotenv

# ضبط التشفير للكونسول في ويندوز لمنع كراش الحروف العربية والإيموجي
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import database
import script_generator
import voice_narrator

load_dotenv()

# إعداد اللوجينج
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# الكيبورد الدائم
MAIN_KEYBOARD = [
    [KeyboardButton("🆕 اسكريبت تاريخي جديد"), KeyboardButton("📜 تلقين للشاشة 🎬")],
    [
        KeyboardButton("🏺 أسرار الفراعنة"),
        KeyboardButton("⚔️ معارك وحروب"),
        KeyboardButton("🎲 فكرة تاريخية غريبة"),
    ],
    [KeyboardButton("📜 مواضيعي السابقة"), KeyboardButton("ℹ️ طريقة الاستخدام")],
]
REPLY_MARKUP = ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True)


async def send_safe_message(
    update_or_message,
    text: str,
    reply_markup=None,
    parse_mode: Optional[str] = ParseMode.MARKDOWN,
):
    """إرسال الرسالة بأمان وتقسيمها إذا زادت عن 4000 حرف مع دعم الرجوع للنص العادي لتفادي الأخطاء"""
    max_len = 3900
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break
        split_idx = remaining.rfind("\n\n", 0, max_len)
        if split_idx == -1:
            split_idx = remaining.rfind("\n", 0, max_len)
        if split_idx == -1:
            split_idx = max_len
        chunks.append(remaining[:split_idx])
        remaining = remaining[split_idx:].strip()

    messages_sent = []
    for i, chunk in enumerate(chunks):
        current_markup = reply_markup if i == len(chunks) - 1 else None
        reply_fn = getattr(update_or_message, "reply_text", None)
        if reply_fn is None and hasattr(update_or_message, "message"):
            reply_fn = update_or_message.message.reply_text

        try:
            msg = await reply_fn(
                chunk,
                parse_mode=parse_mode,
                reply_markup=current_markup,
                disable_web_page_preview=True,
            )
            messages_sent.append(msg)
        except Exception:
            try:
                msg = await reply_fn(
                    chunk,
                    parse_mode=None,
                    reply_markup=current_markup,
                    disable_web_page_preview=True,
                )
                messages_sent.append(msg)
            except Exception:
                pass

    return messages_sent


def sanitize_filename(name: str) -> str:
    """تنظيف اسم الملف ليكون مناسباً للحفظ على الويندوز وأنظمة التشغيل بدون أخطاء"""
    clean = re.sub(r'[\\/*?:"<>|#📌🏛️🎬]', "", name)
    clean = clean.replace(" ", "_").strip("_")
    return clean[:45] or "history_script"


def save_script_to_local_file(script_text: str, title: str) -> str:
    """حفظ الاسكريبت كملف نصي محلي على الجهاز في مجلد saved_scripts"""
    save_dir = os.path.join(os.path.dirname(__file__), "saved_scripts")
    try:
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{sanitize_filename(title)}.txt"
        filepath = os.path.join(save_dir, filename)
        with open(filepath, "w", encoding="utf-8-sig") as f:
            f.write(f"📌 {title}\n\n{script_text}\n")
        return filepath
    except Exception as e:
        logger.warning(f"تعذر حفظ الملف المحلي: {e}")
        return ""


async def send_script_as_txt(
    update_or_message,
    script_text: str,
    title: str,
    caption_prefix: str = "📄 *ملف الاسكريبت جاهز للحفظ (TXT):*",
) -> None:
    """إرسال الاسكريبت كملف TXT عبر التليجرام مع حفظ نسخة محلية على الكمبيوتر"""
    local_path = save_script_to_local_file(script_text, title)
    filename = os.path.basename(local_path) if local_path else f"{sanitize_filename(title)}.txt"

    file_bytes = io.BytesIO(f"📌 {title}\n\n{script_text}\n".encode("utf-8-sig"))
    file_bytes.name = filename

    reply_fn = getattr(update_or_message, "reply_document", None)
    if reply_fn is None and hasattr(update_or_message, "message"):
        reply_fn = update_or_message.message.reply_document

    caption = (
        f"{caption_prefix}\n"
        f"📌 *{title}*\n\n"
        f"💾 تم حفظ نسخة تلقائياً على جهازك في مجلد `saved_scripts`، وتقدر تحمله هنا فوراً!"
    )

    try:
        await reply_fn(
            document=file_bytes,
            filename=filename,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        await reply_fn(
            document=file_bytes,
            filename=filename,
            caption=f"ملف الاسكريبت: {title}",
        )


def clean_script_from_message(text: str) -> str:
    """تنظيف الرسالة من ترويسات البوت الترحيبية واستخلاص نص القصة الصافي"""
    lines = text.split("\n")
    cleaned_lines = []
    skip_intro = True
    for line in lines:
        stripped = line.strip()
        if skip_intro and (
            stripped.startswith("🎬 *اسكريبت")
            or stripped.startswith("📜 *اسكريبت")
            or stripped.startswith("📜 *سكريبت")
            or stripped.startswith("✨ *نسخة")
            or stripped.startswith("🎬 *الاسكريبت جاهز")
        ):
            continue
        skip_intro = False
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def extract_script_from_reply(update: Update) -> Optional[dict]:
    """استخراج بيانات الاسكريبت المعني عندما يقوم المستخدم بعمل Reply على رسالة قصة سابقة"""
    if not update.message or not update.message.reply_to_message:
        return None

    reply_msg = update.message.reply_to_message
    user_id = update.effective_user.id

    # 1. إذا كانت الرسالة المردود عليها تحتوي على أزرار تفاعلية (فيها callback_data يحمل script_id)
    if reply_msg.reply_markup and hasattr(reply_msg.reply_markup, "inline_keyboard"):
        for row in reply_msg.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data:
                    m = re.search(r":(\d+)$", btn.callback_data)
                    if m:
                        script_id = int(m.group(1))
                        script_data = database.get_script_by_id(script_id)
                        if script_data:
                            # لو كانت نسخة تلقين سابقة، نجيب السكريبت الأساسي الكامل لمنع الاقتطاع التراكمي
                            base_data = database.get_base_script_for(script_data)
                            return base_data or script_data

    # 2. فحص النص في الرسالة المردود عليها والبحث عنه في قاعدة بيانات المستخدم
    reply_text = reply_msg.text or reply_msg.caption or ""
    if not reply_text.strip():
        return None

    # محاولة استخراج العنوان من الرسالة والبحث عنه
    extracted_title = None
    title_match = re.search(r"📌\s*(?:[^\n:]*[:\-]\s*)?(.*)", reply_text)
    if title_match and title_match.group(1).strip():
        extracted_title = title_match.group(1).split("\n")[0].strip().replace("*", "").replace("#", "").strip()

    # أخذ عينة نصية من قلب القصة للبحث بها في قاعدة البيانات
    snippet = None
    candidates = [
        l.strip()
        for l in reply_text.split("\n")
        if len(l.strip()) >= 15 and not l.startswith(("📌", "🪝", "🎬", "✨", "📜", "📖", "🤯", "🎯", "🏷️", "#"))
    ]
    if candidates:
        snippet = candidates[0][:60]

    found_script = database.find_script_by_title_or_snippet(user_id, title=extracted_title, snippet=snippet)
    if found_script:
        base_data = database.get_base_script_for(found_script)
        return base_data or found_script

    # 3. إذا لم تكن مسجلة في قاعدة البيانات (مثل نص قصة منسوخ أو مبعوث من المستخدم مباشرة)، نستخلص النص لتنسيقه
    cleaned_story = clean_script_from_message(reply_text)
    if len(cleaned_story.split()) >= 15:
        title = extracted_title or script_generator.extract_title(cleaned_story)
        if title == "قصة تاريخية مشوقة" and candidates:
            title = candidates[0][:35]
        return {
            "id": None,
            "user_id": user_id,
            "topic_title": title,
            "era_category": "ريبلاي مخصص",
            "script_text": cleaned_story,
            "format_type": "replied",
        }

    return None


# ==================== HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رسالة الترحيب مع صورة وهوية البوت"""
    welcome_msg = (
        "يا هلا بيك يا معلم! 🎬🏺\n\n"
        "أنا **رفيقك التاريخي وكاتب السكريبتات** بالعامية المصرية الصريحة!\n\n"
        "✨ **تقدر تعمل معايا أي حاجة:**\n"
        "1. ابعت كلمة **'جديد'** (أو اضغط `🆕 اسكريبت تاريخي جديد`) عشان أجبلك قصة نارية مش متكررة.\n"
        "2. قولي: **'اكتبلي سكريبت عن...'** لأي موضوع في بالك وهكتبهولك فوراً كلام صرف جاهز للتصوير من غير دوشة مونتاج وموسيقى!\n"
        "3. **اسألني عن أي حاجة في التاريخ** (مين بنى كذا؟ إيه سبب حرب كذا؟) وهجاوبك وندردش زي اتنين صحاب مؤرخين!\n\n"
        "👇 اضغط على الزراير أو اكتبلي أي حاجة في بالك:"
    )
    
    # إرسال صورة الهوية للبوت إن وجدت
    avatar_path = os.path.join(os.path.dirname(__file__), "bot_avatar.jpg")
    if os.path.exists(avatar_path):
        try:
            with open(avatar_path, "rb") as photo_file:
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=welcome_msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=REPLY_MARKUP,
                )
                return
        except Exception as e:
            logger.warning(f"تعذر إرسال صورة البوت: {e}")

    await update.message.reply_text(welcome_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=REPLY_MARKUP)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """المساعدة"""
    help_text = (
        "💡 *طريقة استخدام البوت:*\n\n"
        "• **عايز فكرة جديدة تماماً؟** اكتب `جديد` أو دوس `🆕 اسكريبت تاريخي جديد`.\n"
        "• **عايز سكريبت منسق ومختصر للشاشة والتسجيل؟** اكتب `تلقين` أو `سكربت منسق` (أو دوس `📜 تلقين للشاشة 🎬`) لتحويل آخر سكريبت لسطور قصيرة مع وقفات تنفس ⏸️.\n"
        "• **عايز سكريبت لموضوع معين؟** اكتب مثلاً: `اكتبلي سكريبت عن معركة حطين` أو `تلقين عن نابليون`.\n"
        "• **عايز تسأل عن أي معلومة أو تاريخ؟** اسألني في الشات علطول: `مين هو صلاح الدين؟` وهجاوبك فوراً!\n"
        "• **الإلقاء الصوتي:** اضغط على زرار `🎙️ اسمع الإلقاء الصوتي` لسماع النص بصوت راوي مصري.\n"
        "• **ريلز أو يوتيوب:** تقدر تختصر الاسكريبت لـ 60 ثانية أو توّسعه ليوتيوب من الزراير."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=REPLY_MARKUP)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض سجل المواضيع السابقة"""
    user_id = update.effective_user.id
    history = database.get_user_history(user_id, limit=20)
    total_count = database.count_user_scripts(user_id)

    if not history:
        await update.message.reply_text(
            "📜 لسه مفيش سكريبتات مسجلة يا صديقي! ابعت كلمة *'جديد'* عشان نبدأ! 🔥",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=REPLY_MARKUP,
        )
        return

    text = f"📜 *سجل مواضيعك السابقة ({total_count} سكريبت):*\n\n"
    for i, item in enumerate(history, 1):
        date_str = item["created_at"].split()[0] if "created_at" in item else ""
        text += f"{i}. 📌 *{item['topic_title']}* (📅 {date_str})\n"

    text += "\n🔒 *البوت بيستبعد المواضيع دي تلقائياً عند طلب جديد عشان ميحصلش أي تكرار.*"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=REPLY_MARKUP)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تصفير السجل"""
    user_id = update.effective_user.id
    database.clear_user_history(user_id)
    await update.message.reply_text("🔄 تم تصفير سجل مواضيعك بنجاح!", reply_markup=REPLY_MARKUP)


async def generate_and_send_new_script(
    update: Update, context: ContextTypes.DEFAULT_TYPE, era_preference: Optional[str] = None
):
    """توليد سكريبت جديد بدون تكرار وبدون توجيهات مونتاج"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    waiting_msg = await update.message.reply_text(
        "⏳ *بدورلك على قصة تاريخية جديدة ومثيرة ومحدش حكاها قبلك... ثواني يا فنان!* ☕",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        script_text, title, script_id = await script_generator.generate_new_history_script(
            user_id=user_id, era_preference=era_preference
        )

        try:
            await waiting_msg.delete()
        except Exception:
            pass

        inline_keyboard = [
            [InlineKeyboardButton("🔄 اسكريبت جديد تاني", callback_data="btn_new_script")],
            [
                InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{script_id}"),
                InlineKeyboardButton("📜 تلقين للشاشة 🎬", callback_data=f"format:teleprompter:{script_id}"),
                InlineKeyboardButton("📹 يوتيوب طويل (5m)", callback_data=f"format:youtube_long:{script_id}"),
            ],
            [
                InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{script_id}"),
                InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{script_id}"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)

        save_script_to_local_file(script_text, title)
        full_message = f"🎬 *اسكريبت جديد طازة للتصوير:*\n\n{script_text}"
        await send_safe_message(update, full_message, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"خطأ أثناء توليد السكريبت: {e}")
        try:
            await waiting_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(
            f"❌ حصل خطأ أثناء التوليد: {str(e)}\nحاول مرة تانية بعد ثواني يا صديقي.",
            reply_markup=REPLY_MARKUP,
        )


async def handle_custom_script_request(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str):
    """كتابة سكريبت لموضوع مخصص طلبه صانع المحتوى"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    waiting_msg = await update.message.reply_text(
        f"⏳ *بكتبلك سكريبت فيديو ممتع عن:* _{topic}_\n⚡ ثواني وهيكون جاهز بلسانك على طول!",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        script_text, title, script_id = await script_generator.generate_custom_topic_script(
            user_id=user_id, custom_topic=topic
        )

        try:
            await waiting_msg.delete()
        except Exception:
            pass

        inline_keyboard = [
            [InlineKeyboardButton("🔄 فكرة جديدة تانية", callback_data="btn_new_script")],
            [
                InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{script_id}"),
                InlineKeyboardButton("📜 تلقين للشاشة 🎬", callback_data=f"format:teleprompter:{script_id}"),
                InlineKeyboardButton("📹 يوتيوب طويل (5m)", callback_data=f"format:youtube_long:{script_id}"),
            ],
            [
                InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{script_id}"),
                InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{script_id}"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)

        save_script_to_local_file(script_text, title)
        full_message = f"🎬 *اسكريبتك جاهز يا فنان:*\n\n{script_text}"
        await send_safe_message(update, full_message, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"خطأ في السكريبت المخصص: {e}")
        try:
            await waiting_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"❌ حدث خطأ: {e}", reply_markup=REPLY_MARKUP)


async def handle_teleprompter_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    topic: Optional[str] = None,
    force_new: bool = False,
):
    """التعامل مع طلب سكريبت منسق أو تلقين (تحويل السابق أو توليد جديد أو بالـ Reply)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # 1. إذا كان المستخدم عامل Reply على رسالة قصة معينة
    replied_script = extract_script_from_reply(update) if not force_new else None
    if replied_script:
        title = replied_script["topic_title"]
        script_id = replied_script.get("id")
        waiting_msg = await update.message.reply_text(
            f"🎬 *جاري تنسيق القصة المحددة (الريبلاي) لنمط التلقين للشاشة:*\n📌 _{title}_\n⚡ بجهزها (جملتين في كل سطر) مع وقفات ⏸️ لتسجيل مريح وسلس...",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            if script_id:
                adapted_script, new_id = await script_generator.adapt_script_format(script_id, "teleprompter")
            else:
                adapted_script = script_generator.format_script_to_teleprompter(replied_script["script_text"])
                new_id = database.save_script(
                    user_id=user_id,
                    topic_title=f"{title} (تلقين)",
                    era_category=replied_script.get("era_category", "ريبلاي"),
                    script_text=adapted_script,
                    format_type="teleprompter",
                )

            save_script_to_local_file(adapted_script, f"{title} (تلقين)")
            try:
                await waiting_msg.delete()
            except Exception:
                pass

            inline_keyboard = [
                [InlineKeyboardButton("🔄 اسكريبت جديد كلياً", callback_data="btn_new_script")],
                [
                    InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{new_id}"),
                    InlineKeyboardButton("🎙️ اسمع الإلقاء الصوتي", callback_data=f"voice:{new_id}"),
                    InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{new_id}"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard)
            full_message = f"📜 *اسكريبت منسق للشاشة للقصة المختارة (نمط التلقين 🎬):*\n📌 *{title}*\n\n{adapted_script}"
            await send_safe_message(update, full_message, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"خطأ في تحويل سكريبت الريبلاي للتلقين: {e}")
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            await update.message.reply_text(f"❌ حدث خطأ أثناء التنسيق: {e}", reply_markup=REPLY_MARKUP)
        return

    # 2. إذا حدد موضوعاً مخصصاً (مثال: تلقين عن حرب أكتوبر)
    if topic and len(topic.strip()) >= 2:
        clean_topic = topic.strip()
        waiting_msg = await update.message.reply_text(
            f"🎬 *بجهزلك سكريبت منسق بنمط التلقين للشاشة عن:* _{clean_topic}_\n⚡ جملتين في كل سطر مع وقفات تنفس ⏸️ لتسجيل مريح وسلس...",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            script_text, title, script_id = await script_generator.generate_teleprompter_script(
                user_id=user_id, topic=clean_topic
            )
            try:
                await waiting_msg.delete()
            except Exception:
                pass

            inline_keyboard = [
                [InlineKeyboardButton("🔄 فكرة تلقين تانية", callback_data="btn_new_script")],
                [
                    InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{script_id}"),
                    InlineKeyboardButton("📹 يوتيوب طويل (5m)", callback_data=f"format:youtube_long:{script_id}"),
                ],
                [
                    InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{script_id}"),
                    InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{script_id}"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard)
            save_script_to_local_file(script_text, f"{title} (تلقين)")
            full_message = f"📜 *اسكريبت منسق للشاشة (نمط التلقين 🎬):*\n📌 *{title}*\n\n{script_text}"
            await send_safe_message(update, full_message, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"خطأ في سكريبت التلقين المخصص: {e}")
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            await update.message.reply_text(f"❌ حدث خطأ: {e}", reply_markup=REPLY_MARKUP)
        return

    # 3. إذا لم يحدد موضوعاً ولم يكن هناك Reply، نأخذ آخر سكريبت أساسي كامل
    last_script = database.get_last_base_script(user_id) if not force_new else None
    if last_script:
        script_id = last_script["id"]
        title = last_script["topic_title"]
        waiting_msg = await update.message.reply_text(
            f"🎬 *جاري تنسيق آخر سكريبت لنمط التلقين للشاشة:*\n📌 _{title}_\n⚡ بجهزه (جملتين في كل سطر) مع وقفات ⏸️ لتسجيل مريح وسلس...",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            adapted_script, new_id = await script_generator.adapt_script_format(script_id, "teleprompter")
            save_script_to_local_file(adapted_script, f"{title} (تلقين)")
            try:
                await waiting_msg.delete()
            except Exception:
                pass

            inline_keyboard = [
                [InlineKeyboardButton("🔄 اسكريبت جديد كلياً", callback_data="btn_new_script")],
                [
                    InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{new_id}"),
                    InlineKeyboardButton("🎙️ اسمع الإلقاء الصوتي", callback_data=f"voice:{new_id}"),
                    InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{new_id}"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard)
            full_message = f"📜 *سكريبت منسق للشاشة (نمط التلقين 🎬):*\n📌 *{title}*\n\n{adapted_script}"
            await send_safe_message(update, full_message, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"خطأ في تحويل السكريبت للتلقين: {e}")
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            await update.message.reply_text(f"❌ حدث خطأ أثناء التنسيق: {e}", reply_markup=REPLY_MARKUP)
        return

    # 3. إذا لم يوجد سكريبت سابق، نولد له سكريبت تلقين جديد طازة
    waiting_msg = await update.message.reply_text(
        "🎬 *بكتبلك اسكريبت جديد طازة منسق بالكامل للشاشة ونمط التلقين (جملتين في كل سطر + وقفات ⏸️)...*",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        script_text, title, script_id = await script_generator.generate_teleprompter_script(user_id=user_id)
        try:
            await waiting_msg.delete()
        except Exception:
            pass

        inline_keyboard = [
            [InlineKeyboardButton("🔄 اسكريبت جديد تاني", callback_data="btn_new_script")],
            [
                InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{script_id}"),
                InlineKeyboardButton("📹 يوتيوب طويل (5m)", callback_data=f"format:youtube_long:{script_id}"),
            ],
            [
                InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{script_id}"),
                InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{script_id}"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        save_script_to_local_file(script_text, f"{title} (تلقين)")
        full_message = f"📜 *اسكريبت منسق للشاشة (نمط التلقين 🎬):*\n\n{script_text}"
        await send_safe_message(update, full_message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"خطأ في توليد سكريبت التلقين: {e}")
        try:
            await waiting_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"❌ حدث خطأ أثناء التوليد: {e}", reply_markup=REPLY_MARKUP)


async def handle_general_history_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str):
    """الإجابة عن أي سؤال تاريخي عام في الشات المفتوح"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        answer = await script_generator.answer_history_question(user_id=user_id, question=question)

        # زر اختياري لتحويل الإجابة لاسكريبت فيديو بضغطة واحدة
        # نحفظ السؤال كـ callback data مختصر
        inline_keyboard = [
            [InlineKeyboardButton("🎬 اكتبلي سكريبت فيديو عن الموضوع ده", callback_data=f"makescript:{question[:50]}")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)

        await send_safe_message(update, answer, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"خطأ في الإجابة التاريخية: {e}")
        await update.message.reply_text(f"❌ حدث خطأ أثناء البحث: {e}", reply_markup=REPLY_MARKUP)

async def handle_voice_request_direct(update: Update, script_data: dict) -> None:
    """تسجيل وإرسال الإلقاء الصوتي لاسكريبت محدد (مثال: عند عمل Reply وطلب الصوت)"""
    title = script_data.get("topic_title", "اسكريبت تاريخي")
    script_text = script_data.get("script_text", "")
    waiting_msg = await update.message.reply_text(
        f"🎙️ *جاري تسجيل الصوت بالإلقاء المصري لـ:* _{title}_\nاستنى ثواني معدودة...",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        spoken_text = script_generator.clean_text_for_speech(script_text)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        await voice_narrator.synthesize_script_audio(spoken_text, tmp_path)
        try:
            await waiting_msg.delete()
        except Exception:
            pass

        with open(tmp_path, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=title,
                performer="راوي تاريخي مصري",
                caption=f"🎙️ **تسجيل صوتي لإلقاء الاسكريبت:**\n📌 {title}\n\n💡 اسمع النبرة ومخارج الحروف واستخدمها في تصويرك!",
                parse_mode=ParseMode.MARKDOWN,
            )
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"خطأ في تسجيل الصوت: {e}")
        try:
            await waiting_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"❌ تعذر تسجيل الصوت: {e}")


async def handle_format_adaptation_direct(update: Update, script_id: int, target_format: str) -> None:
    """تحويل الاسكريبت المردود عليه إلى صيغة ريلز أو يوتيوب وإرساله فوراً"""
    if target_format == "reels_60s":
        label = "ريلز سريع (60 ثانية)"
    elif target_format == "teleprompter":
        label = "وضع التلقين للشاشة (Teleprompter)"
    else:
        label = "يوتيوب مفصل (5 دقائق)"

    waiting_msg = await update.message.reply_text(f"⏳ جاري تجهيز نسخة {label} للقصة المختارة كلام صافي...")
    try:
        adapted_script, new_id = await script_generator.adapt_script_format(script_id, target_format)
        save_script_to_local_file(adapted_script, f"script_{new_id}_{label}")
        try:
            await waiting_msg.delete()
        except Exception:
            pass

        inline_keyboard = [
            [InlineKeyboardButton("🔄 اسكريبت جديد كلياً", callback_data="btn_new_script")],
            [
                InlineKeyboardButton("📜 وضع التلقين للشاشة", callback_data=f"format:teleprompter:{new_id}"),
                InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{new_id}"),
                InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{new_id}"),
            ],
        ]
        await send_safe_message(
            update,
            f"✨ *نسخة {label}:*\n\n{adapted_script}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard),
        )
    except Exception as e:
        try:
            await waiting_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"❌ تعذر تغيير التنسيق: {e}")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة جميع الرسائل النصية بمرونة وذكاء فائق"""
    text = update.message.text.strip()
    clean_text = text.lower()

    # 1. طلب جديد
    is_new = (
        clean_text == "جديد"
        or clean_text in ["جديد يا باشا", "جديد يا معلم", "هات جديد", "اسكريبت جديد", "موضوع جديد"]
        or "🆕 اسكريبت تاريخي جديد" in text
        or "🎲 فكرة تاريخية غريبة" in text
    )
    if is_new:
        await generate_and_send_new_script(update, context)
        return

    # 2. أزرار التصنيفات
    if "🏺 أسرار الفراعنة" in text:
        await generate_and_send_new_script(update, context, era_preference="أسرار الفراعنة ومصر القديمة والمومياوات واللعنات")
        return

    if "⚔️ معارك وحروب" in text:
        await generate_and_send_new_script(update, context, era_preference="أغرب المعارك والحروب في التاريخ والخطط الحربية الماكرة")
        return

    if "🕵️‍♂️ خفايا وجواسيس" in text:
        await generate_and_send_new_script(update, context, era_preference="أخطر عمليات الجاسوسية والمخابرات والاغتيالات التاريخية")
        return

    if "📜 مواضيعي السابقة" in text:
        await history_command(update, context)
        return

    if "ℹ️ طريقة الاستخدام" in text:
        await help_command(update, context)
        return

    # 3. الرد على التحيات والترحيب الودي
    greetings = ["ازيك", "عامل ايه", "صباح الخير", "مساء الخير", "سلام عليكم", "السلام عليكم", "يا هلا", "اهلا", "أهلا", "مرحبا", "هاي", "hello", "hi", "شكرا", "تسلم", "حبيبي", "عاش", "تمام", "يا باشا"]
    if clean_text in greetings:
        await update.message.reply_text(
            "يا هلا بيك يا معلم! نورتني دائماً 🎬🏺\n\n"
            "جاهز في أي لحظة.. تحب نكتب اسكريبت عن إيه النهاردة؟ أو ابعت كلمة **'جديد'** أو **'تلقين'** وهظبطك فوراً! 🔥",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=REPLY_MARKUP,
        )
        return

    # 4. فحص طلبات التلقين والسكريبت المنسق للشاشة
    tele_standalone = [
        "تلقين", "ملقن", "منسق", "سكربت منسق", "سكريبت منسق", "اسكريبت منسق", 
        "اسكربت منسق", "وضع التلقين", "نمط التلقين", "تلقين للشاشة", "تلقين شاشة", 
        "نسق الكلام", "نسق الاسكريبت", "نسق السكربت", "عايز تلقين", "هات تلقين", 
        "سكريبت تلقين", "سكربت تلقين", "اسكريبت تلقين", "اسكربت تلقين", "تلقين يا باشا",
        "سكربت منسق يا باشا", "منسق يا باشا",
        "جملتين في السطر", "خليهم جملتين في السطر", "خليهم جملتين بالسطر", "جملتين بالسطر",
        "خليهم جملتين", "جملتين", "خليهم جملتين في السطر مش جمله", "جملتين في السطر مش جمله",
        "خليهم جملتين في السطر مش جملة", "جملتين في السطر مش جملة"
    ]
    is_tele_reply = (
        update.message.reply_to_message is not None
        and any(w in clean_text for w in ["تلقين", "ملقن", "منسق", "نسق", "جملتين", "شاشة", "اعمل ده", "خليه", "نسقه", "نسقلي", "تلقينها", "تلقين لده", "تلقين دي"])
    )
    if clean_text in tele_standalone or "📜 تلقين للشاشة 🎬" in text or clean_text.startswith("تلقين للشاشة") or "جملتين في السطر" in clean_text or is_tele_reply:
        await handle_teleprompter_request(update, context, topic=None)
        return

    # فحص طلب فكرة جديدة بنمط التلقين
    if clean_text in ["جديد تلقين", "تلقين جديد", "جديد منسق", "منسق جديد", "هات تلقين جديد"]:
        await handle_teleprompter_request(update, context, topic=None, force_new=True)
        return

    # فحص إذا كان يطلب كتابة سكريبت منسق أو تلقين عن موضوع محدد
    tele_patterns = [
        r"^(?:اكتبلي|اكتبي|اكتب|اعملي|اعمل|عايز|محتاج|هاتلي|هات|سوّيلي|سوي|احكيلي|احكي|قولي)?\s*(?:لي)?\s*(?:اسكريبت|سكريبت|سكربت|اسكربت|فيديو|قصة|حكاية|كلام)?\s*(?:منسق|تلقين|ملقن)\s*(?:عن|في|بخصوص|حول)?\s*(.*)$",
        r"^(?:تلقين|ملقن|منسق)\s*(?:عن|في|بخصوص|حول)\s*(.+)$",
    ]
    for pat in tele_patterns:
        match = re.match(pat, text, re.IGNORECASE)
        if match:
            topic = match.group(1).strip()
            topic = re.sub(r"^(?:عن|في|بخصوص|حول)\s+", "", topic).strip()
            if len(topic) >= 2:
                await handle_teleprompter_request(update, context, topic=topic)
                return
            else:
                await handle_teleprompter_request(update, context, topic=None)
                return

    # 5. فحص إذا كان رداً على رسالة اسكريبت لتحويله لريلز أو يوتيوب
    if update.message.reply_to_message is not None:
        if any(w in clean_text for w in ["ريلز", "60 ثانية", "دقيقة", "تيك توك", "شورتس", "قصير", "لخص"]):
            target_reels = extract_script_from_reply(update)
            if target_reels and target_reels.get("id"):
                await handle_format_adaptation_direct(update, target_reels["id"], "reels_60s")
                return
        elif any(w in clean_text for w in ["يوتيوب", "5 دقائق", "طويل", "مفصل", "حلقة", "وسع"]):
            target_yt = extract_script_from_reply(update)
            if target_yt and target_yt.get("id"):
                await handle_format_adaptation_direct(update, target_yt["id"], "youtube_long")
                return

    # 6. فحص إذا كان المستخدم يطلب كتابة سكريبت عن موضوع محدد (بأي صيغة عربية ممكنة)
    # أمثلة: "اكتبلي سكريبت عن كذا"، "اكتبي سكريبت عن كذا"، "اعملي سكريبت عن كذا"، "احكيلي عن كذا"، "عايز فيديو عن كذا"
    script_patterns = [
        r"^(?:اكتبلي|اكتبي|اكتب|اعملي|اعمل|عايز|محتاج|هاتلي|هات|سوّيلي|سوي|احكيلي|احكي|كلمنا|تكلم|قولي|قول)\s*(?:لي)?\s*(?:اسكريبت|سكريبت|فيديو|قصة|حكاية|موضوع)?\s*(?:عن|في|بخصوص|حول)?\s*(.+)$",
        r"^(?:اسكريبت|سكريبت|فيديو|قصة|حكاية)\s*(?:عن|في|بخصوص|حول)?\s*(.+)$",
    ]
    
    for pat in script_patterns:
        match = re.match(pat, text, re.IGNORECASE)
        if match:
            topic = match.group(1).strip()
            topic = re.sub(r"^(?:عن|في|بخصوص|حول)\s+", "", topic).strip()
            if len(topic) >= 2:
                await handle_custom_script_request(update, context, topic=topic)
                return

    # فحص إضافي: لو الرسالة فيها كلمة "سكريبت" أو "اسكريبت" في أي مكان
    if "سكريبت" in clean_text or "اسكريبت" in clean_text:
        topic = re.sub(r"(?:اكتبلي|اكتبي|اكتب|اعملي|اعمل|عايز|محتاج|اسكريبت|سكريبت|عن|في|حول)", "", text).strip()
        if len(topic) >= 2:
            await handle_custom_script_request(update, context, topic=topic)
            return

    # 5. إذا كتب موضوعاً أو سؤالاً أو دردشة تاريخية عامة بدون أي قيود!
    await handle_general_history_question(update, context, question=text)


# ==================== CALLBACK QUERY (BUTTONS) ====================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة ضغطات الأزرار التفاعلية"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "btn_new_script":
        user_id = query.from_user.id
        waiting_msg = await query.message.reply_text("⏳ بدورلك على قصة تانية جديدة تماماً...")
        try:
            script_text, title, script_id = await script_generator.generate_new_history_script(user_id=user_id)
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            inline_keyboard = [
                [InlineKeyboardButton("🔄 اسكريبت جديد تاني", callback_data="btn_new_script")],
                [
                    InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{script_id}"),
                    InlineKeyboardButton("📜 تلقين للشاشة 🎬", callback_data=f"format:teleprompter:{script_id}"),
                    InlineKeyboardButton("📹 يوتيوب طويل (5m)", callback_data=f"format:youtube_long:{script_id}"),
                ],
                [
                    InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{script_id}"),
                    InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{script_id}"),
                ],
            ]
            save_script_to_local_file(script_text, title)
            await send_safe_message(
                query.message,
                f"🎬 *اسكريبت مختلف وجديد كلياً:*\n\n{script_text}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard),
            )
        except Exception as e:
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            await query.message.reply_text(f"❌ حدث خطأ: {e}")
        return

    if data.startswith("makescript:"):
        topic = data.split(":", 1)[1]
        user_id = query.from_user.id
        waiting_msg = await query.message.reply_text("⏳ بحولك الموضوع ده لاسكريبت فيديو جاهز للتصوير...")
        try:
            script_text, title, script_id = await script_generator.generate_custom_topic_script(user_id=user_id, custom_topic=topic)
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            inline_keyboard = [
                [InlineKeyboardButton("🔄 اسكريبت جديد", callback_data="btn_new_script")],
                [
                    InlineKeyboardButton("⏱️ ريلز سريع (60s)", callback_data=f"format:reels_60s:{script_id}"),
                    InlineKeyboardButton("📜 تلقين للشاشة 🎬", callback_data=f"format:teleprompter:{script_id}"),
                    InlineKeyboardButton("📹 يوتيوب طويل (5m)", callback_data=f"format:youtube_long:{script_id}"),
                ],
                [
                    InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{script_id}"),
                    InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{script_id}"),
                ],
            ]
            save_script_to_local_file(script_text, title)
            await send_safe_message(
                query.message,
                f"🎬 *الاسكريبت جاهز يا فنان:*\n\n{script_text}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard),
            )
        except Exception as e:
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            await query.message.reply_text(f"❌ خطأ: {e}")
        return

    if data.startswith("format:"):
        parts = data.split(":")
        target_format = parts[1]
        script_id = int(parts[2])

        if target_format == "reels_60s":
            label = "ريلز سريع (60 ثانية)"
        elif target_format == "teleprompter":
            label = "وضع التلقين للشاشة (Teleprompter)"
        else:
            label = "يوتيوب مفصل (5 دقائق)"

        waiting_msg = await query.message.reply_text(f"⏳ جاري تجهيز نسخة {label} كلام صافي بدون مونتاج وموسيقى...")

        try:
            adapted_script, new_id = await script_generator.adapt_script_format(script_id, target_format)
            save_script_to_local_file(adapted_script, f"script_{new_id}_{label}")
            try:
                await waiting_msg.delete()
            except Exception:
                pass

            inline_keyboard = [
                [InlineKeyboardButton("🔄 اسكريبت جديد كلياً", callback_data="btn_new_script")],
                [
                    InlineKeyboardButton("📜 وضع التلقين للشاشة", callback_data=f"format:teleprompter:{new_id}"),
                    InlineKeyboardButton("🎙️ الإلقاء الصوتي", callback_data=f"voice:{new_id}"),
                    InlineKeyboardButton("📄 تحميل ملف TXT", callback_data=f"download_txt:{new_id}"),
                ],
            ]
            await send_safe_message(
                query.message,
                f"✨ *نسخة {label}:*\n\n{adapted_script}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard),
            )
        except Exception as e:
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            await query.message.reply_text(f"❌ تعذر تغيير التنسيق: {e}")
        return

    if data.startswith("download_txt:"):
        script_id = int(data.split(":")[1])
        script_data = database.get_script_by_id(script_id)
        if not script_data:
            await query.message.reply_text("❌ لم يتم العثور على الاسكريبت في قاعدة البيانات!")
            return

        try:
            await send_script_as_txt(
                query.message,
                script_text=script_data["script_text"],
                title=script_data["topic_title"],
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال ملف TXT: {e}")
            await query.message.reply_text(f"❌ تعذر إرسال الملف: {e}")
        return

    if data.startswith("voice:"):
        script_id = int(data.split(":")[1])
        script_data = database.get_script_by_id(script_id)
        if not script_data:
            await query.message.reply_text("❌ لم يتم العثور على الاسكريبت!")
            return

        waiting_msg = await query.message.reply_text("🎙️ *جاري تسجيل الصوت بالإلقاء المصري... استنى ثواني معدودة!*", parse_mode=ParseMode.MARKDOWN)

        try:
            spoken_text = script_generator.clean_text_for_speech(script_data["script_text"])
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_path = tmp_file.name

            await voice_narrator.synthesize_script_audio(spoken_text, tmp_path)
            try:
                await waiting_msg.delete()
            except Exception:
                pass

            with open(tmp_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    title=f"{script_data['topic_title']}",
                    performer="راوي تاريخي مصري",
                    caption=f"🎙️ **تسجيل صوتي لإلقاء الاسكريبت:**\n📌 {script_data['topic_title']}\n\n💡 اسمع النبرة ومخارج الحروف واستخدمها في تصويرك!",
                    parse_mode=ParseMode.MARKDOWN,
                )

            try:
                os.remove(tmp_path)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"خطأ في الصوت: {e}")
            try:
                await waiting_msg.delete()
            except Exception:
                pass
            await query.message.reply_text(f"❌ تعذر تسجيل الصوت: {e}")
        return


import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Bot is running 24/7!".encode("utf-8"))

    def log_message(self, format, *args):
        pass

def run_health_server(port: int):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Health server error: {e}")


def create_telegram_application():
    """بناء وتجهيز كائن Application وتعيين كل المعالجات عليه (يدعم الـ Polling والـ Webhook)"""
    is_pa = "PYTHONANYWHERE_DOMAIN" in os.environ or os.path.exists("/etc/pythonanywhere")
    proxy_env = os.getenv("http_proxy") or os.getenv("https_proxy")
    if is_pa or proxy_env:
        from telegram.request import HTTPXRequest
        proxy_url = proxy_env or "http://proxy.server:3128"
        req = HTTPXRequest(
            proxy_url=proxy_url,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
        )
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(req).build()
        logger.info(f"Using proxy: {proxy_url}")
    else:
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", lambda u, c: generate_and_send_new_script(u, c)))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    return app


# ==================== MAIN ====================

def main() -> None:
    """تشغيل البوت"""
    print("=" * 60)
    print("🏺 بوت السكريبتات التاريخية والشات المفتوح لصانع المحتوى 🎬")
    print("=" * 60)

    if not TELEGRAM_BOT_TOKEN or "ضع_توكن" in TELEGRAM_BOT_TOKEN:
        print("❌ خطأ: TELEGRAM_BOT_TOKEN غير محدد في ملف .env!")
        return

    # تشغيل خادم ويب خفيف للاستضافات السحابية عند وجود متغير PORT
    port_env = os.getenv("PORT")
    if port_env:
        try:
            port = int(port_env)
            t = threading.Thread(target=run_health_server, args=(port,), daemon=True)
            t.start()
            logger.info(f"Health server started on port {port}")
        except Exception as e:
            logger.warning(f"Could not start health server: {e}")

    print("🚀 البوت شغال الآن بنجاح ومفتوح لأي سؤال أو اسكريبت!")
    app = create_telegram_application()
    app.run_polling(poll_interval=2, timeout=10, allowed_updates=Update.ALL_TYPES)



if __name__ == "__main__":
    main()
