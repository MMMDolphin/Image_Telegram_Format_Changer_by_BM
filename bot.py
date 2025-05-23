import os
import logging
import zipfile
import tempfile
import json
import time
from datetime import datetime
from PIL import Image
import pillow_avif
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from base64 import b64encode
from hashlib import sha256
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
SESSION_PASSWORD = os.getenv('SESSION_PASSWORD', 'default_password')  # Never use default in production
ADMIN_ID = os.getenv('ADMIN_ID')

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Supported formats for conversion
SUPPORTED_FORMATS = {
    'JPEG': '.jpg',
    'PNG': '.png',
    'WEBP': '.webp',
    'GIF': '.gif',
    'TIFF': '.tiff',
    'BMP': '.bmp',
    'AVIF': '.avif' # Added AVIF
}

# Statistics file
STATS_FILE = 'bot_statistics.json'


class Statistics:
    def __init__(self):
        self.stats = self.load_stats()

    def load_stats(self):
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading statistics: {e}")
        return {
            'total_images': 0,
            'total_size_original': 0,
            'total_size_converted': 0,
            'conversions_by_format': {},
            'daily_stats': {},
            'monthly_stats': {}
        }

    def save_stats(self):
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f)
        except Exception as e:
            logger.error(f"Error saving statistics: {e}")

    def update_conversion_stats(self, original_size, converted_size, target_format):
        today = datetime.now().strftime('%Y-%m-%d')
        month = datetime.now().strftime('%Y-%m')

        # Update total stats
        self.stats['total_images'] += 1
        self.stats['total_size_original'] += original_size
        self.stats['total_size_converted'] += converted_size

        # Update format stats
        if target_format not in self.stats['conversions_by_format']:
            self.stats['conversions_by_format'][target_format] = 0
        self.stats['conversions_by_format'][target_format] += 1

        # Update daily stats
        if today not in self.stats['daily_stats']:
            self.stats['daily_stats'][today] = {
                'images': 0,
                'size_original': 0,
                'size_converted': 0
            }
        self.stats['daily_stats'][today]['images'] += 1
        self.stats['daily_stats'][today]['size_original'] += original_size
        self.stats['daily_stats'][today]['size_converted'] += converted_size

        # Update monthly stats
        if month not in self.stats['monthly_stats']:
            self.stats['monthly_stats'][month] = {
                'images': 0,
                'size_original': 0,
                'size_converted': 0
            }
        self.stats['monthly_stats'][month]['images'] += 1
        self.stats['monthly_stats'][month]['size_original'] += original_size
        self.stats['monthly_stats'][month]['size_converted'] += converted_size

        self.save_stats()


# Initialize statistics
stats = Statistics()


def get_encryption_key(session_id: str) -> bytes:
    """Generate a unique encryption key for each session."""
    combined = f"{SESSION_PASSWORD}{session_id}"
    return base64.urlsafe_b64encode(sha256(combined.encode()).digest())


def encrypt_data(data: bytes, session_id: str) -> bytes:
    """Encrypt data using session-specific key."""
    f = Fernet(get_encryption_key(session_id))
    return f.encrypt(data)


def decrypt_data(encrypted_data: bytes, session_id: str) -> bytes:
    """Decrypt data using session-specific key."""
    f = Fernet(get_encryption_key(session_id))
    return f.decrypt(encrypted_data)


