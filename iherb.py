from datetime import datetime

from utils import analyze_sentiment
from utils import get_random_user_agent
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
import nest_asyncio
import traceback
import os
import math  # Import math for floor and ceil functions
import gc

nest_asyncio.apply()

# Function to save data when an error occurs or periodically
def save_data_to_file(data, file_name="scraped_data.csv"):
    df = pd.DataFrame(data)
    df.to_csv(file_name, index=False)
    print(f"Data saved to {file_name}")


# Function to scrape with Playwright and BeautifulSoup
async def scrape_iherb_product_details(url, xpath_query, num_pages):
    product_list = []
    # Start Playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)  # You can set headless=False to see the browser in action

        try:
            for page_number in range(num_pages):
                page_url = f"{url}&p={page_number + 1}"
                page = await browser.new_page(user_agent=get_random_user_agent())

                # Navigate to the URL
                await page.goto(page_url)

                # Wait for content to load (if necessary, you can use more sophisticated waiting strategies)
                await page.wait_for_selector('body')

                # Extract content via XPath
                element = page.locator(xpath_query)
                print("Element:", await element.count())

                if await element.count() > 0:
                    # Extract the HTML content of the first matching element
                    element_html = await element.first.inner_html()

                    # Parse the HTML with BeautifulSoup
                    soup = BeautifulSoup(element_html, 'html.parser')
                    product_divs = soup.find_all('div', class_='product-cell-container col-xs-12 col-sm-12 col-md-8 col-lg-6')
                    print("product:", product_divs.__len__())
                    for product in product_divs:
                        id_element = product.find('div', class_='product ga-product')
                        product_id = id_element['id'] if id_element else None
                        product_id = product_id.replace('pid_', '') if product_id != None else None # Remove 'pid_' from ID

                        product_link = product.find('a', class_='absolute-link product-link')
                        product_name = product_link['title'] if product_link else None
                        product_href = product_link['href'] if product_link else None

                        rating_element = product.find('a', class_='stars scroll-to')
                        product_rating = rating_element['title'] if rating_element else None
                        product_rating = product_rating.split(' - ')[0] if product_rating is not None else None

                        # Update starts here: Process the rating as per your instructions
                        if product_rating:
                            try:
                                # Extract the numeric rating value (e.g., 4.6 from "4.6/5")
                                numeric_rating = float(product_rating.split('/')[0])

                                # Check the decimal part and round accordingly
                                decimal_part = numeric_rating - int(numeric_rating)
                                if decimal_part > 0.5:
                                    numeric_rating = math.ceil(numeric_rating)
                                else:
                                    numeric_rating = math.floor(numeric_rating)
                            except ValueError:
                                # If conversion fails, set numeric_rating to None
                                numeric_rating = None
                        else:
                            numeric_rating = None

                        product_price = product.find('span', class_='price')
                        product_price = product_price.find('bdi').get_text(strip=True) if product_price and product_price.find('bdi') else None

                        product_list.append({
                            'Product Name': product_name,
                            'Product Price': product_price,
                            'Product Rating': product_rating,
                            'Label': numeric_rating,
                            "Product ID": product_id,
                            "Product Link": product_href,
                        })
                await page.close()
        except Exception as e:
            print(f"Error occurred while scraping product details: {str(e)}")
            traceback.print_exc()

            # Save collected data when an error occurs
            save_data_to_file(product_list, "partial_product_data.csv")

        finally:
            # Close the browser
            await page.close()
            await browser.close()

    save_data_to_file(product_list, "iherb_product_data.csv")
    return product_list

