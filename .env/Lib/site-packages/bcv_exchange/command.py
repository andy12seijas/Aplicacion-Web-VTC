from bcv_exchange import get_exchange_rate


def get_bcv_exchange():
    try:
        exchange_data = get_exchange_rate()
        print("Exchange Rates:")
        for currency, rate in exchange_data["exchange_rates"].items():
            print(f"* {currency}: {rate} Bs")
        print(f"Last update: {exchange_data['date_of_change'].strftime("%d/%m/%Y")}")
        print(f"Source: {exchange_data['source']}")
    except Exception as e:
        print(f"Error: {str(e)}")
