import math
from typing import Dict, List, Optional

class LocationService:
    """Service for location-based calculations"""
    
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula
        Returns distance in kilometers
        """
        # Convert degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        
        return c * r
    
    @staticmethod
    def estimate_transfer_time(distance_km: float, area_type: str = "urban") -> str:
        """
        Estimate transfer time based on distance and area type
        """
        # Base speed assumptions (km/h)
        speeds = {
            "urban": 20,      # City traffic
            "suburban": 30,   # Town areas
            "rural": 40,      # Countryside
        }
        
        speed = speeds.get(area_type, 25)
        time_hours = distance_km / speed
        time_minutes = time_hours * 60
        
        if time_minutes < 1:
            return "Less than 1 min"
        elif time_minutes < 60:
            return f"{int(time_minutes)} min"
        else:
            hours = int(time_minutes // 60)
            minutes = int(time_minutes % 60)
            return f"{hours}h {minutes}m"
    
    @staticmethod
    def get_area_type(location_address: str) -> str:
        """
        Determine area type based on location address
        """
        address_lower = location_address.lower()
        
        if any(word in address_lower for word in ['city', 'blantyre', 'lilongwe', 'mzuzu', 'zomba']):
            return "urban"
        elif any(word in address_lower for word in ['town', 'trading', 'market']):
            return "suburban"
        else:
            return "rural"