
# AI Scrapper

**AI Scrapper** is a Python-based web scraping application built using Flask. It allows users to input an Amazon product URL, scrape product information, and perform sentiment analysis on the product reviews. The application saves the results, including the sentiment scores, in a CSV file that can be downloaded directly from the webpage.

## Table of Contents
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Features
- **Web Scraping**: Scrapes Amazon product pages for information such as product name, price, rating, and reviews.
- **Sentiment Analysis**: Uses VADER (Valence Aware Dictionary and sEntiment Reasoner) to analyze customer reviews and calculate a sentiment score.
- **Asynchronous Requests**: Uses `aiohttp` and `asyncio` to asynchronously fetch reviews and product details.
- **Dynamic Review Collection**: Allows users to specify the number of pages of reviews to scrape.
- **CSV Export**: Results are exported to a CSV file containing product information and the sentiment scores of reviews.
- **Clean and Responsive UI**: Modern, simple, and aesthetically pleasing UI using HTML, CSS, and Flask templating.

## Technologies Used
- **Python**: Core logic of the app, including scraping and sentiment analysis.
- **Flask**: Python micro web framework used for the back-end.
- **aiohttp & asyncio**: For making asynchronous HTTP requests.
- **BeautifulSoup**: For HTML parsing and data extraction from Amazon pages.
- **VADER**: A sentiment analysis tool to evaluate customer reviews.
- **HTML/CSS**: For structuring and styling the front-end.

## Installation
### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/ai-scrapper.git
cd ai-scrapper
```

### 2. Create a Virtual Environment (optional but recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```
Navigate to `http://127.0.0.1:5000` in your browser to access the application.

## Usage
1. **Input URL**: Enter the URL of an Amazon product in the input field on the homepage.
2. **Scrape Reviews**: Click the "Scrape Website" button (or the search icon) to start scraping reviews and performing sentiment analysis.
3. **Download Results**: After scraping, the application will provide a downloadable CSV file with product details and sentiment analysis.

## Project Structure
```bash
├── static
│   └── style.css           # CSS for styling the front-end
├── templates
│   └── index.html          # HTML template for the main UI
├── app.py               # Flask application with scraping and sentiment analysis logic
├── requirements.txt        # Required Python libraries
└── README.md               # Project documentation
```

### File Overview:
- **index.html**: Front-end template that includes the input form and visual layout of the application.
- **style.css**: The stylesheet that adds modern, aesthetic styling to the webpage, such as gradients and animations.
- **app.py**: Main application logic for web scraping, sentiment analysis, and file generation.
- **requirements.txt**: Lists all the dependencies used in this project (Flask, BeautifulSoup, aiohttp, etc.).

## Contributing
Feel free to fork the repository, create a new branch, and submit a pull request. Contributions are welcome!

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

