import os

from dotenv import load_dotenv

load_dotenv()

# --- API keys (leave blank in .env for now, fill in later) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
NEWSAPI_API_KEY = os.environ.get("NEWSAPI_API_KEY", "")

MODEL_NAME = "claude-sonnet-4-6"

# --- Weather condition -> items to bring ---
PACKING_RULES = {
    "rain": ["umbrella", "waterproof jacket", "waterproof shoes"],
    "drizzle": ["light rain jacket", "umbrella"],
    "thunderstorm": ["umbrella", "waterproof jacket", "consider an indoor backup plan"],
    "snow": ["winter coat", "gloves", "boots", "scarf"],
    "clear": ["sunglasses"],
    "clouds": ["light jacket"],
    "mist": ["light jacket", "allow extra travel time for low visibility"],
    "fog": ["light jacket", "allow extra travel time for low visibility"],
    "tornado": ["seek sturdy shelter immediately", "avoid travel if at all possible"],
    "squall": ["secure loose items", "windproof jacket", "expect sudden weather changes"],
    "ash": ["mask or respirator", "eye protection", "avoid prolonged outdoor exposure"],
    "smoke": ["mask or respirator", "avoid prolonged outdoor exposure"],
    "haze": ["mask if air quality is poor", "limit strenuous outdoor activity"],
    "dust": ["mask or scarf to cover nose and mouth", "eye protection"],
    "sand": ["mask or scarf to cover nose and mouth", "eye protection"],
    "default": ["check the forecast again closer to the date"],
    # extra items added on top of the base list when temperatures are extreme
    "extreme_heat": ["sunscreen", "water bottle", "hat"],
    "extreme_cold": ["heavy coat", "thermal layers", "gloves"],
}

# --- Extra items added on top of the weather-based list, per activity type ---
ACTIVITY_ADDITIONS = {
    "commute": [],
    "outdoor_activity": ["sunscreen", "extra water"],
    "travel": ["travel adapter", "pack layers for the destination's climate"],
    "general": [],
}
