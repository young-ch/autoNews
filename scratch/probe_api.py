import requests

url = "https://stock.marsticker.com/api/sectors"
try:
    res = requests.get(url, timeout=5)
    print(f"Sectors status: {res.status_code}")
    print(res.text[:500])
except Exception as e:
    print(e)

url2 = "https://stock.marsticker.com/api/market-data"
try:
    res = requests.get(url2, timeout=5)
    print(f"Market-data status: {res.status_code}")
    print(res.text[:500])
except Exception as e:
    print(e)

url3 = "https://stock.marsticker.com/api/us-market"
try:
    res = requests.get(url3, timeout=5)
    print(f"US-market status: {res.status_code}")
    print(res.text[:500])
except Exception as e:
    print(e)
