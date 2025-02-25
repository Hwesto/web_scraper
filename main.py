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
    print (status)
    return (raw_data)
    

# -- Data Parsing --

def parse_data(raw_data):
    """Parsing HTML with bs4"""
    parsed_data = BeautifulSoup(raw_data, "html.parser")
    return parsed_data

def locate_titles(parsed_data)




# -- Extracting Information --

# -- Parsing Information -- 

# -- Appending Information --

# -- Polite robot.txt scraping --
# Time constraints etc

#-- Main function--
def main():
    raw_data = connection_request()
    parsed_data = parse_data(raw_data)
    locate_titles = 


if __name__ == "__main__":
    main()