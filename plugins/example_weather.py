"""Example plugin: Weather tool"""

from src.plugin_registry import tool


@tool(name="weather", description="Get current weather for a city")
def get_weather(city: str, unit: str = "celsius") -> dict:
    """
    Fetch weather information.
    
    Args:
        city: City name (e.g., 'Paris')
        unit: Temperature unit: celsius or fahrenheit
    
    Returns:
        dict with temperature, condition, humidity
    """
    # Mock data - replace with real API call
    return {
        "city": city,
        "temperature": 22,
        "unit": unit,
        "condition": "Partly cloudy",
        "humidity": 65
    }


@tool(name="forecast", description="Get 7-day weather forecast")
def get_forecast(city: str, days: int = 7) -> dict:
    """
    Get weather forecast for upcoming days.
    
    Args:
        city: City name
        days: Number of days (1-14)
    
    Returns:
        dict with forecast data
    """
    return {
        "city": city,
        "days": min(days, 14),
        "forecast": [
            {"day": f"Day {i+1}", "high": 20+i, "low": 15+i}
            for i in range(min(days, 14))
        ]
    }
