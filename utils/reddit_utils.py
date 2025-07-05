import requests
import time
import random
from utils.config import *
from utils.utils import *
from rank_bm25 import BM25Okapi

# Define the user agent and headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Define the URL templates
url_templates = {
    'hot': 'https://www.reddit.com/r/{subreddit}/hot.json',
    'new': 'https://www.reddit.com/r/{subreddit}/new.json',
    'top': 'https://www.reddit.com/r/{subreddit}/top.json?t={time_filter}',
    'search': 'https://www.reddit.com/search.json?q={query}&sort={sort_type}&type=posts',
    'url': '{url}.json'
}

# Function to fetch and parse Reddit posts
def fetch_reddit_posts(subreddit=None, url_type='hot', limit=10, time_filter='all', custom_url=None, search_query=None, sort_type='relevance'):
    """
    Fetches posts from Reddit based on the provided subreddit, URL type, and query parameters.

    Args:
        subreddit (str, optional): The subreddit to fetch posts from (e.g., 'python'). Defaults to None.
        url_type (str): The type of posts to fetch ('hot', 'new', 'top', 'search', 'url'). Defaults to 'hot'.
        limit (int, optional): The number of posts to retrieve. Defaults to 10.
        time_filter (str, optional): Time filter for top posts ('day', 'week', 'month', 'year', 'all'). Defaults to 'all'.
        custom_url (str, optional): A custom Reddit URL for fetching posts. Defaults to None.
        search_query (str, optional): Search query to fetch specific posts. Defaults to None.
        sort_type (str, optional): Sorting type for search results ('relevance', 'new', 'top'). Defaults to 'relevance'.

    Returns:
        list: A list of dictionaries containing post titles, links, IDs, text, and comments.
    """
    posts = []
    try:
        if url_type == 'url' and custom_url:
            url = url_templates['url'].format(url=custom_url)
        elif url_type == 'search' and search_query:
            url = url_templates['search'].format(query=search_query, sort_type=sort_type)
        else:
            url = url_templates[url_type].format(subreddit=subreddit, time_filter=time_filter)
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Parse JSON to get post titles, ids, links, and text
        if url_type == 'url':
            try:
                post_data = data[0]['data']['children'][0]['data']
                title = post_data['title']
                link = 'https://www.reddit.com' + post_data['permalink']
                post_id = post_data['id']
                selftext = post_data.get('selftext', '')
                posts.append({'title': title, 'link': link, 'id': post_id, 'text': selftext, 'comments': []})
            except:
                pass
        else:
            # Collect posts with their scores
            post_list = []
            for post in data['data']['children']:
                post_data = post['data']
                title = post_data['title']
                link = 'https://www.reddit.com' + post_data['permalink']
                post_id = post_data['id']
                selftext = post_data.get('selftext', '')
                score = post_data.get('score', 0)
                post_list.append({'title': title, 'link': link, 'id': post_id, 'text': selftext, 'comments': [], 'score': score})
            # Sort posts by score in descending order bm25 lol because reddit doesnt give any # relevance score
            if search_query:
                # Prepare corpus and tokenize
                corpus = [post['title'] + ' ' + post['text'] for post in post_list]
                tokenized_corpus = [doc.lower().split() for doc in corpus]
                bm25 = BM25Okapi(tokenized_corpus)
                tokenized_query = search_query.lower().split()
                scores = bm25.get_scores(tokenized_query)
                # Attach BM25 scores and sort
                for i, post in enumerate(post_list):
                    post['bm25_score'] = scores[i]
                post_list.sort(key=lambda x: x['bm25_score'], reverse=True)
            else:
                post_list.sort(key=lambda x: x['score'], reverse=True)
            posts.extend(post_list[:limit])
        
        return posts
    except Exception as e:
        return [{"error": f"Error fetching Reddit posts: {str(e)}"}]

# Function to fetch comments for a given post
def fetch_post_comments(post_id, limit=5, is_custom_url=False):
    """
    Fetches comments for a specific Reddit post by post ID.

    Args:
        post_id (str): The ID of the Reddit post to fetch comments for.
        limit (int, optional): The number of comments to retrieve. Defaults to 5.
        is_custom_url (bool, optional): Whether the post was fetched using a custom URL. Defaults to False.

    Returns:
        list: A list of comments (as strings) for the given post.
    """
    comments = []
    try:
        url = f'https://www.reddit.com/comments/{post_id}.json' if is_custom_url else f'https://www.reddit.com/comments/{post_id}.json'
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Parse JSON to get comments
        for comment in data[1]['data']['children'][:limit]:
            if comment['kind'] == 't1':  # Check if it's a comment (not a more comment or other kind)
                comment_data = comment['data']
                comments.append(comment_data['body'])
        
        return comments
    except requests.exceptions.RequestException as e:
        print(f"Error fetching comments for post {post_id}: {e}")
        return comments

