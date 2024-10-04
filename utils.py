from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import random
import re



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
