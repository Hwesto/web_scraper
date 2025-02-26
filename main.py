"""Project Overview: Simple Web Scraper
Goal: Build a tool to extract data from a website (e.g., quotes, headlines, or product listings).
Why this matters: Scraping is how you automate data collection—useful for research, market analysis, and competitive intelligence."""

"""
TO DO

Fix find_data to find data within same block.
Associate data points ensuring the rest of the code still works.
Create fully cleaned and associated data
Write function to print all associated data.
Use Pandas to save the data and manipulate.
Add timer to be polite.
Add pageination to scrape all quotes
Neaten main


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

def fetch_elements(parsed_data, tag: str, class_name:str):
    """Fetches text content from elements with the specified tag and class."""
    return [element.get_text() for element in parsed_data.find_all(tag, class_=class_name)]

def find_data(parsed_data) -> dict:
    """Fetches and returns all desired elements as a dictionary."""
    raw_elements = {
    name: fetch_elements(parsed_data, tag, class_name) 
    for name, tag, class_name in ELEMENTS_TO_FETCH}
    return(raw_elements)


# -- Clean Data -- 

def clean_data(raw_elements: dict) -> dict:
    """Cleans a dictionary of strings by stripping whitespace and removing empty entries."""
    return {key: [item.strip() for item in value if item.strip()] for key, value in raw_elements.items()}

def clean_text_list(text_list: list) -> list:
    """Cleans a list of strings by stripping whitespace and removing empty entries."""
    return [item.strip() for item in text_list if item.strip()]

def clean_tags(tag_list: list) -> list:
    cleaned_tags = []
    for tag_block in tag_list:
        tags = tag_block.replace("Tags:", "").strip().split('\n')
        cleaned_tags.extend(clean_text_list(tags))
    return (cleaned_tags)

def join(clean_elements):
    ce = clean_elements
    return (f"{ce["Quotes"]} by {ce["Authors"]}")

# -- Store Data --


# -- Polite robot.txt scraping --


# Time constraints etc



#-- Main function--


def main():
    raw_data = connection_request()
    parsed_data = parse_data(raw_data)
    raw_elements = find_data(parsed_data)
    clean_elements = clean_data(raw_elements)
    tags = clean_elements["Tags"]
    cleaned_tags =clean_tags(tags)
    clean_elements["Tags"] = cleaned_tags
    
    trial = join(clean_elements)
    print (trial)
    

if __name__ == "__main__":
    main()