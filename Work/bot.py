import requests
import json

username = 'shixionghan'
apiKey = 'KoIVRNRwukn8V1My5NCHSx9DH'

apiEndPoint = "http://api.scraping-bot.io/scrape/retail"

payload = json.dumps({
  "url": "https://www.bol.com/nl/nl/p/philips-243v7qdsb-full-hd-ips-monitor-24-inch/9200000077546745/",
  "options": {
    "premiumProxy": False,
    "useChrome": False,
    "proxyCountry": "GB",
    "proxyState": "ny",
    "waitForNetworkRequests": False
  }
})
headers = {
  'Content-Type': "application/json"
}

response = requests.request("POST", apiEndPoint, data=payload, auth=(username, apiKey), headers=headers)

print(response.text)