def format_size(size_bytes):
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} GB"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    welcome_message = (
        "👋 Welcome to the Image Format Changer Bot!\n\n"
        "You can:\n"
        "1. Send me any image or multiple images\n"
        "2. Send a ZIP file containing images\n"
        "I'll detect the format and provide conversion options.\n\n"
        "Try sending an image now! 📸"
    )
    await update.message.reply_text(welcome_message)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the stats command."""
    if not ADMIN_ID or str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("You don't have permission to view statistics.")
        return

    period = context.args[0] if context.args else 'all'

    if period == 'today':
        today = datetime.now().strftime('%Y-%m-%d')
        daily_stats = stats.stats['daily_stats'].get(today, {
            'images': 0,
            'size_original': 0,
            'size_converted': 0
        })

        stats_message = (
            "📊 Today's Statistics:\n"
            f"Images processed: {daily_stats['images']}\n"
            f"Original size: {format_size(daily_stats['size_original'])}\n"
            f"Converted size: {format_size(daily_stats['size_converted'])}\n"
            f"Space saved: {format_size(daily_stats['size_original'] - daily_stats['size_converted'])}"
        )

    elif period == 'month':
        month = datetime.now().strftime('%Y-%m')
        monthly_stats = stats.stats['monthly_stats'].get(month, {
            'images': 0,
            'size_original': 0,
            'size_converted': 0
        })

        stats_message = (
            "📊 This Month's Statistics:\n"
            f"Images processed: {monthly_stats['images']}\n"
            f"Original size: {format_size(monthly_stats['size_original'])}\n"
            f"Converted size: {format_size(monthly_stats['size_converted'])}\n"
            f"Space saved: {format_size(monthly_stats['size_original'] - monthly_stats['size_converted'])}"
        )

    else:
        total_stats = stats.stats
        format_stats = "\n".join(
            f"- {fmt}: {count} images"
            for fmt, count in total_stats['conversions_by_format'].items()
        )

        stats_message = (
            "📊 Overall Statistics:\n"
            f"Total images processed: {total_stats['total_images']}\n"
            f"Total original size: {format_size(total_stats['total_size_original'])}\n"
            f"Total converted size: {format_size(total_stats['total_size_converted'])}\n"
            f"Total space saved: {format_size(total_stats['total_size_original'] - total_stats['total_size_converted'])}\n\n"
            "Conversions by format:\n"
            f"{format_stats}"
        )

    await update.message.reply_text(stats_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "🔍 Here's how to use this bot:\n\n"
        "1. Send any image or multiple images\n"
        "2. Or send a ZIP file containing images\n"
        "3. I'll detect the format automatically\n"
        "4. Choose the desired format from the inline buttons\n"
        "5. I'll convert and send back your image(s) in a ZIP file.\n\n"
        "Supported formats: JPEG, PNG, WEBP, GIF, TIFF, BMP, AVIF\n\n"
        "Maximum file size: 20MB\n"
        "Maximum batch size: 50 images"
    )
    await update.message.reply_text(help_text)


def get_format_buttons():
    """Create inline keyboard with format options."""
    keyboard = []
    row = []
    for i, format_name in enumerate(SUPPORTED_FORMATS.keys()):
        row.append(InlineKeyboardButton(
            format_name,
            callback_data=f"convert_{format_name.lower()}"
        ))
        if len(row) == 2 or i == len(SUPPORTED_FORMATS) - 1:
            keyboard.append(row)
            row = []
    return InlineKeyboardMarkup(keyboard)


def get_image_info(pending_images_data):
    """Get summary of images and their formats. pending_images_data is a list of (path, original_name)."""
    formats = {}
    total_size = 0
    image_paths = [item[0] for item in pending_images_data]

    for path in image_paths:
        try:
            if not os.path.exists(path):
                logger.warning(f"File {path} not found in get_image_info. Skipping.")
                continue
            total_size += os.path.getsize(path)
            with Image.open(path) as img:
                format_name = img.format if img.format else "Unknown"
                formats[format_name] = formats.get(format_name, 0) + 1
        except Exception as e:
            logger.error(f"Error reading image {path} in get_image_info: {str(e)}")
    
    summary = []
    total_images = len(image_paths)
    summary.append(f"📸 Total images: {total_images} ({format_size(total_size)})")
    if not formats:
        summary.append("- No image formats detected yet (or files are not images).")
    else:
        for fmt, count in formats.items():
            summary.append(f"- {fmt}: {count} image{'s' if count > 1 else ''}")
    
    return "\n".join(summary)


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received images."""
    try:
        # Initialize or get the image collection for this user
        if 'pending_images' not in context.user_data:
            context.user_data['pending_images'] = []  # Stores tuples: (temp_file_path, original_filename)
            context.user_data['message_to_edit'] = None

        # Get the file
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Generate a generic original filename as Telegram doesn't provide one for photos directly
        # We'll use the file_unique_id to make it somewhat distinguishable
        original_filename = f"image_{photo.file_unique_id}.jpg" # Assume jpg, will be detected later by PIL

        # Download the file
        # We use a suffix that helps identify the original, though PIL will determine actual format
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{original_filename}") as temp_file_obj:
            await file.download_to_drive(temp_file_obj.name)
            context.user_data['pending_images'].append((temp_file_obj.name, original_filename))
            logger.info(f"Downloaded direct image to {temp_file_obj.name} (original: {original_filename})")

        # Update or send the status message
        status_text = (
            f"{get_image_info(context.user_data['pending_images'])}\n\n"
            "Select the format to convert all images:"
        )

        if context.user_data['message_to_edit']:
            try:
                await context.user_data['message_to_edit'].edit_text(
                    status_text,
                    reply_markup=get_format_buttons()
                )
            except Exception:
                # If editing fails, send a new message
                message = await update.message.reply_text(
                    status_text,
                    reply_markup=get_format_buttons()
                )
                context.user_data['message_to_edit'] = message
        else:
            message = await update.message.reply_text(
                status_text,
                reply_markup=get_format_buttons()
            )
            context.user_data['message_to_edit'] = message

    except Exception as e:
        logger.error(f"Error handling image: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error processing your image. Please try again.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received documents (ZIP files)."""
    try:
        document = update.message.document
        mime_type = document.mime_type

        if mime_type == 'application/zip':
            if 'pending_images' not in context.user_data:
                context.user_data['pending_images'] = [] # Stores tuples: (temp_file_path, original_filename)
                context.user_data['message_to_edit'] = None

            file = await context.bot.get_file(document.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_zip_file:
                await file.download_to_drive(temp_zip_file.name)
                zip_download_path = temp_zip_file.name
                logger.info(f"Downloaded ZIP to {zip_download_path}")

            with tempfile.TemporaryDirectory() as temp_extract_dir:
                logger.info(f"Extracting ZIP {zip_download_path} to {temp_extract_dir}")
                with zipfile.ZipFile(zip_download_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_dir)
                logger.info(f"Extraction complete.")

                for filename_in_zip in os.listdir(temp_extract_dir):
                    original_full_path = os.path.join(temp_extract_dir, filename_in_zip)
                    if os.path.isfile(original_full_path) and \
                       any(filename_in_zip.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.tiff', '.bmp', '.avif']): # Added .avif
                        
                        # Create a new temporary file to store this image from the zip,
                        # ensuring it persists until we are done with it.
                        # Suffix helps in debugging, not functionally critical here.
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename_in_zip}") as temp_image_storage:
                            with open(original_full_path, 'rb') as src_img_file:
                                temp_image_storage.write(src_img_file.read())
                            context.user_data['pending_images'].append((temp_image_storage.name, filename_in_zip))
                            logger.info(f"Stored {filename_in_zip} from ZIP to {temp_image_storage.name}")
                    else:
                        logger.info(f"Skipping non-image file or directory from ZIP: {filename_in_zip}")
            
            os.unlink(zip_download_path) # Clean up downloaded ZIP file
            logger.info(f"Cleaned up downloaded ZIP: {zip_download_path}")

            if not context.user_data['pending_images']:
                await update.message.reply_text("The ZIP file did not contain any supported image files.")
                return

            status_text = (
                f"{get_image_info(context.user_data['pending_images'])}\n\n"
                "Select the format to convert all images:"
            )
            if context.user_data['message_to_edit']:
                try:
                    await context.user_data['message_to_edit'].edit_text(status_text, reply_markup=get_format_buttons())
                except Exception: 
                    context.user_data['message_to_edit'] = await update.message.reply_text(status_text, reply_markup=get_format_buttons())
            else:
                context.user_data['message_to_edit'] = await update.message.reply_text(status_text, reply_markup=get_format_buttons())
        else:
            await update.message.reply_text("Please send a ZIP file containing images or send images directly.")

    except Exception as e:
        logger.error(f"Error handling document: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error processing your file. Please try again.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks for format conversion."""
    query = update.callback_query
    await query.answer()

    try:
        target_format = query.data.split('_')[1].upper()
        
        if 'pending_images' in context.user_data and context.user_data['pending_images']:
            pending_files_data = context.user_data['pending_images']
            status_message_text = f"Preparing to convert {len(pending_files_data)} images to {target_format}..."
            status = await query.message.reply_text(status_message_text)
            logger.info(status_message_text)

            start_time = time.time()
            converted_files_paths = [] # Store (output_path, original_filename_for_zip)
            total_original_size = 0
            total_converted_size = 0
            successfully_converted_count = 0

            for temp_file_path, original_filename in pending_files_data:
                try:
                    logger.info(f"Processing file: {temp_file_path} (original: {original_filename})")
                    if not os.path.exists(temp_file_path):
                        logger.error(f"File {temp_file_path} does not exist. Skipping.")
                        continue
                    
                    current_original_size = os.path.getsize(temp_file_path)
                    if current_original_size == 0:
                        logger.warning(f"File {temp_file_path} is empty. Skipping.")
                        continue
                    total_original_size += current_original_size
                    
                    img = Image.open(temp_file_path)
                    logger.info(f"Opened {temp_file_path}: format={img.format}, mode={img.mode}, size={img.size}")
                    
                    # Image mode conversion logic
                    if target_format == 'JPEG' and img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    elif target_format == 'WEBP' and img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA')
                    elif target_format == 'AVIF' and img.mode not in ('RGB', 'RGBA'): # AVIF often supports RGBA
                        logger.info(f"Converting image mode from {img.mode} to RGBA for AVIF.")
                        img = img.convert('RGBA')
                    
                    # Construct the new filename for inside the zip
                    base, _ = os.path.splitext(original_filename)
                    filename_in_zip = f"{base}{SUPPORTED_FORMATS[target_format]}"

                    # Output path for the temporary converted file
                    # We create it in a temporary directory that will be cleaned up by the OS or manually if needed.
                    # Suffix ensures it has the correct extension for PIL to save correctly.
                    with tempfile.NamedTemporaryFile(delete=False, suffix=SUPPORTED_FORMATS[target_format]) as temp_conv_file:
                        output_converted_path = temp_conv_file.name
                    
                    logger.info(f"Attempting to save to {output_converted_path} as {target_format} (for original: {original_filename})")
                    img.save(output_converted_path, format=target_format) # Pillow uses format string like 'JPEG', 'PNG'
                    logger.info(f"Saved {output_converted_path}")
                    
                    if not os.path.exists(output_converted_path) or os.path.getsize(output_converted_path) == 0:
                        logger.error(f"Output file {output_converted_path} is missing or empty after save. Skipping.")
                        if os.path.exists(output_converted_path): os.unlink(output_converted_path) # Clean up empty/failed file
                        continue
                    
                    current_converted_size = os.path.getsize(output_converted_path)
                    total_converted_size += current_converted_size
                    stats.update_conversion_stats(current_original_size, current_converted_size, target_format)
                    
                    converted_files_paths.append((output_converted_path, filename_in_zip))
                    successfully_converted_count += 1
                    
                    if successfully_converted_count % 5 == 0 or successfully_converted_count == len(pending_files_data):
                        progress_text = (
                            f"Converting... {successfully_converted_count}/{len(pending_files_data)} images processed.\n"
                            f"Total size so far: {format_size(total_original_size)} → {format_size(total_converted_size)}"
                        )
                        try: await status.edit_text(progress_text)
                        except Exception as e_edit: logger.warning(f"Could not edit progress message: {e_edit}")

                except Exception as e:
                    logger.error(f"Error converting image {temp_file_path} (original: {original_filename}): {str(e)}", exc_info=True)
                    await query.message.reply_text(f"⚠️ Error converting {original_filename}. Skipping it. Check logs.")
                    if 'output_converted_path' in locals() and os.path.exists(output_converted_path):
                         os.unlink(output_converted_path) # Clean up partially created file if error occurred after its creation
                    continue
            
            # After loop, if there are converted files, ZIP them up.
            if converted_files_paths:
                zip_filename_base = f"converted_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                zip_output_path = os.path.join(tempfile.gettempdir(), f"{zip_filename_base}.zip")
                
                logger.info(f"Creating ZIP file at {zip_output_path} with {len(converted_files_paths)} images.")
                with zipfile.ZipFile(zip_output_path, 'w') as zipf:
                    for file_path, filename_in_zip in converted_files_paths:
                        zipf.write(file_path, arcname=filename_in_zip)
                        logger.info(f"Added {file_path} as {filename_in_zip} to ZIP.")
                
                # Send the ZIP file
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=open(zip_output_path, 'rb'),
                    caption=f"Converted {successfully_converted_count} images to {target_format}."
                )
                logger.info(f"Sent ZIP file {zip_output_path}")
                
                # Clean up the sent ZIP file and individual converted temp files
                os.unlink(zip_output_path)
                for file_path, _ in converted_files_paths:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                logger.info("Cleaned up temporary converted files and ZIP.")
            else:
                await query.message.reply_text("No images were successfully converted.")

            time_taken = time.time() - start_time
            size_reduction_percent = ((total_original_size - total_converted_size) / total_original_size * 100) if total_original_size > 0 else 0
            final_status_text = (
                f"✅ Batch conversion completed!\n"
                f"- Processed: {successfully_converted_count}/{len(pending_files_data)} images\n"
                f"- Original total size: {format_size(total_original_size)}\n"
                f"- Converted total size: {format_size(total_converted_size)}\n"
                f"- Space saved: {format_size(total_original_size - total_converted_size)} ({size_reduction_percent:.1f}%)\n"
                f"- Time taken: {time_taken:.1f} seconds"
            )
            await status.edit_text(final_status_text)
            logger.info(final_status_text)

            # Cleanup original downloaded temp files
            for temp_file_path, _ in pending_files_data:
                if os.path.exists(temp_file_path):
                    try: os.unlink(temp_file_path)
                    except Exception as e_unlink: logger.error(f"Error unlinking original temp file {temp_file_path}: {e_unlink}")
            
            context.user_data['pending_images'] = []
            context.user_data['message_to_edit'] = None
            
        else:
            await query.message.reply_text("No images found to convert. Please send images first.")

    except Exception as e:
        logger.error(f"Error in button_callback: {str(e)}", exc_info=True)
        await query.message.reply_text("Sorry, a critical error occurred during conversion. Please try again.")


def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main() 