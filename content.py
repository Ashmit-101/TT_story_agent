import requests
import moviepy.editor as mp
import srt
from dotenv import load_dotenv
import nltk
import os
import pandas as pd
import time
import PIL
from PIL import Image, ImageFilter
import numpy as np
import logging
from Tiktok_uploader import uploadVideo


# Set up logging
logging.basicConfig(filename='content_log.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Pillow >=10 removed ANTIALIAS
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

nltk.download('punkt')
nltk.download('punkt_tab')

load_dotenv()
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
if not ELEVENLABS_API_KEY:
    print("❌ Error: No ElevenLabs API key found! Check your .env file")
    logging.error("Missing ElevenLabs API key")
    exit(1)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/fCxG8OHm4STbIsWe4aT9"

PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
if not PEXELS_API_KEY:
    print("❌ Error: No Pexels API key found! Check your .env file")
    logging.error("Missing Pexels API key")
    exit(1)

PEXELS_API_URL = "https://api.pexels.com/videos/search"

def generate_narration(script, video_number=1):
    """Generate narration audio for a specific video."""
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    payload = {
        "text": script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.75
        }
    }
    
    try:
        response = requests.post(ELEVENLABS_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        audio_filename = f"narration_{video_number}.mp3"
        with open(audio_filename, "wb") as f:
            f.write(response.content)
        
        # Placeholder timestamps
        timestamps = [{"word": w, "start": i*0.5, "end": (i+1)*0.5} for i, w in enumerate(script.split())]
        logging.info(f"Generated narration for video {video_number}")
        return timestamps, audio_filename
    except requests.exceptions.RequestException as e:
        print(f"❌ Error generating narration: {e}")
        logging.error(f"Error generating narration: {e}")
        return None, None

def create_srt(script, timestamps, video_number=1, speed_factor=1.3):
    """Create SRT subtitle file with adjusted timing for speed factor."""
    sentences = nltk.sent_tokenize(script)
    subtitles = []
    idx = 0
    
    for i, sentence in enumerate(sentences):
        words = sentence.split()
        if idx < len(timestamps) and idx + len(words) - 1 < len(timestamps):
            start = timestamps[idx]["start"] / speed_factor
            end = timestamps[idx + len(words) - 1]["end"] / speed_factor
            subtitles.append(srt.Subtitle(
                index=i+1,
                start=srt.srt_timestamp_to_timedelta(f"00:00:{start:.3f}"),
                end=srt.srt_timestamp_to_timedelta(f"00:00:{end:.3f}"),
                content=sentence
            ))
            idx += len(words)
    
    srt_filename = "subtitles.srt"
    with open(srt_filename, "w") as f:
        f.write(srt.compose(subtitles))
    
    logging.info(f"Created subtitles for video {video_number}")
    return srt_filename, subtitles

def download_background_video():
    """Download the most optimal background video (longest duration)."""
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": "Minecraft gameplay vertical", "per_page": 10}
    
    try:
        response = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        videos = response.json()["videos"]
        if videos:
            # Select video with longest duration
            best_video = max(videos, key=lambda v: v.get('duration', 0))
            video_url = best_video["video_files"][0]["link"]
            
            video_data = requests.get(video_url, timeout=30)
            video_data.raise_for_status()
            
            video_filename = "background.mp4"
            with open(video_filename, "wb") as f:
                f.write(video_data.content)
            
            logging.info(f"Downloaded background video: {video_filename}, duration: {best_video.get('duration')}s")
            return video_filename
        else:
            print("❌ No videos found for query 'Minecraft gameplay vertical'")
            logging.warning("No videos found for query 'Minecraft gameplay vertical'")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading background video: {e}")
        logging.error(f"Error downloading background video: {e}")
        return None

def loop_video(video, target_duration):
    video_duration = video.duration
    if video_duration >= target_duration:
        return video.subclip(0, target_duration)
    loops_needed = int(target_duration / video_duration) + 1
    video = video.loop(n=loops_needed)
    return video.subclip(0, target_duration)

def resize_to_9_16(video):
    target_width, target_height = 1080, 1920
    video_width, video_height = video.size
    
    scale = min(target_width / video_width, target_height / video_height)
    new_width = int(video_width * scale)
    new_height = int(video_height * scale)
    
    video = video.resize((new_width, new_height))
    
    frame = video.get_frame(0)
    img = Image.fromarray(frame)
    blurred_img = img.filter(ImageFilter.GaussianBlur(radius=20))
    blurred_array = np.array(blurred_img)
    
    blurred_clip = mp.ImageClip(blurred_array, duration=video.duration).resize((target_width, target_height))
    
    x = (target_width - new_width) / 2
    y = (target_height - new_height) / 2
    video = mp.CompositeVideoClip([blurred_clip, video.set_position((x, y))])
    
    return video

def add_subtitles(video, subtitles):
    clips = []
    for subtitle in subtitles:
        text_clip = mp.TextClip(
            subtitle.content,
            font="Arial",
            fontsize=40,
            color='white',
            stroke_color='black',
            stroke_width=2,
            method='caption',
            size=(video.size[0] - 100, None),
            align='center'
        )
        text_clip = text_clip.set_start(subtitle.start.total_seconds()).set_end(subtitle.end.total_seconds())
        text_clip = text_clip.set_position(('center', 'center'))
        clips.append(text_clip)
    
    return mp.CompositeVideoClip([video] + clips)

def generate_video(audio_filename, video_filename, subtitles):
    try:
        video = mp.VideoFileClip(video_filename)
        audio = mp.AudioFileClip(audio_filename)
        
        # Speed up audio by compressing duration
        original_duration = audio.duration
        target_duration = original_duration / 1.3
        audio = audio.set_duration(target_duration)
        
        # Loop video to match sped-up audio duration
        video = loop_video(video, target_duration)
        
        video = video.set_audio(audio)
        
        video = resize_to_9_16(video)
        
        video = add_subtitles(video, subtitles)
        
        output_filename = "final_video.mp4"
        video.write_videofile(output_filename, codec="libx264", audio_codec="aac")
        
        video.close()
        audio.close()
        
        print(f"✅ Video generated successfully: {output_filename}")
        logging.info(f"Generated video: {output_filename}")
        return output_filename
        
    except Exception as e:
        print(f"❌ Error generating video: {e}")
        logging.error(f"Error generating video: {e}")
        return None

def script_retriever():
    try:
        df = pd.read_csv("tiktok_scripts.csv")
        if df.empty:
            print("❌ No scripts found in tiktok_scripts.csv")
            logging.warning("No scripts found in tiktok_scripts.csv")
            return None
        
        # Take the first (and only) script
        row = df.iloc[0]
        hook = str(row['hook_title']) if pd.notna(row['hook_title']) else ""
        script = str(row['script']) if pd.notna(row['script']) else ""
        cta = str(row['cta']) if pd.notna(row['cta']) else ""
        
        complete_script = f"{hook} {script} {cta}".strip()
        logging.info(f"Retrieved script: {complete_script[:100]}...")
        return complete_script if complete_script else None
        
    except FileNotFoundError:
        print("❌ Error: tiktok_scripts.csv file not found!")
        logging.error("tiktok_scripts.csv file not found")
        return None
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        logging.error(f"Error reading CSV file: {e}")
        return None
    
def post_to_tiktok(video_path, caption, hashtags):
    session_id = "eae137523872fc7b0e75868ad7d89fd7"  # Replace with your TikTok session ID
    file = video_path
    title = caption
    tags = hashtags.split()
    uploadVideo(session_id, file, title, tags, verbose=True)

def main():
    print("🚀 Starting TikTok video generation...")
    logging.info("Starting TikTok video generation")
    
    script = script_retriever()
    
    if not script:
        print("❌ No valid script found. Please check tiktok_scripts.csv.")
        logging.error("No valid script found")
        return
    
    print("📝 Processing 1 script")
    print(f"Script preview: {script[:100]}...")
    
    try:
        print("🎤 Generating narration...")
        timestamps, audio_filename = generate_narration(script)
        
        if not timestamps or not audio_filename:
            print("❌ Failed to generate narration")
            logging.error("Failed to generate narration")
            return
        
        print("📝 Creating subtitles...")
        srt_filename, subtitles = create_srt(script=script, timestamps=timestamps, video_number=1, speed_factor=1.3)
        
        print("🎥 Downloading background video...")
        video_filename = download_background_video()
        
        if not video_filename:
            print("❌ Failed to download background video")
            logging.error("Failed to download background video")
            return
        
        print("🎬 Generating final video...")
        final_video = generate_video(audio_filename, video_filename, subtitles)
        
        if final_video:
            print(f"✅ Video generation complete: {final_video}")
            df = pd.read_csv("tiktok_scripts.csv")
            hook_title = df['hook_title'].iloc[0]  # Adjust based on your CSV structure
            hashtags = "#FYP #TikTokAutomation #YourHashtag"  # Your fixed hashtags
            post_to_tiktok(final_video, hook_title, hashtags)
            print(f"✅ Video posted to TikTok with caption: {hook_title} {hashtags}")
                
        
    except Exception as e:
        print(f"❌ Error processing video: {e}")
        logging.error(f"Error processing video: {e}")

if __name__ == "__main__":
    main()