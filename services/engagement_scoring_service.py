"""
EngagementScoringService - P4-01 Engagement Scoring System
Calculates RFM scores, time-decay weighted scores, and predictive engagement metrics
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from functools import lru_cache

from repositories.engagement_event_repository import EngagementEventRepository
from repositories.engagement_score_repository import EngagementScoreRepository
from repositories.contact_repository import ContactRepository
from services.common.result import Result
from crm_database import EngagementEvent, EngagementScore, Contact
from utils.datetime_utils import utc_now, ensure_utc

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configuration for scoring component weights"""
    recency_weight: float = 0.3
    frequency_weight: float = 0.25
    monetary_weight: float = 0.2
    time_decay_weight: float = 0.15
    diversity_weight: float = 0.1
    
    def validate(self) -> bool:
        """Ensure weights sum to 1.0"""
        total = (self.recency_weight + self.frequency_weight + 
                self.monetary_weight + self.time_decay_weight + 
                self.diversity_weight)
        return abs(total - 1.0) < 0.001


class EngagementScoringService:
    """Service for calculating and managing engagement scores"""
    
    # Event type weights for scoring
    EVENT_TYPE_WEIGHTS = {
        'delivered': 1.0,
        'opened': 3.0,
        'clicked': 5.0,
        'responded': 7.0,
        'converted': 10.0,
        'opted_out': -5.0,
        'bounced': -3.0
    }
    
    # Positive and negative event classifications
    POSITIVE_EVENTS = {'opened', 'clicked', 'responded', 'converted'}
    NEGATIVE_EVENTS = {'opted_out', 'bounced', 'complained'}
    
    def __init__(self, 
                 event_repository: EngagementEventRepository,
                 score_repository: EngagementScoreRepository,
                 contact_repository: ContactRepository):
        """
        Initialize the engagement scoring service.
        
        Args:
            event_repository: Repository for engagement events
            score_repository: Repository for engagement scores
            contact_repository: Repository for contacts
        """
        self.event_repository = event_repository
        self.score_repository = score_repository
        self.contact_repository = contact_repository
        self.default_weights = ScoringWeights()
    
    def calculate_rfm_scores(self, contact_id: int, campaign_id: int) -> Dict[str, float]:
        """
        Calculate RFM (Recency, Frequency, Monetary) scores for a contact.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
        
        Returns:
            Dictionary with recency_score, frequency_score, and monetary_score
        """
        try:
            # Get all events for the contact
            events = self.event_repository.get_events_for_contact(contact_id)
            
            if not events:
                return {
                    'recency_score': 0.0,
                    'frequency_score': 0.0,
                    'monetary_score': 0.0
                }
            
            now = utc_now()
            
            # Calculate Recency Score (0-100)
            most_recent_event = events[0]  # Events are sorted by timestamp desc
            days_since_last = (now - most_recent_event.event_timestamp).days
            
            # Use exponential decay for recency scoring
            # Score = 100 * e^(-days/30), where 30 is the decay constant
            recency_score = 100.0 * math.exp(-days_since_last / 30.0)
            recency_score = max(0.0, min(100.0, recency_score))
            
            # Calculate Frequency Score (0-100)
            # Normalize frequency based on time span
            if len(events) > 1:
                oldest_event = events[-1]
                time_span_days = max(1, (now - oldest_event.event_timestamp).days)
                events_per_day = len(events) / time_span_days
                
                # Score based on events per day (cap at 1 event per day = 100)
                frequency_score = min(100.0, events_per_day * 100.0)
            else:
                frequency_score = 10.0  # Single event gets minimal frequency score
            
            # Calculate Monetary Score (0-100)
            total_value = Decimal('0')
            conversion_count = 0
            
            for event in events:
                if event.conversion_value:
                    total_value += event.conversion_value
                    conversion_count += 1
            
            if total_value > 0:
                # Logarithmic scale for monetary value
                # $1000+ = 100, $100 = 50, $10 = 25
                monetary_score = min(100.0, 25.0 * math.log10(float(total_value) + 1))
            else:
                monetary_score = 0.0
            
            return {
                'recency_score': round(recency_score, 2),
                'frequency_score': round(frequency_score, 2),
                'monetary_score': round(monetary_score, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating RFM scores for contact {contact_id}: {e}")
            raise
    
    def calculate_time_decay_score(self, contact_id: int, campaign_id: int, 
                                   decay_factor: float = 0.95) -> float:
        """
        Calculate time-decay weighted engagement score.
        
        More recent events have higher weight than older events.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
            decay_factor: Decay factor per day (0.95 = 5% decay per day)
        
        Returns:
            Time-decay weighted score (0-100)
        """
        try:
            events = self.event_repository.get_events_for_contact(contact_id)
            
            if not events:
                return 0.0
            
            now = utc_now()
            weighted_sum = 0.0
            weight_sum = 0.0
            
            for event in events:
                # Calculate days elapsed
                days_elapsed = (now - event.event_timestamp).days
                
                # Apply time decay
                time_weight = math.pow(decay_factor, days_elapsed)
                
                # Get event type weight
                event_weight = self.EVENT_TYPE_WEIGHTS.get(event.event_type, 1.0)
                
                # Combine weights
                combined_weight = time_weight * abs(event_weight)
                
                # Add to weighted sum (negative for negative events)
                if event_weight >= 0:
                    weighted_sum += combined_weight * event_weight
                else:
                    weighted_sum -= combined_weight * abs(event_weight)
                
                weight_sum += combined_weight
            
            if weight_sum == 0:
                return 0.0
            
            # Normalize to 0-100 scale
            # Assume max possible weighted sum is 10 * weight_sum (all conversions)
            normalized_score = (weighted_sum / (10.0 * weight_sum)) * 100.0
            
            # Ensure score is in valid range
            return max(0.0, min(100.0, normalized_score))
            
        except Exception as e:
            logger.error(f"Error calculating time decay score for contact {contact_id}: {e}")
            return 0.0
    
    def calculate_engagement_diversity_score(self, contact_id: int, campaign_id: int) -> float:
        """
        Calculate engagement diversity score based on variety of event types.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
        
        Returns:
            Diversity score (0-100)
        """
        try:
            events = self.event_repository.get_events_for_contact(contact_id)
            
            if not events:
                return 0.0
            
            # Count unique event types
            event_types = set()
            positive_types = set()
            
            for event in events:
                event_types.add(event.event_type)
                if event.event_type in self.POSITIVE_EVENTS:
                    positive_types.add(event.event_type)
            
            # Maximum possible positive event types
            max_positive_types = len(self.POSITIVE_EVENTS)
            
            # Score based on diversity of positive events
            if max_positive_types > 0:
                diversity_ratio = len(positive_types) / max_positive_types
                diversity_score = diversity_ratio * 100.0
            else:
                diversity_score = 0.0
            
            # Bonus for having multiple event types overall
            type_variety_bonus = min(20.0, len(event_types) * 4.0)
            
            # Penalty for negative events
            has_negative = any(et in self.NEGATIVE_EVENTS for et in event_types)
            if has_negative:
                diversity_score *= 0.8  # 20% penalty
            
            final_score = min(100.0, diversity_score + type_variety_bonus)
            
            return round(final_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating diversity score for contact {contact_id}: {e}")
            return 0.0
    
    def calculate_composite_score(self, component_scores: Dict[str, float], 
                                 weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate weighted composite score from individual components.
        
        Args:
            component_scores: Dictionary of score components
            weights: Optional custom weights (uses defaults if not provided)
        
        Returns:
            Composite score (0-100)
        """
        if not weights:
            weights = {
                'recency_weight': self.default_weights.recency_weight,
                'frequency_weight': self.default_weights.frequency_weight,
                'monetary_weight': self.default_weights.monetary_weight,
                'time_decay_weight': self.default_weights.time_decay_weight,
                'diversity_weight': self.default_weights.diversity_weight
            }
        
        composite = 0.0
        
        # Map component scores to weights
        score_weight_mapping = [
            ('recency_score', 'recency_weight'),
            ('frequency_score', 'frequency_weight'),
            ('monetary_score', 'monetary_weight'),
            ('time_decay_score', 'time_decay_weight'),
            ('engagement_diversity_score', 'diversity_weight')
        ]
        
        for score_key, weight_key in score_weight_mapping:
            if score_key in component_scores and weight_key in weights:
                composite += component_scores[score_key] * weights[weight_key]
        
        return round(composite, 2)
    
    def calculate_engagement_probability(self, contact_id: int, campaign_id: int) -> float:
        """
        Calculate probability of future engagement using statistical model.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
        
        Returns:
            Engagement probability (0.0-1.0)
        """
        try:
            events = self.event_repository.get_events_for_contact(contact_id)
            
            if not events:
                return 0.1  # Base probability for new contacts
            
            # Calculate engagement rate
            total_events = len(events)
            positive_events = sum(1 for e in events if e.event_type in self.POSITIVE_EVENTS)
            
            if total_events == 0:
                return 0.1
            
            base_rate = positive_events / total_events
            
            # Adjust for recency
            now = utc_now()
            most_recent = events[0]
            days_since_last = (now - most_recent.event_timestamp).days
            
            # Recency factor (decreases probability as time passes)
            recency_factor = math.exp(-days_since_last / 30.0)
            
            # Check for recent positive engagement
            recent_positive = any(
                e.event_type in self.POSITIVE_EVENTS and 
                (now - e.event_timestamp).days <= 7
                for e in events[:5]  # Check last 5 events
            )
            
            # Calculate final probability
            if recent_positive:
                # Boost probability for recent positive engagement
                probability = base_rate * 0.7 + recency_factor * 0.3
            elif base_rate == 0:  # No positive events at all
                # Very low probability for zero engagement
                probability = 0.05 + recency_factor * 0.1
            else:
                # Standard calculation with lower baseline for low engagement
                probability = base_rate * 0.4 + recency_factor * 0.2 + 0.1
            
            # Check for negative events
            has_opted_out = any(e.event_type == 'opted_out' for e in events)
            if has_opted_out:
                probability *= 0.1  # Massive reduction for opt-outs
            
            # Ensure probability is in valid range
            return max(0.0, min(1.0, probability))
            
        except Exception as e:
            logger.error(f"Error calculating engagement probability for contact {contact_id}: {e}")
            return 0.1
    
    def normalize_scores_to_percentile(self, raw_scores: List[float]) -> List[float]:
        """
        Normalize raw scores to 0-100 percentile scale.
        
        Args:
            raw_scores: List of raw score values
        
        Returns:
            List of normalized scores (0-100)
        """
        if not raw_scores:
            return []
        
        if len(raw_scores) == 1:
            return [50.0]  # Single score gets median percentile
        
        # Sort scores for percentile calculation
        sorted_scores = sorted(raw_scores)
        score_to_percentile = {}
        
        for i, score in enumerate(sorted_scores):
            # Calculate percentile (0-100)
            percentile = (i / (len(sorted_scores) - 1)) * 100.0
            score_to_percentile[score] = percentile
        
        # Map original scores to percentiles
        return [score_to_percentile[score] for score in raw_scores]
    
    def calculate_engagement_score(self, contact_id: int, campaign_id: int) -> EngagementScore:
        """
        Calculate and save full engagement score for a contact.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
        
        Returns:
            EngagementScore instance
        """
        try:
            # Get events once and cache them
            events = self.event_repository.get_events_for_contact(contact_id)
            
            # Calculate all score components using cached events
            rfm_scores = self._calculate_rfm_scores_with_events(events)
            time_decay_score = self._calculate_time_decay_score_with_events(events)
            diversity_score = self._calculate_engagement_diversity_score_with_events(events)
            
            # Combine scores for composite
            component_scores = {
                **rfm_scores,
                'time_decay_score': time_decay_score,
                'engagement_diversity_score': diversity_score
            }
            
            # Calculate composite score
            overall_score = self.calculate_composite_score(component_scores)
            
            # Calculate engagement probability using cached events
            engagement_probability = self._calculate_engagement_probability_with_events(events)
            
            # Get event statistics from cached events
            positive_count = sum(1 for e in events if e.event_type in self.POSITIVE_EVENTS)
            negative_count = sum(1 for e in events if e.event_type in self.NEGATIVE_EVENTS)
            
            # Prepare score data
            score_data = {
                'overall_score': overall_score,
                'recency_score': rfm_scores['recency_score'],
                'frequency_score': rfm_scores['frequency_score'],
                'monetary_score': rfm_scores['monetary_score'],
                'engagement_diversity_score': diversity_score,
                'time_decay_score': time_decay_score,
                'engagement_probability': engagement_probability,
                'total_events_count': len(events),
                'positive_events_count': positive_count,
                'negative_events_count': negative_count,
                'last_event_timestamp': events[0].event_timestamp if events else None,
                'first_event_timestamp': events[-1].event_timestamp if events else None,
                'score_version': '1.0',
                'calculation_method': 'rfm',
                'calculated_at': utc_now()
            }
            
            # Upsert the score
            return self.score_repository.upsert_score(contact_id, campaign_id, **score_data)
            
        except Exception as e:
            logger.error(f"Error calculating engagement score for contact {contact_id}: {e}")
            raise
    
    def batch_calculate_scores(self, campaign_id: int, 
                              contact_ids: Optional[List[int]] = None) -> List[EngagementScore]:
        """
        Calculate scores for multiple contacts in batch.
        
        Args:
            campaign_id: Campaign ID
            contact_ids: Optional list of contact IDs (if None, processes all)
        
        Returns:
            List of calculated EngagementScore instances
        """
        try:
            # Get contacts to process
            if contact_ids:
                contacts = [self.contact_repository.get_by_id(cid) for cid in contact_ids]
                contacts = [c for c in contacts if c]  # Filter out None values
            else:
                contacts = self.contact_repository.get_all()
            
            results = []
            
            for contact in contacts:
                try:
                    score = self.calculate_engagement_score(contact.id, campaign_id)
                    results.append(score)
                except Exception as e:
                    logger.error(f"Error calculating score for contact {contact.id}: {e}")
                    # Continue with other contacts
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch score calculation: {e}")
            return []
    
    def update_stale_scores(self, max_age_hours: int = 168) -> int:
        """
        Update scores that are considered stale.
        
        Args:
            max_age_hours: Maximum age in hours before score is stale
        
        Returns:
            Number of scores updated
        """
        try:
            # Get stale scores
            stale_scores = self.score_repository.get_scores_needing_update(max_age_hours)
            
            updated_count = 0
            
            for score in stale_scores:
                try:
                    # Recalculate the score
                    self.calculate_engagement_score(score.contact_id, score.campaign_id)
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Error updating stale score {score.id}: {e}")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating stale scores: {e}")
            return 0
    
    def get_score_explanation(self, score_components: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate human-readable explanation of score components.
        
        Args:
            score_components: Dictionary of score components
        
        Returns:
            Dictionary with explanations
        """
        overall_score = score_components.get('overall_score', 0)
        recency_score = score_components.get('recency_score', 0)
        frequency_score = score_components.get('frequency_score', 0)
        monetary_score = score_components.get('monetary_score', 0)
        engagement_prob = score_components.get('engagement_probability', 0)
        diversity_score = score_components.get('engagement_diversity_score', 0)
        
        # Determine overall assessment
        if overall_score >= 80:
            assessment = "Highly engaged contact"
        elif overall_score >= 60:
            assessment = "Moderately engaged contact"
        elif overall_score >= 40:
            assessment = "Low engagement contact"
        else:
            assessment = "Minimal or no engagement"
        
        # Identify key strengths
        strengths = []
        if recency_score >= 80:
            strengths.append("Recent activity")
        if frequency_score >= 70:
            strengths.append("Frequent interactions")
        if monetary_score >= 50:
            strengths.append("Revenue generating")
        if diversity_score >= 70:
            strengths.append("Diverse engagement types")
        
        # Identify improvement areas
        improvements = []
        if recency_score < 40:
            improvements.append("Re-engage soon - no recent activity")
        if frequency_score < 30:
            improvements.append("Increase interaction frequency")
        if monetary_score < 20:
            improvements.append("Focus on conversion opportunities")
        if diversity_score < 40:
            improvements.append("Encourage varied engagement types")
        
        # Engagement prediction
        if engagement_prob >= 0.7:
            prediction = "High likelihood of future engagement"
        elif engagement_prob >= 0.4:
            prediction = "Moderate chance of engagement"
        else:
            prediction = "Low engagement probability - needs attention"
        
        return {
            'overall_assessment': assessment,
            'key_strengths': strengths,
            'improvement_areas': improvements,
            'engagement_prediction': prediction,
            'score_breakdown': {
                'overall': f"{overall_score:.1f}/100",
                'recency': f"{recency_score:.1f}/100",
                'frequency': f"{frequency_score:.1f}/100",
                'monetary': f"{monetary_score:.1f}/100",
                'diversity': f"{diversity_score:.1f}/100",
                'probability': f"{engagement_prob:.2%}"
            }
        }
    
    def validate_calculation_inputs(self, contact_id: Optional[int], 
                                   campaign_id: Optional[int]) -> bool:
        """
        Validate inputs for score calculation.
        
        Args:
            contact_id: Contact ID to validate
            campaign_id: Campaign ID to validate
        
        Returns:
            True if inputs are valid
        
        Raises:
            ValueError: If inputs are invalid
        """
        if contact_id is None:
            raise ValueError("Contact ID cannot be None")
        
        if contact_id <= 0:
            raise ValueError("Contact ID must be positive")
        
        if campaign_id is None:
            raise ValueError("Campaign ID cannot be None")
        
        if campaign_id <= 0:
            raise ValueError("Campaign ID must be positive")
        
        return True
    
    def get_or_calculate_score(self, contact_id: int, campaign_id: int,
                               force_recalculate: bool = False,
                               max_age_hours: int = 24) -> EngagementScore:
        """
        Get existing score or calculate if needed.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
            force_recalculate: Force recalculation even if recent score exists
            max_age_hours: Maximum age before score is recalculated
        
        Returns:
            EngagementScore instance
        """
        try:
            if not force_recalculate:
                # Check for existing recent score
                existing_score = self.score_repository.get_by_contact_and_campaign(
                    contact_id, campaign_id
                )
                
                if existing_score:
                    # Check if score is recent enough
                    age_hours = (utc_now() - existing_score.calculated_at).total_seconds() / 3600
                    
                    if age_hours <= max_age_hours:
                        return existing_score
            
            # Calculate new score
            return self.calculate_engagement_score(contact_id, campaign_id)
            
        except Exception as e:
            logger.error(f"Error getting or calculating score: {e}")
            raise
    
    def predict_engagement_probability(self, contact_id: int, campaign_id: int) -> float:
        """
        Alias for calculate_engagement_probability for backward compatibility.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
        
        Returns:
            Engagement probability (0.0-1.0)
        """
        return self.calculate_engagement_probability(contact_id, campaign_id)
    
    # Internal methods that work with pre-fetched events to avoid redundant queries
    def _calculate_rfm_scores_with_events(self, events: List[EngagementEvent]) -> Dict[str, float]:
        """Internal RFM calculation using pre-fetched events."""
        if not events:
            return {
                'recency_score': 0.0,
                'frequency_score': 0.0,
                'monetary_score': 0.0
            }
        
        now = utc_now()
        
        # Calculate Recency Score
        most_recent_event = events[0]
        days_since_last = (now - most_recent_event.event_timestamp).days
        recency_score = 100.0 * math.exp(-days_since_last / 30.0)
        recency_score = max(0.0, min(100.0, recency_score))
        
        # Calculate Frequency Score
        if len(events) > 1:
            oldest_event = events[-1]
            time_span_days = max(1, (now - oldest_event.event_timestamp).days)
            events_per_day = len(events) / time_span_days
            frequency_score = min(100.0, events_per_day * 100.0)
        else:
            frequency_score = 10.0
        
        # Calculate Monetary Score
        total_value = Decimal('0')
        for event in events:
            if event.conversion_value:
                total_value += event.conversion_value
        
        if total_value > 0:
            monetary_score = min(100.0, 25.0 * math.log10(float(total_value) + 1))
        else:
            monetary_score = 0.0
        
        return {
            'recency_score': round(recency_score, 2),
            'frequency_score': round(frequency_score, 2),
            'monetary_score': round(monetary_score, 2)
        }
    
    def _calculate_time_decay_score_with_events(self, events: List[EngagementEvent], 
                                                decay_factor: float = 0.95) -> float:
        """Internal time-decay calculation using pre-fetched events."""
        if not events:
            return 0.0
        
        now = utc_now()
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for event in events:
            days_elapsed = (now - event.event_timestamp).days
            time_weight = math.pow(decay_factor, days_elapsed)
            event_weight = self.EVENT_TYPE_WEIGHTS.get(event.event_type, 1.0)
            combined_weight = time_weight * abs(event_weight)
            
            if event_weight >= 0:
                weighted_sum += combined_weight * event_weight
            else:
                weighted_sum -= combined_weight * abs(event_weight)
            
            weight_sum += combined_weight
        
        if weight_sum == 0:
            return 0.0
        
        normalized_score = (weighted_sum / (10.0 * weight_sum)) * 100.0
        return max(0.0, min(100.0, normalized_score))
    
    def _calculate_engagement_diversity_score_with_events(self, events: List[EngagementEvent]) -> float:
        """Internal diversity calculation using pre-fetched events."""
        if not events:
            return 0.0
        
        event_types = set()
        positive_types = set()
        
        for event in events:
            event_types.add(event.event_type)
            if event.event_type in self.POSITIVE_EVENTS:
                positive_types.add(event.event_type)
        
        max_positive_types = len(self.POSITIVE_EVENTS)
        
        if max_positive_types > 0:
            diversity_ratio = len(positive_types) / max_positive_types
            diversity_score = diversity_ratio * 100.0
        else:
            diversity_score = 0.0
        
        type_variety_bonus = min(20.0, len(event_types) * 4.0)
        has_negative = any(et in self.NEGATIVE_EVENTS for et in event_types)
        
        if has_negative:
            diversity_score *= 0.8
        
        final_score = min(100.0, diversity_score + type_variety_bonus)
        return round(final_score, 2)
    
    def _calculate_engagement_probability_with_events(self, events: List[EngagementEvent]) -> float:
        """Internal probability calculation using pre-fetched events."""
        if not events:
            return 0.1
        
        total_events = len(events)
        positive_events = sum(1 for e in events if e.event_type in self.POSITIVE_EVENTS)
        
        if total_events == 0:
            return 0.1
        
        base_rate = positive_events / total_events
        
        now = utc_now()
        most_recent = events[0]
        days_since_last = (now - most_recent.event_timestamp).days
        recency_factor = math.exp(-days_since_last / 30.0)
        
        recent_positive = any(
            e.event_type in self.POSITIVE_EVENTS and 
            (now - e.event_timestamp).days <= 7
            for e in events[:5]
        )
        
        if recent_positive:
            probability = base_rate * 0.7 + recency_factor * 0.3
        elif base_rate == 0:
            probability = 0.05 + recency_factor * 0.1
        else:
            probability = base_rate * 0.4 + recency_factor * 0.2 + 0.1
        
        has_opted_out = any(e.event_type == 'opted_out' for e in events)
        if has_opted_out:
            probability *= 0.1
        
        return max(0.0, min(1.0, probability))