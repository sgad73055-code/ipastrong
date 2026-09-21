import os
import logging
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import fitz  # PyMuPDF
from PIL import Image

# ========== الاعدادات ==========
BOT_TOKEN = os.getenv("BOT_TOKEN") or "ضع_توكنك_هنا"
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME") or "@ipastron"
CHANNEL_LINK = os.getenv("CHANNEL_LINK") or "https://t.me/ipastron"
# ==============================

logging.basicConfig(level=logging.INFO)
user_files = {}  # user_id -> list of file paths

async def is_subscribed(bot, user_id):
    try:
        m = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return m.status in ['member','administrator','creator']
    except:
        return False

async def check_sub_required(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(context.bot, user_id):
        kb = [[InlineKeyboardButton("📢 اشترك بقناتي", url=CHANNEL_LINK)],
              [InlineKeyboardButton("✅ تأكيد الاشتراك", callback_data="check_sub")]]
        if update.message:
            await update.message.reply_text(f"🔒 لازم تشترك بقناتي حتى تستخدم البوت\n\n{CHANNEL_USERNAME}\n\nبعد الاشتراك دوس تأكيد", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.callback_query.answer("❌ اشترك اولاً", show_alert=True)
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_sub_required(update, context):
        return
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("📚 دمج ملفات PDF", callback_data="merge"), InlineKeyboardButton("✂️ تقسيم ملف PDF", callback_data="split")],
        [InlineKeyboardButton("🗜️ ضغط ملف PDF", callback_data="compress"), InlineKeyboardButton("📄 وورد إلى PDF", callback_data="word2pdf_info")],
        [InlineKeyboardButton("📊 Excel إلى PDF", callback_data="excel2pdf_info"), InlineKeyboardButton("📽️ باوربوينت إلى PDF", callback_data="ppt2pdf_info")],
        [InlineKeyboardButton("🖼️ JPG إلى PDF", callback_data="jpg2pdf"), InlineKeyboardButton("📝 تعديل PDF", callback_data="edit_info")],
        [InlineKeyboardButton("📷 صورة JPG إلى PDF", callback_data="img2pdf"), InlineKeyboardButton("🔄 PDF إلى JPG", callback_data="pdf2jpg")],
        [InlineKeyboardButton("💧 علامة مائية", callback_data="watermark"), InlineKeyboardButton("🔄 تدوير صفحات", callback_data="rotate")],
        [InlineKeyboardButton("🌐 HTML إلى PDF", callback_data="html2pdf_info"), InlineKeyboardButton("📑 تنظيم ملفات PDF", callback_data="organize")],
        [InlineKeyboardButton("🔧 إصلاح ملف PDF", callback_data="repair"), InlineKeyboardButton("📋 PDF/A", callback_data="pdfa_info")],
        [InlineKeyboardButton("🔢 أرقام الصفحات", callback_data="pagenum"), InlineKeyboardButton("📱 مسح ضوئي إلى PDF", callback_data="scan")],
        [InlineKeyboardButton("🔍 مقارنة ملفات", callback_data="compare"), InlineKeyboardButton("🔤 OCR", callback_data="ocr_info")],
        [InlineKeyboardButton("✂️ قص حواف", callback_data="crop"), InlineKeyboardButton("🧹 حذف معلومات حساسة", callback_data="clean")],
        [InlineKeyboardButton("🖼️ حوّل الصور إلى PDF", callback_data="images2pdf"), InlineKeyboardButton("📤 استخراج الصفحات", callback_data="extract")],
        [InlineKeyboardButton("📄 إضافة صفحات فارغة", callback_data="addblank"), InlineKeyboardButton("📝 تعديل البيانات الوصفية", callback_data="metadata")],
        [InlineKeyboardButton("🔄 عكس ترتيب الصفحات", callback_data="reverse"), InlineKeyboardButton("ℹ️ معلومات ملف", callback_data="info")],
        [InlineKeyboardButton("📑 رؤوس وتذييلات", callback_data="headerfooter"), InlineKeyboardButton