import praw
import pandas as pd
from dotenv import load_dotenv
import os
from datetime import datetime
import logging
from textblob import TextBlob
from transformers import pipeline
import time
from retrying import retry

# Set up logging
logging.basicConfig(filename='reddit_scraper.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Initialize Reddit API
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent=os.getenv('REDDIT_USER_AGENT')
)


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def scrape_subreddit(subreddit_name, limit=10, time_filter='month'):
    """Scrape top posts with retry logic."""
    try:
        subreddit = reddit.subreddit(subreddit_name)
        posts = []
        for post in subreddit.top(time_filter=time_filter, limit=limit):
            post.comments.replace_more(limit=0)
            top_comments = [comment.body for comment in post.comments.list()[:3]]
            post_data = {
                'subreddit': subreddit_name,
                'title': post.title,
                'body': post.selftext,
                'comments': top_comments,
                'score': post.score,
                'url': post.url,
                'created_utc': datetime.utcfromtimestamp(post.created_utc)
            }
            posts.append(post_data)
        logging.info(f"Scraped {len(posts)} posts from r/{subreddit_name}")
        return posts
    except Exception as e:
        logging.error(f"Error scraping r/{subreddit_name}: {e}")
        raise

def save_posts(posts, filename='reddit_posts.csv'):
    """Save posts to CSV."""
    df = pd.DataFrame(posts)
    df.to_csv(filename, index=False)
    logging.info(f"Saved {len(posts)} posts to {filename}")

def filter_posts(posts, min_score=1000, min_polarity=0.2):
    """Filter posts for engagement using NLP and score."""
    try:
        # Initialize Hugging Face emotion classifier
        emotion_classifier = pipeline('text-classification', model='bhadresh-savani/distilbert-base-uncased-emotion')
        
        filtered_posts = []
        for post in posts:
            # Sentiment analysis with TextBlob
            text = post['title'] + ' ' + post['body']
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 (negative) to 1 (positive)
            
            # Emotion analysis with Hugging Face
            emotions = emotion_classifier(text[:512])  # Truncate for model limit
            top_emotion = emotions[0]['label'] if emotions else 'neutral'
            
            # Filter criteria: high score and strong sentiment/emotion
            if (post['score'] >= min_score and 
                abs(polarity) >= min_polarity and 
                top_emotion in ['anger', 'joy', 'sadness']):
                post['polarity'] = polarity
                post['emotion'] = top_emotion
                filtered_posts.append(post)
        
        logging.info(f"Filtered {len(filtered_posts)} posts from {len(posts)}")
        return filtered_posts
    except Exception as e:
        logging.error(f"Error filtering posts: {e}")
        return []

def main():
    subreddits = ['AmItheAsshole', 'confessions', 'tifu', 'relationships', 'ProRevenge']
    all_posts = []
    for subreddit in subreddits:
        posts = scrape_subreddit(subreddit, limit=10)
        all_posts.extend(posts)
    
    if all_posts:
        filtered_posts = filter_posts(all_posts)
        if filtered_posts:
            save_posts(filtered_posts, 'filtered_reddit_posts.csv')
        else:
            logging.warning("No posts passed filtering")
    else:
        logging.warning("No posts scraped")

if __name__ == "__main__":
    main()