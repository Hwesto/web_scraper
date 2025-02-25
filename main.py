"""Project Overview: Simple Web Scraper
Goal: Build a tool to extract data from a website (e.g., quotes, headlines, or product listings).
Why this matters: Scraping is how you automate data collection—useful for research, market analysis, and competitive intelligence."""



# -- Imports --

import requests
import pandas as pd
from bs4 import BeautifulSoup


# -- Constants --

URL ="http://quotes.toscrape.com"
TIME_DELAY = 2
MAX_ATTEMPTS = 100
MAX_PAGES = 10


# -- Connection Request --

def fetch_response() -> requests.Response:
    """Fetches HTTP response or returns None on failure"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(URL, headers)
        return response
    except (requests.RequestException):
        print ("Connection Error")
        return None
        

def fetch_status(response: requests.Response) -> int:
    """fetching the status code"""
    status = response.status_code
    return status


def fetch_raw(response: requests.Response) -> str:
     """Checking the raw html of the link"""
     raw_data = response.text
     return raw_data

   
def connection_request():
    """fetching the connection responses"""
    response = fetch_response()
    status = fetch_status(response)
    raw_data = fetch_raw(response)
    return (raw_data)
    

# -- Data Parsing --

def parse_data(raw_data):
    """Parsing HTML with bs4"""
    parsed_data = BeautifulSoup(raw_data, "html.parser")
    return parsed_data

#-- Find Data --

def fetch_title_h1(parsed_data):
    """find and parse all h1 titles from html"""
    title_location = parsed_data.find("h1")
    title_txt = title_location.get_text()
    return (title_txt)

def fetch_quotes(parsed_data):
    """find and parse all quotes from html"""
    quotes = []
    raw_quotes = parsed_data.find_all("span", class_="text")
    for raw_quote in raw_quotes:
        quote = raw_quote.get_text()
        quotes.append(quote) 
    return quotes

def fetch_authors(parsed_data):
    """find and parse all authors from html"""
    authors = []
    raw_authors = parsed_data.find_all("small", class_="author")
    for raw_author in raw_authors:
        author = raw_author.get_text()
        authors.append(author)
    return authors

def fetch_author_about(parsed_data):
    """find and parse all authors from html"""
    abouts = []
    raw_abouts = parsed_data.find_all("a",)
    for raw_about in raw_abouts:
        about = raw_about["href"]
        abouts.append(about)
    return abouts

def fetch_tags(parsed_data):
    """find and parse all tags from html"""
    tags = []
    raw_tags = parsed_data.find_all("div", class_="tags")
    for raw_tag in raw_tags:
        tag = raw_tag.get_text()
        tags.append(tag)
    return tags #Tags are mashed will need to fix

def fetch_title_h2(parsed_data):
    """find and parse all h1 titles from html"""
    title_location = parsed_data.find("h2")
    title_txt = title_location.get_text()
    return (title_txt)

def fetch_top_ten(parsed_data):
    """find and parse all tags from html"""
    top_ten = []
    raw_tens = parsed_data.find_all("span", class_="tag-item")
    for raw_ten in raw_tens:
        ten = raw_ten.get_text()
        top_ten.append(ten)
    return (top_ten)


def find_data(parsed_data):
    h1_title = fetch_title_h1(parsed_data)
    quotes = fetch_quotes(parsed_data)
    authors = fetch_authors(parsed_data)
    tags = fetch_tags(parsed_data)
    h2_title = fetch_title_h2(parsed_data)
    abouts = fetch_author_about(parsed_data)
    top_ten = fetch_top_ten(parsed_data)
    for quote, author in zip(quotes, authors):
        print({f"{quote} by {author}"})
    


# -- Clean Data -- 



# -- Concatenate Data --



# -- Appending --

# -- Polite robot.txt scraping --
# Time constraints etc

#-- Main function--
def main():
    raw_data = connection_request()
    parsed_data = parse_data(raw_data)

if __name__ == "__main__":
    main()