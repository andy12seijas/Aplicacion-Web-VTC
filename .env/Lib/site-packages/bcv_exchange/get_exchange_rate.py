from datetime import datetime
import urllib3

from bs4 import BeautifulSoup
import requests

BCV_OFFICIAL_URL = "https://www.bcv.org.ve/"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_exchange_rate():
    """
    Retrieve official BCV exchange rates for Venezuela.
    
    Performs web scraping on the official website (https://www.bcv.org.ve/) of the Central Bank of Venezuela (BCV)
    to obtain exchange rates for major foreign currencies.

    Returns:
        dict: Dictionary containing:
            - 'source' (str): URL of the data source (BCV website)
            - 'date_of_change' (datetime): Last update date of exchange rates in ISO 8601 format
            - 'exchange_rates' (dict): Currency exchange rates in {currency_code: value_in_bolivars} format

    Raises:
        Exception: If connection error occurs or parsing fails
        ValueError: If BCV page structure has changed (selectors no longer valid)

    Notes:
        Supported currencies (as of latest page structure):
            - Euro (EUR)
            - Chinese Yuan (CNY)
            - Turkish Lira (TRY)
            - Russian Ruble (RUB)
            - US Dollar (USD)
        
        Requirements:
            - Active internet connection
            - Python dependencies: requests, beautifulsoup4
        
        SSL verification is disabled (verify=False) to handle potential certificate issues.
        This should be used with caution in production environments.

    Example:
        >>> rates = get_exchange_rate()
        >>> print(f"Source: {rates['source']}")
        >>> print(f"Last update: {rates['date_of_change']}")
        >>> print(f"USD rate: {rates['exchange_rates']['USD']}")
    """
    
    currencies = ['euro', 'yuan', 'lira', 'rublo', 'dolar']
    exchange_rates = {}

    try:
        r = requests.get(BCV_OFFICIAL_URL, verify=False)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error connecting to BCV: {e}")

    soup = BeautifulSoup(r.text, 'html.parser')
    
    main_container = soup.select_one('div.view-tipo-de-cambio-oficial-del-bcv')
    if not main_container:
        raise ValueError("Exchange rate container not found. The page structure may have changed")

    date_of_change = main_container.select_one('span.date-display-single')
    if not date_of_change:
        raise ValueError("Date of change not found. The page structure may have changed")

    for currency in currencies:
        try:
            currency_container = main_container.select_one(f'div#{currency}')
            money_format = currency_container.select_one('span').get_text(strip=True)
            money_value = currency_container.select_one('strong').get_text(strip=True).replace(',', '.')
            exchange_rates[money_format] = float(money_value)

        except (AttributeError, ValueError) as e:
            raise Exception(f'Exchange rate {currency} not found. The page structure may have changed.')

    return {
        "source": BCV_OFFICIAL_URL,
        "date_of_change": datetime.fromisoformat(date_of_change.attrs.get('content')),
        "exchange_rates": exchange_rates
    }
