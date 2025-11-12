from typing import List, Dict, Optional
from decimal import Decimal
from django.db.models import Q
from .location_service import LocationService
from ..models import Agent, User

class RecommendationService:
    """Advanced agent recommendation engine for no-money-holding model"""
    
    @staticmethod
    def find_recommended_agents(
        client: User,
        amount: Decimal,
        to_service: str,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Find recommended agents based on multiple factors
        Returns list of agent data with scores and recommendations
        """
        # Step 1: Filter eligible agents
        eligible_agents = RecommendationService._filter_eligible_agents()
        
        # Step 2: Calculate scores for each agent
        scored_agents = []
        for agent in eligible_agents:
            score_data = RecommendationService._calculate_agent_scores(agent, client)
            scored_agents.append(score_data)
        
        # Step 3: Sort by combined recommendation score
        scored_agents.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        # Step 4: Return top results
        return scored_agents[:max_results]
    
    @staticmethod
    def _filter_eligible_agents():
        """Filter agents who can handle swaps (no float check since no money holding)"""
        return Agent.objects.filter(
            verified=True,
            is_online=True
        ).select_related('user')
    
    @staticmethod
    def _calculate_agent_scores(agent: Agent, client: User) -> Dict:
        """Calculate various scores for agent recommendation"""
        
        # Trust Score (already calculated in model)
        trust_score = agent.trust_score
        
        # Proximity Score
        proximity_score = RecommendationService._calculate_proximity_score(agent, client)
        
        # Availability Score (based on current workload)
        availability_score = RecommendationService._calculate_availability_score(agent)
        
        # Service Match Score
        service_score = 100  # All filtered agents can handle the service
        
        # Combined Recommendation Score
        recommendation_score = RecommendationService._calculate_combined_score(
            trust_score, proximity_score, availability_score, service_score
        )
        
        # Build response data
        return {
            'agent': agent,
            'trust_score': trust_score,
            'trust_level': agent.trust_level,
            'proximity_score': proximity_score,
            'availability_score': availability_score,
            'recommendation_score': recommendation_score,
            'distance_km': RecommendationService._get_distance_km(agent, client),
            'estimated_time': RecommendationService._get_estimated_time(agent, client),
            'completion_rate': agent.completion_rate,
            'average_response_time': agent.average_response_time,
            'experience_display': RecommendationService._get_experience_display(agent),
        }
    
    @staticmethod
    def _calculate_proximity_score(agent: Agent, client: User) -> float:
        """Calculate score based on proximity (0-100)"""
        if not client.has_location or not agent.user.has_location:
            return 50  # Neutral score if location data missing
        
        distance_km = LocationService.calculate_distance(
            float(client.location_lat), float(client.location_lng),
            float(agent.user.location_lat), float(agent.user.location_lng)
        )
        
        # Score based on distance (closer = higher score)
        if distance_km <= 1:    # Within 1km
            return 100
        elif distance_km <= 5:  # Within 5km
            return 80
        elif distance_km <= 10: # Within 10km
            return 60
        elif distance_km <= 20: # Within 20km
            return 40
        else:                   # Beyond 20km
            return 20
    
    @staticmethod
    def _calculate_availability_score(agent: Agent) -> float:
        """Calculate score based on current availability"""
        # Count active swaps (not completed or cancelled)
        active_swaps = agent.swap_requests.filter(
            status__in=['ACCEPTED', 'AWAITING_CLIENT_PROOF', 'CLIENT_PROOF_UPLOADED', 'AWAITING_AGENT_PROOF']
        ).count()
        
        # Score based on workload (fewer active swaps = higher score)
        if active_swaps == 0:
            return 100
        elif active_swaps == 1:
            return 80
        elif active_swaps == 2:
            return 60
        elif active_swaps == 3:
            return 40
        else:
            return 20
    
    @staticmethod
    def _calculate_combined_score(trust: float, proximity: float, availability: float, service: float) -> float:
        """Calculate combined recommendation score with weights"""
        weights = {
            'trust': 0.4,       # 40% - Most important: reliability
            'proximity': 0.3,   # 30% - Location convenience
            'availability': 0.2, # 20% - Current capacity
            'service': 0.1,     # 10% - Service match
        }
        
        return (
            trust * weights['trust'] +
            proximity * weights['proximity'] +
            availability * weights['availability'] +
            service * weights['service']
        )
    
    @staticmethod
    def _get_distance_km(agent: Agent, client: User) -> Optional[float]:
        """Get distance in km if locations available"""
        if not client.has_location or not agent.user.has_location:
            return None
        
        return LocationService.calculate_distance(
            float(client.location_lat), float(client.location_lng),
            float(agent.user.location_lat), float(agent.user.location_lng)
        )
    
    @staticmethod
    def _get_estimated_time(agent: Agent, client: User) -> str:
        """Get estimated transfer time"""
        distance_km = RecommendationService._get_distance_km(agent, client)
        if not distance_km:
            return "Location required"
        
        area_type = LocationService.get_area_type(agent.user.location_address)
        return LocationService.estimate_transfer_time(distance_km, area_type)
    
    @staticmethod
    def _get_experience_display(agent: Agent) -> str:
        """Get human-readable experience level"""
        swaps = agent.completed_swaps
        if swaps == 0:
            return "New Agent"
        elif swaps < 10:
            return f"{swaps} swaps"
        elif swaps < 50:
            return "Experienced"
        else:
            return "Expert"