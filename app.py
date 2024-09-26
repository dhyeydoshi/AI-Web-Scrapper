import asyncio
import aiohttp
from flask import Flask, render_template, request, send_file
from bs4 import BeautifulSoup
import pandas as pd
from aiohttp import TCPConnector
import nest_asyncio
import random
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # Using VADER
import re
import time

# Apply nested asyncio loop patch
nest_asyncio.apply()

# Initialize Flask app
app = Flask(__name__)

# User agents list for rotation to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/89.0"
]

# Initialize VADER sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# Function to get random user agent
def get_random_user_agent():
    return random.choice(USER_AGENTS)

# Function to clean the reviews text
def clean_text(text):
    # Replace encoded apostrophes and special characters with plain text equivalents
    text = text.replace("&#39;", "'")  # Replacing encoded apostrophe
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remove non-ASCII characters
    text = re.sub(r'\s+', ' ', text)  # Remove extra whitespaces
    return text.strip()

# Updated function to perform sentiment analysis using VADER
def analyze_sentiment(reviews):
    if not reviews:
        return "No Reviews", 0

    total_sentiment = 0
    cleaned_reviews = [clean_text(review) for review in reviews]  # Clean reviews before analyzing

    print(f"Cleaned Reviews for analysis: {cleaned_reviews}")  # Print cleaned reviews for debugging

    for review in cleaned_reviews:
        sentiment_score = analyzer.polarity_scores(review)['compound']  # Use VADER compound score for each review
        total_sentiment += sentiment_score

    avg_sentiment = total_sentiment / len(cleaned_reviews)  # Average sentiment score across all reviews
    print(f"Average Sentiment Score: {avg_sentiment}")  # Debugging output to see the score

    # Determine sentiment based on the average compound score
    if avg_sentiment >= 0.7:
        return "Highly Positive", avg_sentiment
    elif 0.3 <= avg_sentiment < 0.7:
        return "Positive", avg_sentiment
    elif -0.3 <= avg_sentiment < 0.3:
        return "Mixed", avg_sentiment
    elif -0.7 <= avg_sentiment < -0.3:
        return "Negative", avg_sentiment
    else:
        return "Highly Negative", avg_sentiment


# Asynchronous function to fetch reviews for a single product
async def fetch_reviews(session, product_name, product_link):
    if product_link == 'No Link':
        print(f"Skipping product without a valid link: {product_name}")
        return []

    headers = {"User-Agent": get_random_user_agent()}
    print(f"Fetching reviews for: {product_name}")

    async with session.get(product_link, headers=headers) as response:
        if response.status == 200:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            # Locate and parse the reviews section from the product page
            reviews = []
            for review in soup.find_all('div', {'data-hook': 'review'}, limit=30):  # Limit to 30 reviews
                review_text = review.find('span', {'data-hook': 'review-body'}).get_text(strip=True)
                reviews.append(review_text)

            return reviews if reviews else ['No Reviews']
        else:
            print(f"Failed to fetch reviews for {product_name}")
            return ['No Reviews']

# Function to parse the HTML and extract product details
def parse_product_details(html):
    soup = BeautifulSoup(html, 'html.parser')
    products = []

    for product in soup.find_all('div', {'data-component-type': 's-search-result'}):
        # Product Name
        product_name = product.h2.text.strip() if product.h2 else "No Product Name"

        # Price (whole and fractional)
        price_whole = product.find('span', {'class': 'a-price-whole'})
        price_fraction = product.find('span', {'class': 'a-price-fraction'})
        price = f"${price_whole.text.strip()}{price_fraction.text.strip()}" if price_whole and price_fraction else "No Price"

        # Rating
        rating = product.find('span', {'class': 'a-icon-alt'})
        rating = rating.text.strip() if rating else "No Rating"

        # Product Link
        product_link = product.find('a', {'class': 'a-link-normal'}, href=True)
        product_link = 'https://www.amazon.com' + product_link['href'] if product_link else 'No Link'

        # Append parsed product details
        products.append({
            'Product Name': product_name,
            'Product Link': product_link,
            'Price': price,
            'Rating': rating,
        })

    return products if products else None  # Return None if no products found

# Asynchronous function to scrape product links and their reviews
async def scrape_amazon_reviews(url, total_pages):
    connector = TCPConnector(limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []

        # First scrape product URLs from the search pages
        for page in range(1, total_pages + 1):
            paginated_url = f"{url}&page={page}"
            tasks.append(fetch_page(session, paginated_url))
        print(f"Total tasks Lenght: {len(tasks)}")
        print(f"Total tasks: {tasks}")
        all_products = []
        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                all_products.extend(result)

        all_reviews = []
        # Now, for each product, visit the product page and extract reviews
        for product in all_products:
            reviews = await fetch_reviews(session, product['Product Name'], product['Product Link'])

            # Perform sentiment analysis
            sentiment, score = analyze_sentiment(reviews)
            product['Summary Sentiment'] = sentiment
            product['Sentiment Score'] = score
            all_reviews.append(product)

        return all_reviews

# Define the fetch_page function
async def fetch_page(session, url, max_retries=3):
    retries = 0
    while retries < max_retries:
        try:
            headers = {"User-Agent": get_random_user_agent()}
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    product_details = parse_product_details(html)
                    return product_details if product_details else []
                elif response.status == 503:
                    print(f"Failed to fetch page: {response.url}")
                    print(f"Error 503: Service unavailable. Retrying... ({retries + 1}/{max_retries})")
                    retries += 1
                    await asyncio.sleep(2 ** retries)  # Backoff
                else:
                    print(f"Error: {response.status}")
                    print(f"Failed to fetch page: {response.url}")
                    return []
        except aiohttp.ClientError as e:
            print(f"HTTP Error: {e}")
            retries += 1
            await asyncio.sleep(2 ** retries)
    return []

# Function to run asyncio in a synchronous environment and scrape Amazon reviews
def scrape_amazon_products_reviews(base_url, total_pages):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():  # Handle case where the event loop is closed
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:  # No event loop in current thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    reviews = loop.run_until_complete(scrape_amazon_reviews(base_url, total_pages))
    return reviews

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form['url']
    pages = int(request.form.get('pages', 1))

    if 'amazon.com' in url:
        reviews = scrape_amazon_products_reviews(url, total_pages=pages)

        # Save the results to a CSV file
        df = pd.DataFrame(reviews)
        
        # Reorder columns to move Product Link after Product Name
        df = df[['Product Name', 'Product Link', 'Price', 'Rating', 'Summary Sentiment', 'Sentiment Score']]
        
        output_file = 'amazon_1000_products_with_sentiment.csv'
        df.to_csv(output_file, index=False)
        return send_file(output_file, as_attachment=True, mimetype='text/csv')
    else:
        return "Invalid URL, please provide a valid Amazon URL."

if __name__ == '__main__':
    app.run(debug=True)
