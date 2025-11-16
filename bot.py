import os
import json
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== ADD THESE 2 LINES =====
from keep_alive import keep_alive
keep_alive()
# =============================

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
GITHUB_USERNAME = os.getenv('USERNAME')
GITHUB_REPO = os.getenv('REPO')
GITHUB_BRANCH = 'compounds'

# GitHub raw URL for fetching files
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}/"

# Load compounds data
def load_compounds():
    """Load compounds from JSON file"""
    try:
        with open('compounds.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['compounds']
    except Exception as e:
        logger.error(f"Error loading compounds.json: {e}")
        return []

COMPOUNDS = load_compounds()

# Pagination settings
ITEMS_PER_PAGE = 8

def create_keyboard(page=0):
    """Create inline keyboard with compound buttons"""
    keyboard = []
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    
    # Get compounds for current page
    page_compounds = COMPOUNDS[start_idx:end_idx]
    
    # Create buttons (2 per row)
    for i in range(0, len(page_compounds), 2):
        row = []
        for j in range(2):
            if i + j < len(page_compounds):
                compound = page_compounds[i + j]
                button_text = f"{compound['formula']} - {compound['name']}"
                callback_data = f"compound_{start_idx + i + j}"
                row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        keyboard.append(row)
    
    # Navigation buttons
    nav_buttons = []
    total_pages = (len(COMPOUNDS) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page-1}"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add refresh button
    keyboard.append([InlineKeyboardButton("🔄 Refresh List", callback_data="refresh")])
    
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        f"🧪 Welcome to **Molecular Structures Bot**\n\n"
        f"I can send you interactive 3D molecular structures in HTML format.\n\n"
        f"📚 **Available Compounds:** {len(COMPOUNDS)}\n\n"
        f"👇 Select a compound below to download its 3D structure:"
    )
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=create_keyboard(page=0),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    help_text = (
        "🧪 **Molecular Structures Bot - Help**\n\n"
        "**Available Commands:**\n"
        "/start - Show compound list\n"
        "/help - Show this help message\n"
        "/list - Show all compounds\n\n"
        "**How to use:**\n"
        "1️⃣ Click on any compound button\n"
        "2️⃣ Download the HTML file\n"
        "3️⃣ Open it in Chrome/Firefox\n"
        "4️⃣ Enjoy interactive 3D molecule! 🎉\n\n"
        "**Note:** Files open directly in your browser - no installation needed!"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown'
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all compounds"""
    await update.message.reply_text(
        "📚 **Select a compound:**",
        reply_markup=create_keyboard(page=0),
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Handle pagination
    if data.startswith("page_"):
        page = int(data.split("_")[1])
        await query.edit_message_text(
            "📚 **Select a compound:**",
            reply_markup=create_keyboard(page=page),
            parse_mode='Markdown'
        )
        return
    
    # Handle refresh
    if data == "refresh":
        global COMPOUNDS
        COMPOUNDS = load_compounds()
        await query.edit_message_text(
            f"🔄 **List refreshed!**\n\n📚 **Available Compounds:** {len(COMPOUNDS)}\n\nSelect a compound:",
            reply_markup=create_keyboard(page=0),
            parse_mode='Markdown'
        )
        return
    
    # Handle compound selection
    if data.startswith("compound_"):
        idx = int(data.split("_")[1])
        
        if idx >= len(COMPOUNDS):
            await query.edit_message_text("❌ Compound not found!")
            return
        
        compound = COMPOUNDS[idx]
        
        # Send loading message
        loading_msg = await query.edit_message_text(
            f"⏳ **Preparing {compound['formula']} - {compound['name']}...**\n\n"
            f"Downloading file from GitHub..."
        )
        
        try:
            # Fetch HTML file from GitHub
            file_url = GITHUB_RAW_URL + compound['file']
            logger.info(f"Fetching: {file_url}")
            
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            
            # Send file to user
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=response.content,
                filename=compound['file'],
                caption=(
                    f"🧪 **{compound['formula']} - {compound['name']}**\n\n"
                    f"📄 Download complete!\n\n"
                    f"**How to view:**\n"
                    f"1. Download the file\n"
                    f"2. Open with Chrome/Firefox\n"
                    f"3. Interact with the 3D structure!\n\n"
                    f"💡 *Tip: You can rotate, zoom, and explore the molecule!*"
                ),
                parse_mode='Markdown'
            )
            
            # Delete loading message and show success with back button
            await loading_msg.delete()
            
            back_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to List", callback_data="page_0")]
            ])
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ **{compound['name']} sent successfully!**\n\nSelect another compound:",
                reply_markup=back_keyboard,
                parse_mode='Markdown'
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching file: {e}")
            await loading_msg.edit_text(
                f"❌ **Error downloading file!**\n\n"
                f"File: `{compound['file']}`\n"
                f"Error: Connection timeout or file not found\n\n"
                f"Please make sure the file exists in the `compounds` branch.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await loading_msg.edit_text(
                f"❌ **Unexpected error occurred!**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or contact support.",
                parse_mode='Markdown'
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ **Oops! Something went wrong.**\n\n"
            "Please try again or use /start to restart the bot.",
            parse_mode='Markdown'
        )

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found! Please set it in environment variables.")
        return
    
    if not GITHUB_USERNAME or not GITHUB_REPO:
        logger.error("GitHub configuration not found! Please set GITHUB_USERNAME and GITHUB_REPO.")
        return
    
    if not COMPOUNDS:
        logger.error("No compounds found in compounds.json!")
        return
    
    logger.info(f"Starting bot with {len(COMPOUNDS)} compounds...")
    logger.info(f"GitHub URL: {GITHUB_RAW_URL}")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Bot started successfully! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
