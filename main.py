
"""Project Overview: Simple Web Scraper
Goal: Build a tool to extract data from a website (e.g., quotes, headlines, or product listings).
Why this matters: Scraping is how you automate data collection—useful for research, market analysis, and competitive intelligence."""

"""
TO DO

Use Pandas to save the data and manipulate.
Add timer to be polite.

"""


# -- Imports --

import requests
import pandas as pd
from bs4 import BeautifulSoup


# -- Constants --

URL ="http://quotes.toscrape.com"
TIME_DELAY = 2
MAX_ATTEMPTS = 100
MAX_PAGES = 10
ELEMENTS_TO_FETCH =[
    ("Quotes", "span", "text"),
    ("Tags", "div", "tags"),
    ("Top Ten", "span", "tag-item"),
    ("Titles H1", "h1", None),
    ("Titles H2", "h2", None),
    ("Authors", "small", "author"),
    ("Author About", "a", None)]


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
    print (f"Status code = {status}")
    return status


def fetch_raw(response: requests.Response) -> str:
     """Checking the raw html of the link"""
     raw_data = response.text
     return raw_data

   
def connection_request() -> str:
    """fetching the connection responses"""
    response = fetch_response()
    status = fetch_status(response)
    raw_data = fetch_raw(response)
    return (raw_data)
    

# -- Data Parsing --

def parse_data(raw_data: str) -> BeautifulSoup:
    """Parsing HTML with bs4"""
    parsed_data = BeautifulSoup(raw_data, "html.parser")
    return parsed_data

#-- Find Data --

def get_quote_blocks(parsed_data: BeautifulSoup) -> BeautifulSoup:
    """Splitting down the data into blocks of quotes, so the data stays consistent"""
    blocks = parsed_data.find_all("div",class_="quote")
    return blocks


def quote_data(blocks: BeautifulSoup) -> list:
    """Extract structured data from each quote block"""
    all_quotes = []
    for block in blocks:
        quote_data={
            "Quote": block.find("span",class_="text").get_text(strip=True),
            "Authors":block.find("small", class_="author").get_text(strip=True),
            "Tags" : [tag.get_text(strip=True) for tag in block.find("div",class_="tags").find_all("a",class_="tag")]
        }
        all_quotes.append(quote_data)
    return all_quotes


def sub_data(parsed_data: BeautifulSoup) -> tuple[str, str, dict[str, str]]:
    h1_title = parsed_data.find("h1").get_text(strip=True)
    h2_title = parsed_data.find("h2").get_text(strip=True)
    top_ten = {f"tag {n}": ten.get_text(strip=True) for n, ten in enumerate(parsed_data.find_all("span",class_="tag-item"), start=1)}
    print (type(h1_title))
    return h1_title, h2_title, top_ten
    


# -- Store Data --

# -- Polite robot.txt scraping --


# Time constraints etc



#-- Main function--


def main():
    raw_data = connection_request()
    parsed_data = parse_data(raw_data)
    blocks = get_quote_blocks(parsed_data)
    quotes = quote_data(blocks)
    h1_title, h2_title, top_ten = sub_data(parsed_data)
    print (f"{h2_title} \n{top_ten}")
    print (f"\n {h1_title}")
    print (f"\n {quotes}")


if __name__ == "__main__":
    main()
    
    