from utils import analyze_sentiment
from utils import get_random_user_agent
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import nest_asyncio
import asyncio
import random
nest_asyncio.apply()


# Asynchronous function to fetch reviews for a single product using Playwright
async def fetch_amazon_reviews(playwright, product_name, product_link):
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
            reviews = await fetch_amazon_reviews(playwright, product['Product Name'], product['Product Link'])

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