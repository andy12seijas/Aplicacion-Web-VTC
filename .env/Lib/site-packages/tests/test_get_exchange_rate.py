import unittest
from datetime import datetime

from bcv_exchange import get_exchange_rate

class TestBCVResponseStructure(unittest.TestCase):
    
    def test_response_contains_required_fields(self):
        result = get_exchange_rate()
        self.assertIsInstance(result, dict)
        self.assertIn("source", result)
        self.assertEqual(result["source"], "https://www.bcv.org.ve/")
        self.assertIn("date_of_change", result)
        self.assertIsInstance(result["date_of_change"], datetime)
        self.assertIn("exchange_rates", result)
        exchange_rates = result["exchange_rates"]
        self.assertIsInstance(exchange_rates, dict)
        
        expected_currencies = {"USD", "EUR", "CNY", "TRY", "RUB"}
        self.assertEqual(set(exchange_rates.keys()), expected_currencies)
        
        for currency in expected_currencies:
            with self.subTest(currency=currency):
                self.assertIn(currency, exchange_rates)
                self.assertIsInstance(exchange_rates[currency], float)


if __name__ == '__main__':
    unittest.main()