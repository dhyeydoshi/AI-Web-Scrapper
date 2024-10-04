from utils import analyze_sentiment
from utils import get_random_user_agent
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
import nest_asyncio
nest_asyncio.apply()


# Function to scrape with Playwright and BeautifulSoup
async def scrape_iherb_product_details(url, xpath_query, num_pages):
    product_list = []
    # Start Playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)  # You can set headless=False to see the browser in action

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

                    product_price = product.find('span', class_='price')
                    product_price = product_price.find('bdi').get_text(strip=True) if product_price and product_price.find('bdi') else None

                    product_list.append({
                        'Product Name': product_name,
                        'Product Price': product_price,
                        'Product Rating': product_rating,
                        "Product ID": product_id,
                        "Product Link": product_href,
                    })
            await page.close()

        # Close the browser
        await browser.close()
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
    for page_number in range(num_review_pages):
        print(f"Fetching reviews for: {product_name}({page_number + 1}/{num_review_pages} pages)...)")
        url = product_href.replace('iherb.com/pr', 'iherb.com/r')+f'?sort=6&isshowtranslated=true&p={page_number+1}'
        await page.goto(url)
        try:
            await page.wait_for_selector('#reviews', timeout=2000)
        except Exception:
            print(f"No reviews found for {product_name} on page {page_number + 1}.")
            return ["No Reviews Found"]
        # Locate the review container
        review_blocks = page.locator('div#reviews div.MuiBox-root.css-1v71s4n')

        # Get the number of reviews on the page
        review_count = await review_blocks.count()
        if review_count == 0:
            return ["No Reviews"]

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

            # Now extract the full review text (whether expanded or not)
            review_text_element = review.locator('span.__react-ellipsis-js-content, div.review-full-text')
            review_text = await review_text_element.text_content() if await review_text_element.count() > 0 else "No Review Text"

            reviews.append(review_text.strip())

    await browser.close()
    return reviews if reviews else ['No Reviews']


async def scrape_iherb_product_reviews(product_list, num_review_pages):
    async with async_playwright() as playwright:
        for product in product_list:
            product_name = product['Product Name']
            product_id = product['Product ID']
            product_href = product['Product Link']

            reviews = await fetch_iherb_reviews(playwright, product_name, product_id, product_href, num_review_pages=num_review_pages)
            sentiment, score = analyze_sentiment(reviews)
            product.update({
                "Summary Sentiment": sentiment,
                "Sentiment Score": score,
            })

    return product_list


async def scrape_iherb_product_reviews_main(url, xpath_query, num_pages, num_review_pages):
    # Stage 1: Scrape product details
    product_list = await scrape_iherb_product_details(url, xpath_query, num_pages)

    # Stage 2: Scrape product reviews
    product_list_with_reviews = await scrape_iherb_product_reviews(product_list, num_review_pages)

    df = pd.DataFrame(product_list_with_reviews)
    return df