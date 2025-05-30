#!/usr/bin/env python3
import os
from webdriver_manager.chrome import ChromeDriverManager
from tiktok_uploader.auth   import AuthBackend
from tiktok_uploader.upload import upload_video

COOKIES_FILE = "cookies.txt"
VIDEO_FILE   = "final_video.mp4"

def main():
    print("🔄 TikTok Upload Test Starting…\n")

    # 1) Check that cookies.txt is here
    if not os.path.exists(COOKIES_FILE):
        print(f"❌ {COOKIES_FILE} not found. Export ALL TikTok cookies (use the Get-cookies.txt LOCALLY extension) in Netscape format.")
        return
    print(f"✅ Found {COOKIES_FILE}")

    # 2) Check that your video is here
    if not os.path.exists(VIDEO_FILE):
        print(f"❌ Video file '{VIDEO_FILE}' not found in {os.getcwd()}")
        return
    print(f"✅ Found video '{VIDEO_FILE}'\n")

    # 3) Install/fetch a matching ChromeDriver
    print("🔧 Installing/fetching ChromeDriver via webdriver_manager…")
    driver_path = ChromeDriverManager().install()
    print(f"✅ Using ChromeDriver at: {driver_path}\n")

    # 4) Build an AuthBackend with your cookies
    auth = AuthBackend(cookies=COOKIES_FILE)
    print("✅ AuthBackend created (will use cookies.txt to log you in)\n")

    # 5) Call upload_video with your auth _and_ driver_path
    try:
        upload_video(
            path        = VIDEO_FILE,
            description = "Test Upload from tiktok_uploader #test #upload",
            auth        = auth,
            headless    = False,       # so you can see the browser
            browser     = "chrome",
            driver_path = driver_path   # ⚠️ this is the key line
        )
        print("\n🎉 Upload successful!")
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        print(" • If Chrome bounced you to login, your cookies.txt is stale/incomplete.")
        print(" • Re-export ALL TikTok cookies via the browser extension and try again.")

if __name__ == "__main__":
    main()
