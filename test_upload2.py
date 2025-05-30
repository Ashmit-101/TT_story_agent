from tiktok_uploader.upload import upload_video, upload_videos
from tiktok_uploader.auth import AuthBackend

# single video
upload_video('final_video.mp4', description='this is my description', cookies='cookies.txt')
