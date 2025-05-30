import pandas as pd
import openai
import os
from dotenv import load_dotenv
import logging
from retrying import retry
import time
import re

# Set up logging
logging.basicConfig(filename='script_generator.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def rank_stories(posts):
    """Rank posts based on quality and emotional engagement using GPT."""
    try:
        # Prepare input for GPT
        post_summaries = [
            f"Post {i+1}: Title: {post['title']}\nBody: {post['body'][:500]}...\nEmotion: {post['emotion']}\nScore: {post['score']}"
            for i, post in enumerate(posts)
        ]
        input_text = "\n\n".join(post_summaries)
        
        prompt = f"""
        You are a TikTok content expert. Below are summaries of {len(posts)} Reddit posts. Evaluate each based on:
        1. Quality (clarity, coherence, storytelling).
        2. Emotional engagement (ability to evoke strong emotions like anger, joy, sadness).
        3. TikTok suitability (dramatic, concise, likely to go viral).
        Rank the posts from best to worst and select the top post. Provide only the index (0-based) of the best post.

        Posts:
        {input_text}

        Output:
        Best post index: [index]
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a TikTok content analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.5
        )
        
        output = response.choices[0].message.content
        match = re.search(r'Best post index: (\d+)', output)
        if match:
            best_index = int(match.group(1))
            logging.info(f"Selected post index {best_index} as best story")
            return best_index
        else:
            logging.error("Failed to parse best post index")
            return 0  # Default to first post
    except Exception as e:
        logging.error(f"Error ranking stories: {e}")
        return 0

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def generate_script(post, max_words=200):
    """Generate a TikTok-friendly script from a Reddit post."""
    try:
        input_text = f"Title: {post['title']}\nBody: {post['body']}\nEmotion: {post['emotion']}"
        
        prompt = f"""
        You are a creative TikTok scriptwriter. From the Reddit post below, create a concise script (150–200 words) for a TikTok video under 60 seconds. Follow these rules:
        1. Rewrite the title into an engaging, attention-grabbing hook (10–15 words max).
        2. Summarize the post into a dramatic, emotional story that matches the post's emotion ({post['emotion']}).
        3. End with a call-to-action (e.g., 'What would you do?' or 'Follow for more!') tailored to the story.
        4. Ensure the script is TikTok-friendly: short sentences, emotional tone, conversational style.
        5. Do not exceed {max_words} words.

        Post:
        {input_text}

        Output format:
        Hook: [Your engaging title]
        Script: [Your summarized story]
        CTA: [Your call-to-action]"""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a TikTok content creator specializing in Reddit stories."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        output = response.choices[0].message.content
        logging.info(f"Raw output for post '{post['title']}':\n{output}")
        
        hook, script, cta = parse_output(output)
        
        if not script.strip():
            logging.warning(f"Empty script generated for post '{post['title']}'")
            return None
        
        if len(script.split()) > max_words:
            logging.warning(f"Script for '{post['title']}' exceeds {max_words} words")
            return None
        
        logging.info(f"Successfully generated script for post: '{post['title']}'")
        return {
            'original_title': post['title'],
            'hook_title': hook,
            'script': script,
            'cta': cta,
            'emotion': post['emotion']
        }
    except Exception as e:
        logging.error(f"Error generating script for post '{post['title']}': {e}")
        return None

def parse_output(output):
    try:
        hook = re.search(r'Hook:\s*(.+?)(?=\nScript:|\nCTA:|$)', output, re.DOTALL)
        script = re.search(r'Script:\s*(.+?)(?=\nCTA:|$)', output, re.DOTALL)
        cta = re.search(r'CTA:\s*(.+)', output, re.DOTALL)
        
        hook_text = hook.group(1).strip() if hook else ''
        script_text = script.group(1).strip() if script else ''
        cta_text = cta.group(1).strip() if cta else ''
        
        return hook_text, script_text, cta_text
    except Exception as e:
        logging.error(f"Error parsing output: {e}")
        return '', '', ''

def process_posts(input_file='filtered_reddit_posts.csv', output_file='tiktok_scripts.csv'):
    try:
        df = pd.read_csv(input_file)
        posts = [row.to_dict() for _, row in df.iterrows()]
        
        if not posts:
            logging.warning("No posts found in input file")
            return
        
        # Skip posts with empty bodies
        valid_posts = [post for post in posts if post['body'].strip()]
        if not valid_posts:
            logging.warning("No valid posts with non-empty bodies")
            return
        
        # Rank posts and select the best
        best_index = rank_stories(valid_posts)
        best_post = valid_posts[best_index]
        
        # Generate script for the best post
        script_data = generate_script(best_post)
        if script_data:
            df_scripts = pd.DataFrame([script_data])
            df_scripts.to_csv(output_file, index=False)
            logging.info(f"Saved 1 script to '{output_file}'")
        else:
            logging.warning("Failed to generate script for best post")
        
    except Exception as e:
        logging.error(f"Error processing posts: {e}")

def main():
    process_posts()

if __name__ == "__main__":
    main()