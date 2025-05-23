# Image Format Changer Telegram Bot

This bot can receive images or ZIP files containing images and detect their formats. It provides options to convert images to different formats using inline buttons.

## Features
- Accepts single or multiple images
- Accepts ZIP files containing images
- Auto-detects image formats
- Converts images to various formats
- Uses inline keyboard buttons for easy interaction
- Session-based password encryption
- Detailed conversion statistics

## Setup
1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file and add your configuration:
```env
BOT_TOKEN=your_bot_token_here
SESSION_PASSWORD=your_secure_password_here  # Used for encrypting session data
ADMIN_ID=your_telegram_id    # Optional: for receiving usage statistics
```

3. Run the bot:
```bash
python bot.py
```

## Security Features
- Session-based encryption using AES-256
- Each user session is individually encrypted
- Temporary files are securely deleted after conversion
- No image data is stored permanently

## Usage
1. Send an image or multiple images to the bot
2. Send a ZIP file containing images
3. The bot will show:
   - Total number of images detected
   - Breakdown of current formats
   - Total size of files
4. Select the desired format to convert all images
5. The bot will display conversion progress:
   ```
   📸 Converting batch #1234
   - Total images: 5 (15.2 MB)
   - Formats detected: JPEG (3), PNG (2)
   - Converting to: WebP
   - Progress: 3/5 completed
   - Size reduction: 15.2 MB → 8.7 MB (43% smaller)
   ```

## Statistics and Monitoring
The bot keeps track of:
- Number of images processed
- Total size of original files
- Total size after conversion
- Space saved through conversion
- Most used conversion formats
- Average processing time

Admins can access these statistics using:
- `/stats` - View general usage statistics
- `/stats today` - View today's statistics
- `/stats month` - View monthly statistics

## Supported Formats
- JPEG/JPG
- PNG
- WebP
- GIF
- TIFF
- BMP

## Performance
- Batch processing for multiple images
- Efficient memory management
- Automatic cleanup of temporary files
- Progress tracking for large conversions

## Error Handling
- Automatic retry for failed conversions
- Detailed error reporting
- Graceful handling of unsupported formats
- Network interruption recovery

## Best Practices
1. For best compression results:
   - Use WebP for web images
   - Use PNG for screenshots
   - Use JPEG for photos
2. Maximum file size: 20MB per file
3. Maximum batch size: 50 images
4. Supported image dimensions: up to 4096x4096 pixels

## Troubleshooting
If you encounter issues:
1. Check your internet connection
2. Verify file sizes are within limits
3. Ensure images are not corrupted
4. Check bot permissions
5. Verify .env configuration 