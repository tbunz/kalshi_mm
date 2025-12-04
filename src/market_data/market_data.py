from kalshi_python_async import Configuration, KalshiClient
from dotenv import load_dotenv
import os

load_dotenv()
KEY = os.getenv("KEY")
KEY_ID = os.getenv("KEY_ID")

# Configure the client
config = Configuration(
    host="https://api.elections.kalshi.com/trade-api/v2"
)



config.api_key_id = KEY_ID
config.private_key_pem = KEY

# Initialize the client
client = KalshiClient(config)

# Make API calls
balance = client.get_balance()
print(balance)