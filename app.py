import asyncio
from flask import Flask, render_template, request, send_file
from bs4 import BeautifulSoup
import pandas as pd
import nest_asyncio
import random
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import re
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Apply nested asyncio loop patch
nest_asyncio.apply()

# Initialize Flask app
app = Flask(__name__)

# User agents list for rotation to avoid detection
USER_AGENTS = [
    # (Your list of user agents)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/89.0",
    # Add more user agents if needed
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

# Asynchronous function to fetch reviews for a single product using Playwright
async def fetch_reviews(playwright, product_name, product_link):
    if product_link == 'No Link':
        print(f"Skipping product without a valid link: {product_name}")
        return []

    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page(user_agent=get_random_user_agent())
    print(f"Fetching reviews for: {product_name}")

    await page.goto(product_link)
    content = await page.content()
    soup = BeautifulSoup(content, 'html.parser')

    # Locate and parse the reviews section from the product page
    reviews = []
    for review in soup.find_all('div', {'data-hook': 'review'}, limit=30):  # Limit to 30 reviews
        review_text = review.find('span', {'data-hook': 'review-body'}).get_text(strip=True)
        reviews.append(review_text)

    await browser.close()
    return reviews if reviews else ['No Reviews']

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
        product_link = product.find('a', {'class': 'a-link-normal s-no-outline'}, href=True)
        product_link = 'https://www.amazon.com' + product_link['href'] if product_link else 'No Link'

        # Append parsed product details
        products.append({
            'Product Name': product_name,
            'Product Link': product_link,
            'Price': price,
            'Rating': rating,
        })

    return products if products else None  # Return None if no products found

# Asynchronous function to scrape product links and their reviews using Playwright
async def scrape_amazon_reviews(url, total_pages=1):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page(user_agent=get_random_user_agent())

        all_products = []
        current_page = 1
        try:
            await page.goto(url)
            while current_page <= total_pages:
                print(f"Scraping page: {current_page}")

                # Wait for the product listings to load
                try:
                    await page.wait_for_selector('div.s-main-slot', timeout=15000)
                except PlaywrightTimeoutError:
                    print("Timeout while waiting for product listings to load.")
                    break

                # Check for CAPTCHA
                if "Enter the characters you see below" in await page.content():
                    print("Encountered CAPTCHA. Exiting.")
                    break

                html = await page.content()
                product_details = parse_product_details(html)

                if product_details:
                    all_products.extend(product_details)
                else:
                    print(f"No products found on page {current_page}")
                    break  # Exit the loop if no products are found

                if current_page < total_pages:
                    # Try to find the 'Next' button using various selectors
                    next_page_button = await page.query_selector("//a[contains(@aria-label, 'Next')]")
                    if not next_page_button:
                        next_page_button = await page.query_selector("li.a-last a")
                    if not next_page_button:
                        next_page_button = await page.query_selector("a.s-pagination-next")

                    if next_page_button:
                        next_page_url = await next_page_button.get_attribute('href')
                        if next_page_url:
                            next_page_url = 'https://www.amazon.com' + next_page_url
                            print(f"Navigating to next page: {next_page_url}")
                            await asyncio.sleep(random.uniform(2, 5))  # Random delay
                            await page.goto(next_page_url)
                            current_page += 1
                        else:
                            print("No 'href' found for 'Next' button, ending pagination.")
                            break
                    else:
                        print("No 'Next' button found, ending pagination.")
                        break  # No more pages, exit the loop
                else:
                    print("Desired number of pages scraped.")
                    break

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await browser.close()

        # Now process the products and get reviews, as before
        all_reviews = []
        for product in all_products:
            reviews = await fetch_reviews(playwright, product['Product Name'], product['Product Link'])

            # Perform sentiment analysis
            sentiment, score = analyze_sentiment(reviews)
            product['Summary Sentiment'] = sentiment
            product['Sentiment Score'] = score
            all_reviews.append(product)

        return all_reviews

# Function to run asyncio in a synchronous environment and scrape Amazon reviews
def scrape_amazon_products_reviews(base_url, total_pages=1):
    loop = asyncio.get_event_loop()
    reviews = loop.run_until_complete(scrape_amazon_reviews(base_url, total_pages))
    return reviews

# HTML Form to input the number of pages to scrape
@app.route('/')
def index():
    return render_template('index.html')

# Handling the scraping request and how many pages to scrape
@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form['url']
    pages = int(request.form.get('pages', 1))  # Default is 1 page, or you can specify how many in the form

    if 'amazon.com' in url:
        reviews = scrape_amazon_products_reviews(url, total_pages=pages)

        # Save the results to a CSV file
        df = pd.DataFrame(reviews)

        # Reorder columns to move Product Link after Product Name
        df = df[['Product Name', 'Product Link', 'Price', 'Rating', 'Summary Sentiment', 'Sentiment Score']]

        output_file = 'amazon_products_with_sentiment.csv'
        df.to_csv(output_file, index=False)
        return send_file(output_file, as_attachment=True, mimetype='text/csv')
    else:
        return "Invalid URL, please provide a valid Amazon URL."

if __name__ == '__main__':
    app.run(debug=True)