# Function to add random delays
def random_delay():
    """
    Introduces a random delay between requests to mimic natural browsing behavior and avoid rate limiting.
    """
    time.sleep(random.uniform(1, 5))

# Main function to scrape posts and their comments
def reddit_reader(subreddit=None, url_type='hot', n=10, k=5, custom_url=None, time_filter='all', search_query=None, sort_type='relevance'):
    """
    Fetches Reddit posts and their associated comments.

    Args:
        subreddit (str, optional): The subreddit to fetch posts from. Defaults to None.
        url_type (str, optional): The type of posts to fetch ('hot', 'new', 'top', 'search', 'url'). Defaults to 'hot'.
        n (int, optional): The number of posts to fetch. Defaults to 10.
        k (int, optional): The number of comments to fetch for each post. Defaults to 5.
        custom_url (str, optional): A custom URL to fetch posts from. Defaults to None.
        time_filter (str, optional): Time filter for top posts ('day', 'week', 'month', 'year', 'all'). Defaults to 'all'.
        search_query (str, optional): Search query for fetching specific posts. Defaults to None.
        sort_type (str, optional): Sort type for search results ('relevance', 'new', 'top'). Defaults to 'relevance'.

    Returns:
        list: A list of posts, each with associated comments.
    """
    all_posts = []

    print(f"Fetching posts from {url_type} search" if url_type == 'search' else f"Fetching posts from /r/{subreddit}" if subreddit else f"Fetching posts from {custom_url}")
    posts = fetch_reddit_posts(subreddit=subreddit, url_type=url_type, limit=n, time_filter=time_filter, custom_url=custom_url, search_query=search_query, sort_type=sort_type)
    for post in posts:
        print(f"Fetching comments for post: {post['title']}")
        comments = fetch_post_comments(post['id'], limit=k, is_custom_url=(url_type == 'url'))
        post['comments'] = comments
        random_delay()  # Add delay between requests for comments
        
    all_posts.extend(posts)
    random_delay()  # Add delay between requests for posts

    return all_posts

def reddit_to_context(prompt, subreddit=None, url_type='hot', n=10, k=5, custom_url=None, time_filter='all', search_query=None, sort_type='relevance'):
    """
    Generates a context string by combining Reddit posts and comments into a single string.

    Args:
        prompt (str): The initial prompt to append Reddit content to.
        subreddit (str, optional): The subreddit to fetch posts from. Defaults to None.
        url_type (str, optional): The type of posts to fetch ('hot', 'new', 'top', 'search', 'url'). Defaults to 'hot'.
        n (int, optional): The number of posts to fetch. Defaults to 10.
        k (int, optional): The number of comments to fetch for each post. Defaults to 5.
        custom_url (str, optional): A custom URL to fetch posts from. Defaults to None.
        time_filter (str, optional): Time filter for top posts ('day', 'week', 'month', 'year', 'all'). Defaults to 'all'.
        search_query (str, optional): Search query for fetching posts. Defaults to None.
        sort_type (str, optional): Sort type for search results ('relevance', 'new', 'top'). Defaults to 'relevance'.

    Returns:
        str: The concatenated context string.
    """
    posts = reddit_reader(subreddit, url_type, n, k, custom_url, time_filter, search_query, sort_type)
    context = prompt + str(posts)
    return context

def reddit_reader_response(
                           subreddit:str, 
                           url_type:str, 
                           n:int, k:int,
                           custom_url:str, 
                           time_filter:str, 
                           search_query:str, 
                           sort_type:str,
                           model
):
    """
    Generates context by appending Reddit posts and comments to the provided prompt.

    Args:
        subreddit (str, optional): The subreddit to fetch posts from. Defaults to None.
        url_type (str, optional): The type of URL to use (hot, new, top, search, url). Defaults to 'hot'.
        n (int, optional): The number of posts to fetch. Defaults to 10.
        k (int, optional): The number of comments to fetch for each post. Defaults to 5.
        custom_url (str, optional): A custom URL to fetch posts from. Defaults to None.
        time_filter (str, optional): The time filter for top posts (e.g., day, week, month, year, all). Defaults to 'all'.
        search_query (str, optional): The search query for fetching posts. Defaults to None.
        sort_type (str, optional): The sort type for search results (e.g., relevance, new, top,). Defaults to 'relevance'.
    Returns:
        str: The concatenated context string.
    """       
    # context = reddit_to_context(prompt,subreddit, url_type, n=5, k=5, custom_url=custom_url, time_filter=time_filter)
    prompt = prompts['reddit_summary_prompt'].format(search_query=search_query)
    context = reddit_to_context(prompt, subreddit, url_type, n, k, custom_url=custom_url, time_filter=time_filter, search_query=search_query, sort_type=sort_type)
    response = model.invoke(context).content
    return response

