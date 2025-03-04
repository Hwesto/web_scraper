# -- Imports --
"""Import necessary packages"""
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

"""Project Overview: Simple Web Scraper

Goal: Build a tool to extract data from a website 
(e.g., quotes, headlines, or product listings).

Why this matters: 
Scraping is how you automate data collection—useful for research, 
market analysis, and competitive intelligence."""


# -- Constants --

URL ="http://quotes.toscrape.com"
TIME_DELAY = 2
MAX_ATTEMPTS = 100
MAX_PAGES = 12
ELEMENTS_TO_FETCH =[
    ("Quotes", "span", "text"),
    ("Tags", "div", "tags"),
    ("Top Ten", "span", "tag-item"),
    ("Titles H1", "h1", None),
    ("Titles H2", "h2", None),
    ("Authors", "small", "author"),
    ("Author About", "a", None)]


# -- Connection Request --

def fetch_response(current_url) -> requests.Response:
    """Fetches HTTP response or returns None on failure"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(current_url, headers,timeout=15)
        return response
    except requests.RequestException:
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

def connection_request(current_url) -> str:
    """fetching the connection responses"""
    if current_url is None:
        print ("No URL Provided")
        return None
    response = fetch_response(current_url)
    status = fetch_status(response)
    print(status)
    raw_data = fetch_raw(response)
    return raw_data

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
            "Quotes": block.find("span",class_="text").get_text(strip=True),
            "Authors":block.find("small", class_="author").get_text(strip=True),
            "Tags" : [tag.get_text(strip=True) for tag in block.
                    find("div",class_="tags").find_all("a",class_="tag")]
        }
        all_quotes.append(quote_data)
    return all_quotes


def sub_data(parsed_data: BeautifulSoup) -> tuple[str, str, dict[str, str]]:
    """Find and parse all other metadata"""
    h1_title = parsed_data.find("h1").get_text(strip=True)
    h2_title = parsed_data.find("h2").get_text(strip=True)
    top_ten = {f"tag {n}": ten.get_text(strip=True)
               for n, ten in enumerate(parsed_data.find_all("span",class_="tag-item"), start=1)}
    meta_data = {
                 "Title": [h1_title],
                 "Subtitle": [h2_title]
                }
    for tag_key, tag_value in top_ten.items():
        meta_data[tag_key] = [tag_value]
    return meta_data


# -- Store Data --

def save_to_csv(quotes, filename = "quotes_data.csv"):
    """Saves quote data to CSV"""
    data_frame = pd.DataFrame(quotes)
    data_frame["Tags"] = data_frame["Tags"].apply(lambda x: ", ".join(x))
    data_frame.to_csv(filename, index = False)
    return data_frame

def save_metadata(meta_data, filename = "meta_data.csv"):
    """Saves metadata to CSV"""
    df = pd.DataFrame(meta_data)
    df.to_csv(filename, index = False)
    return df

# -- Pagination --
def next_url(parsed_data):
    """creates the next URL in pagination"""
    try:
        next_page = parsed_data.find("li", class_ = "next")
        if next_page:
            next_link = next_page.find("a")["href"]
            print (next_link)
        return URL + next_link
    except UnboundLocalError:
        print ("Final Page")
    return None

# -- Scrape all pages --
def scrape_all_pages():
    """Scrapes data from multiple pages, with politeness delay"""
    current_url = URL
    all_quotes = []
    meta = []
    current_page = 1
    while current_url:
        print(f"Scraping page {current_page}: {current_url}")
        if current_page > 1:
            time.sleep(TIME_DELAY)

        raw_data = connection_request(current_url)
        if raw_data is None:
            print (f"failed to get data from {current_url}")
            break

        parsed_data = parse_data(raw_data)
        quote_blocks = get_quote_blocks(parsed_data)
        quotes = quote_data(quote_blocks)
        current_url = next_url(parsed_data)
        print(current_url)

        all_quotes.extend(quotes)
        current_page +=1
    meta = sub_data(parsed_data)
    return all_quotes, meta


# -- Data Analysis --








































#-- Main function--


def main():
    """main running"""
    all_quotes, meta_data = scrape_all_pages()
    data_frame = save_to_csv(all_quotes)
    meta_data_frame = save_metadata(meta_data)
    print (data_frame)
    print (meta_data_frame)


if __name__ == "__main__":
    main()
