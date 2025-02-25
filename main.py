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


# -- Accessing Link --

"""Accessing the link via request.get"""
def Access(URL):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers =headers)
    print(response.status_code)



"""Checking the Status of the Link"""


# -- Read Data -- 

# -- Extracting Information --

# -- Parsing Information -- 

# -- Appending Information --

# -- Polite robot.txt scraping --
# Time constraints etc

#-- Main function--
def main():
    Access(URL)

if __name__ == "__main__":
    main()