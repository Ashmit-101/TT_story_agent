#!/bin/bash
set -e # Set script to exit on any error


echo "🚀Starting TikTok Content Generation Workflow..."

cd /Users/ashmit/Documents/GitHub/TT_story_agent

# Activate virtual environment
echo " Activating virtual environment..."
source reddit_scraper_env/bin/activate

# Verify activation
echo "Virtual environment activated: $VIRTUAL_ENV"
echo " Using Python: $(which python)"

# Run the Python scripts in sequence with error handling
echo "📱 Step 1: Running Reddit scraper..."
python reddit_scraper_env/reddit_scrapper.py
if [ $? -eq 0 ]; then
    echo "✅ Reddit scraper completed successfully"
else
    echo "❌ Reddit scraper failed"
    deactivate
    exit 1
fi

echo "📝 Step 2: Running script generator..."
python reddit_scraper_env/script_generator.py
if [ $? -eq 0 ]; then
    echo "✅ Script generator completed successfully"
else
    echo "❌ Script generator failed"
    deactivate
    exit 1
fi

echo "🎬 Step 3: Running content generator..."
python reddit_scraper_env/content.py
if [ $? -eq 0 ]; then
    echo "✅ Content generator completed successfully"
else
    echo "❌ Content generator failed"
    deactivate
    exit 1
fi

# Deactivate the virtual environment
deactivate
echo "🎉 All scripts completed successfully!"

# Optional: Show generated files
if ls final_video_*.mp4 1> /dev/null 2>&1; then
    echo "📹 Generated videos:"
    ls -la final_video_*.mp4
fi