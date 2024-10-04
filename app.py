import asyncio
from flask import Flask, render_template, request, send_file
import pandas as pd
import nest_asyncio
from iherb import scrape_iherb_product_reviews_main
from amazon import scrape_amazon_products_reviews

# Apply nested asyncio loop patch
nest_asyncio.apply()

# Initialize Flask app
app = Flask(__name__)


# HTML Form to input the number of pages to scrape
@app.route('/')
def index():
    return render_template('index.html')

# Handling the scraping request and how many pages to scrape
@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form['url']
    pages = int(request.form.get('reviewCount', 1))  # Default is 1 page, or you can specify how many in the form

    if 'amazon.com' in url:
        reviews = scrape_amazon_products_reviews(url, total_pages=pages)

        # Save the results to a CSV file
        df = pd.DataFrame(reviews)

        # Reorder columns to move Product Link after Product Name
        df = df[['Product Name', 'Product Link', 'Price', 'Rating', 'Summary Sentiment', 'Sentiment Score']]

        output_file = 'amazon_products_with_sentiment.csv'
        df.to_csv(output_file, index=False)
        return send_file(output_file, as_attachment=True, mimetype='text/csv')
    elif 'iherb.com' in url:
        # XPath for iHerb product listings
        xpath_query = '//*[@id="FilteredProducts"]/div[1]/div[2]/div[2]'
        num_review_pages = 2  # Number of review pages to scrape per product
        num_pages = pages  # Number of pages to scrape

        df = asyncio.run(scrape_iherb_product_reviews_main(url, xpath_query, num_pages=num_pages, num_review_pages=num_review_pages))
        df.to_csv('iherb_products_with_sentiment.csv', index=False)
        return send_file('iherb_products_with_sentiment.csv', as_attachment=True, mimetype='text/csv')

    else:
        return "Invalid URL, please provide a valid Amazon or iHerb URL."

if __name__ == '__main__':
    app.run(debug=True)