async def fetch_iherb_reviews(playwright, product_name, product_id, product_href, num_review_pages=1):
    if product_href is None or product_id is None:
        print(f"Skipping product without a valid link: {product_name}")
        return []

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(viewport={'width': 3840, 'height': 2160})
    page = await context.new_page()
    await page.set_extra_http_headers({
    'User-Agent': f'{get_random_user_agent()}'
})

    reviews = []
    dates = []
    stars_list = []
    for page_number in range(num_review_pages):
        print(f"Fetching reviews for: {product_name}({page_number + 1}/{num_review_pages} pages)...)")
        url = product_href.replace('iherb.com/pr', 'iherb.com/r')+f'?sort=6&isshowtranslated=true&p={page_number+1}'
        await page.goto(url)
        try:
            await page.wait_for_selector('#reviews', timeout=2000)
        except Exception:
            print(f"No reviews found for {product_name} on page {page_number + 1}.")
            return  ["No Reviews"], None, None
        # Locate the review container
        review_blocks = page.locator('div#reviews div.MuiBox-root.css-1v71s4n')

        # Get the number of reviews on the page
        review_count = await review_blocks.count()
        if review_count == 0:
            return  ["No Reviews"], None, None

        # Loop through each review block
        for i in range(review_count):
            review = review_blocks.nth(i)

            # Check if the "Read more" button exists in this specific review block
            read_more_button = review.locator('span.MuiTypography-root.MuiTypography-body2.css-ptz5k')
            if await read_more_button.count() > 0:
                # Check if the CAPTCHA is present
                captcha_present = await page.locator('#px-captcha-wrapper').count()
                if captcha_present > 0:
                    print(f"CAPTCHA detected on {product_name}.")
                    captcha_div = 'div#px-captcha-wrapper'
                    await page.evaluate(f'document.querySelector("{captcha_div}").remove();')


                # Attempt to click the "Read more" button with force
                try:
                    await read_more_button.click(force=True)
                except Exception as e:
                    print(f"Failed to click 'Read more' for {product_name}: {str(e)}")
                    continue  # Skip this review if the click fails

                # Optionally, wait for the full review text to load
                await page.wait_for_timeout(1000)  # Adjust timeout based on loading speed

            date_element = review.locator(
                'span.MuiTypography-root.MuiTypography-body2.css-1fktd33, span[data-testid="review-posted-date"]')

            # Ensure we await both `count()` and `text_content()`
            if await date_element.count() > 0:
                date_text = await date_element.text_content()
            else:
                date_text = None

            if date_text is not None:
                date_part = date_text.replace("Posted on ", "").strip()
                parsed_date = datetime.strptime(date_part, "%b %d, %Y")
                formatted_date = parsed_date.strftime("%Y-%m-%d")
            else:
                formatted_date = None

            stars = review.locator('ul[data-testid="review-rating"] li svg path[fill="#FAC627"]')
            # Count the number of filled stars

            num_stars = await stars.count() if await stars.count() > 0 else 0

            # Append the review date and star rating
            dates.append(formatted_date)
            stars_list.append(num_stars)
            # Now extract the full review text (whether expanded or not)
            review_text_element = review.locator('span.__react-ellipsis-js-content, div.review-full-text')
            review_text = await review_text_element.text_content() if await review_text_element.count() > 0 else "No Review Text"

            reviews.append(review_text.strip())
    await page.close()
    await context.close()
    await browser.close()
    return reviews, dates, stars_list


async def scrape_iherb_product_reviews(product_list, num_review_pages):
    if os.path.exists("iherb_product_data_reviews.csv"):
        print("Product Data file found. Loading existing product data...")
        product_list_existing = pd.read_csv("iherb_product_data_reviews.csv").to_dict('records')

        # Create a set of processed product IDs
        processed_product_ids = set()
        for product in product_list_existing:
            # if 'Reviews' in product and not pd.isna(product['Reviews']):
            #     processed_product_ids.add(product['Product ID'])
            if 'Review Dates' in product and not pd.isna(product['Review Dates']):
                processed_product_ids.add(product['Product ID'])
    else:
        product_list_existing = []
        processed_product_ids = set()

    product_data_map = {product['Product ID']: product for product in product_list_existing}

    async with async_playwright() as playwright:
        try:
            for idx, product in enumerate(product_list):
                product_name = product['Product Name']
                product_id = product['Product ID']
                product_href = product['Product Link']
                if product_id in processed_product_ids:
                    print(f"Skipping product {product_name} as reviews are already fetched.")
                    continue

                print(f"Index: ({idx+1}) Product: {product_name}")

                reviews, dates, stars_list = await fetch_iherb_reviews(playwright, product_name, product_id, product_href, num_review_pages=num_review_pages)
                sentiment, score = analyze_sentiment(reviews)
                product.update({
                    "Summary Sentiment": sentiment,
                    "Sentiment Score": score,
                    "Reviews": reviews,
                    "Review Dates": dates,
                    "Review Stars": stars_list
                })
                # Update the product data map
                product_data_map[product_id] = product

                df_updated = pd.DataFrame(list(product_data_map.values()))
                df_updated.to_csv('iherb_product_data_reviews.csv', index=False)
                print(f"Data saved to 'iherb_product_data_reviews.csv' after processing {product_name}")
                del stars_list
                del dates
                del sentiment
                del score
                del reviews
                gc.collect()

        except Exception as e:
            print(f"Error occurred while fetching reviews: {str(e)}")
            traceback.print_exc()
            save_data_to_file(product_list, "partial_product_reviews.csv")

    return list(product_data_map.values())


async def scrape_iherb_product_reviews_main(url, xpath_query, num_pages, num_review_pages):
    # Stage 1: Scrape product details
    if os.path.exists("iherb_product_data.csv"):
        print("Product Data file found. Loading existing product data...")
        product_list = pd.read_csv("iherb_product_data.csv").to_dict('records')
    else:
        product_list = await scrape_iherb_product_details(url, xpath_query, num_pages)

    # Stage 2: Scrape product reviews
    product_list_with_reviews = await scrape_iherb_product_reviews(product_list, num_review_pages)

    df = pd.DataFrame(product_list_with_reviews)
    return df