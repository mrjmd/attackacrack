"""
A/B Testing Service - Manages A/B test campaigns and variant performance tracking
Implements deterministic variant assignment and statistical significance testing
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
import logging
from scipy import stats
import numpy as np

from services.common.result import Result
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.ab_test_result_repository import ABTestResultRepository
# Services should not import database models directly - removed imports

logger = logging.getLogger(__name__)


class ABTestingService:
    """
    Service for managing A/B test campaigns.
    
    Handles campaign creation, variant assignment, performance tracking,
    statistical analysis, and winner selection.
    """
    
    def __init__(self, campaign_repository: CampaignRepository,
                 contact_repository: ContactRepository,
                 ab_result_repository: ABTestResultRepository):
        """
        Initialize service with required repositories.
        
        Args:
            campaign_repository: Repository for campaign operations
            contact_repository: Repository for contact operations
            ab_result_repository: Repository for A/B test results
        """
        self.campaign_repository = campaign_repository
        self.contact_repository = contact_repository
        self.ab_result_repository = ab_result_repository
    
    def create_ab_campaign(self, campaign_data: Dict[str, Any]) -> Result[Any]:
        """
        Create a new A/B test campaign.
        
        Args:
            campaign_data: Campaign data including template_a, template_b, and ab_config
            
        Returns:
            Result containing the created campaign or error
        """
        # Validate required fields for A/B test
        if 'template_a' not in campaign_data:
            return Result.failure(
                "template_a is required for A/B test campaign",
                code="MISSING_VARIANT_A"
            )
        
        if 'template_b' not in campaign_data:
            return Result.failure(
                "template_b is required for A/B test campaign",
                code="MISSING_VARIANT_B"
            )
        
        if not campaign_data.get('template_a'):
            return Result.failure(
                "Variant A cannot be empty",
                code="EMPTY_VARIANT_A"
            )
        
        if not campaign_data.get('template_b'):
            return Result.failure(
                "Variant B cannot be empty",
                code="EMPTY_VARIANT_B"
            )
        
        if 'ab_config' not in campaign_data:
            return Result.failure(
                "ab_config is required for A/B test campaign",
                code="MISSING_AB_CONFIG"
            )
        
        # Validate split ratio if provided
        ab_config = campaign_data['ab_config']
        split_ratio = ab_config.get('split_ratio', 50)
        
        if not 1 <= split_ratio <= 99:
            return Result.failure(
                "split_ratio must be between 1 and 99",
                code="INVALID_SPLIT_RATIO"
            )
        
        # Set campaign type
        campaign_data['campaign_type'] = 'ab_test'
        
        # Create campaign
        return self.campaign_repository.create(campaign_data)
    
    def _get_deterministic_variant(self, campaign_id: int, contact_id: int, split_ratio: int) -> str:
        """
        Deterministically assign a variant based on campaign and contact IDs.
        
        Uses hash to ensure same contact always gets same variant for a campaign.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            split_ratio: Percentage for variant A (1-99)
            
        Returns:
            'A' or 'B' based on deterministic assignment
        """
        # Create deterministic hash
        hash_input = f"{campaign_id}:{contact_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        
        # Map to 0-99 range
        assignment_value = hash_value % 100
        
        # Assign based on split ratio
        return 'A' if assignment_value < split_ratio else 'B'
    
    def assign_recipients_to_variants(self, campaign_id: int, contacts: List[Any]) -> Result[List[Dict[str, Any]]]:
        """
        Assign recipients to A/B test variants.
        
        Args:
            campaign_id: Campaign ID
            contacts: List of contacts to assign
            
        Returns:
            Result containing list of assignments or error
        """
        if not contacts:
            return Result.success([])
        
        # Get campaign to check ab_config
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return Result.failure(
                f"Campaign not found: {campaign_id}",
                code="CAMPAIGN_NOT_FOUND"
            )
        
        ab_config = getattr(campaign, 'ab_config', {}) or {}
        split_ratio = ab_config.get('split_ratio', 50)
        
        assignments = []
        
        for contact in contacts:
            # Determine variant deterministically
            variant = self._get_deterministic_variant(campaign_id, contact.id, split_ratio)
            
            # Assign variant in repository
            assign_result = self.ab_result_repository.assign_variant(
                campaign_id, contact.id, variant
            )
            
            if assign_result.is_success:
                assignments.append({
                    'contact_id': contact.id,
                    'variant': variant,
                    'campaign_id': campaign_id
                })
        
        return Result.success(assignments)
    
    def get_contact_variant(self, campaign_id: int, contact_id: int) -> Result[str]:
        """
        Get the assigned variant for a contact in a campaign.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            
        Returns:
            Result containing the variant ('A' or 'B') or error
        """
        return self.ab_result_repository.get_contact_variant(campaign_id, contact_id)
    
    def track_message_sent(self, campaign_id: int, contact_id: int, variant: str, activity_id: int) -> Result[bool]:
        """
        Track that a message was sent.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant sent
            activity_id: Activity ID for the sent message
            
        Returns:
            Result indicating success or failure
        """
        return self.ab_result_repository.track_message_sent(
            campaign_id, contact_id, variant, activity_id
        )
    
    def track_message_opened(self, campaign_id: int, contact_id: int, variant: str) -> Result[bool]:
        """
        Track that a message was opened.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant opened
            
        Returns:
            Result indicating success or failure
        """
        return self.ab_result_repository.track_message_opened(
            campaign_id, contact_id, variant
        )
    
    def track_link_clicked(self, campaign_id: int, contact_id: int, variant: str, link_url: str) -> Result[bool]:
        """
        Track that a link was clicked.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant with clicked link
            link_url: URL that was clicked
            
        Returns:
            Result indicating success or failure
        """
        return self.ab_result_repository.track_link_clicked(
            campaign_id, contact_id, variant, link_url
        )
    
    def track_response_received(self, campaign_id: int, contact_id: int, variant: str,
                               response_type: str, activity_id: int) -> Result[bool]:
        """
        Track that a response was received.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant that received response
            response_type: Type of response ('positive', 'negative', 'neutral')
            activity_id: Activity ID for the response
            
        Returns:
            Result indicating success or failure
        """
        return self.ab_result_repository.track_response_received(
            campaign_id, contact_id, variant, response_type, activity_id
        )
    
    def get_variant_metrics(self, campaign_id: int, variant: str) -> Result[Dict[str, Any]]:
        """
        Get performance metrics for a variant.
        
        Args:
            campaign_id: Campaign ID
            variant: Variant to get metrics for
            
        Returns:
            Result containing metrics dictionary or error
        """
        return self.ab_result_repository.get_variant_metrics(campaign_id, variant)
    
    def get_campaign_ab_summary(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Get complete A/B test summary for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result containing summary with both variants' metrics and winner analysis
        """
        return self.ab_result_repository.get_campaign_ab_summary(campaign_id)
    
    def calculate_statistical_significance(self, variant_a_data: Dict[str, int], 
                                         variant_b_data: Dict[str, int]) -> Result[Dict[str, Any]]:
        """
        Calculate statistical significance between two variants.
        
        Args:
            variant_a_data: Data for variant A (messages_sent, conversions)
            variant_b_data: Data for variant B (messages_sent, conversions)
            
        Returns:
            Result containing significance analysis
        """
        try:
            a_sent = variant_a_data.get('messages_sent', 0)
            a_conversions = variant_a_data.get('conversions', 0)
            b_sent = variant_b_data.get('messages_sent', 0)
            b_conversions = variant_b_data.get('conversions', 0)
            
            # Check for minimum sample size
            min_sample_size = 30  # Statistical minimum for meaningful results
            if a_sent < min_sample_size or b_sent < min_sample_size:
                return Result.success({
                    'p_value': 1.0,
                    'confidence_level': 0.0,
                    'significant': False,
                    'insufficient_sample_size': True,
                    'winner': None
                })
            
            # Calculate conversion rates
            a_rate = a_conversions / a_sent if a_sent > 0 else 0
            b_rate = b_conversions / b_sent if b_sent > 0 else 0
            
            # If rates are identical, no significance
            if a_rate == b_rate:
                return Result.success({
                    'p_value': 1.0,
                    'confidence_level': 0.0,
                    'significant': False,
                    'winner': None
                })
            
            # Create contingency table for chi-square test
            contingency_table = [
                [a_conversions, a_sent - a_conversions],
                [b_conversions, b_sent - b_conversions]
            ]
            
            # Perform chi-square test
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
            confidence_level = 1 - p_value
            
            # Determine if significant (95% confidence level)
            significant = p_value < 0.05
            
            # Determine winner
            winner = None
            if a_rate > b_rate:
                winner = 'A'
            elif b_rate > a_rate:
                winner = 'B'
            
            return Result.success({
                'p_value': p_value,
                'confidence_level': confidence_level,
                'significant': significant,
                'winner': winner,
                'insufficient_sample_size': False,
                'variant_a_rate': a_rate,
                'variant_b_rate': b_rate
            })
            
        except Exception as e:
            logger.error(f"Error calculating statistical significance: {e}")
            return Result.failure(
                f"Statistical calculation error: {str(e)}",
                code="STATS_ERROR"
            )
    
    def identify_winner(self, campaign_id: int, confidence_threshold: float = 0.95) -> Result[Dict[str, Any]]:
        """
        Identify the winning variant based on performance.
        
        Args:
            campaign_id: Campaign ID
            confidence_threshold: Required confidence level (default 95%)
            
        Returns:
            Result containing winner information or error
        """
        # Get campaign summary
        summary_result = self.get_campaign_ab_summary(campaign_id)
        if summary_result.is_failure:
            return summary_result
        
        summary = summary_result.data
        
        # Check for no responses scenario
        if (summary['variant_a'].get('responses_received', 0) == 0 and 
            summary['variant_b'].get('responses_received', 0) == 0):
            return Result.success({
                'winner': None,
                'reason': 'no_responses',
                'confidence_level': 0.0,
                'automatic': True
            })
        
        # Check for tied results
        if summary['variant_a']['conversion_rate'] == summary['variant_b']['conversion_rate']:
            return Result.success({
                'winner': None,
                'reason': 'tied_results',
                'confidence_level': 0.0,
                'automatic': True
            })
        
        # Check if winner meets confidence threshold
        if summary['confidence_level'] >= confidence_threshold and summary['significant_difference']:
            winner_data = {
                'winner': summary['winner'],
                'confidence_level': summary['confidence_level'],
                'automatic': True,
                'variant_a_conversion': summary['variant_a']['conversion_rate'],
                'variant_b_conversion': summary['variant_b']['conversion_rate']
            }
            
            # Update campaign with winner
            updated_campaign = self.campaign_repository.update_by_id(
                campaign_id, ab_winner=summary['winner'], ab_winner_data=winner_data
            )
            
            if not updated_campaign:
                logger.warning(f"Failed to update campaign winner for campaign {campaign_id}")
            
            return Result.success(winner_data)
        else:
            return Result.success({
                'winner': None,
                'reason': 'insufficient_confidence',
                'confidence_level': summary['confidence_level'],
                'automatic': True
            })
    
    def set_manual_winner(self, campaign_id: int, winner: str, override_reason: str) -> Result[Dict[str, Any]]:
        """
        Manually set the winner of an A/B test.
        
        Args:
            campaign_id: Campaign ID
            winner: Winning variant ('A' or 'B')
            override_reason: Reason for manual override
            
        Returns:
            Result containing winner information or error
        """
        if winner not in ['A', 'B']:
            return Result.failure(
                f"Invalid winner: {winner}. Must be 'A' or 'B'",
                code="INVALID_WINNER"
            )
        
        winner_data = {
            'winner': winner,
            'automatic': False,
            'override_reason': override_reason,
            'manual_override': True
        }
        
        # Update campaign with manual winner
        updated_campaign = self.campaign_repository.update_by_id(
            campaign_id, ab_winner=winner, ab_winner_data=winner_data
        )
        
        if not updated_campaign:
            return Result.failure(
                f"Failed to update campaign {campaign_id} with manual winner",
                code="UPDATE_FAILED"
            )
        
        return Result.success(winner_data)
    
    def send_winner_to_remaining(self, campaign_id: int, winning_variant: str) -> Result[Dict[str, Any]]:
        """
        Send the winning variant to remaining recipients.
        
        Args:
            campaign_id: Campaign ID
            winning_variant: The winning variant to send ('A' or 'B')
            
        Returns:
            Result containing information about scheduled sends
        """
        # Get remaining recipients who haven't received any message
        # For now, return a placeholder - this would need to be implemented properly
        # by getting campaign members and filtering out those who already received messages
        remaining_contacts = []
        
        # Get campaign to get the winning template
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return Result.failure(
                f"Campaign {campaign_id} not found",
                code="CAMPAIGN_NOT_FOUND"
            )
        
        # Schedule sends for remaining recipients
        scheduled_sends = []
        for contact in remaining_contacts:
            scheduled_sends.append({
                'contact_id': contact.id,
                'variant': winning_variant,
                'template': getattr(campaign, f'template_{winning_variant.lower()}', '')
            })
        
        return Result.success({
            'variant_sent': winning_variant,
            'recipients_count': len(remaining_contacts),
            'scheduled_sends': scheduled_sends
        })
    
    def generate_ab_test_report(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Generate comprehensive A/B test report.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result containing detailed report or error
        """
        # Get campaign details
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return Result.failure(
                f"Campaign {campaign_id} not found",
                code="CAMPAIGN_NOT_FOUND"
            )
        
        # Get A/B test summary
        summary_result = self.get_campaign_ab_summary(campaign_id)
        if summary_result.is_failure:
            return summary_result
        
        summary = summary_result.data
        
        # Calculate test duration
        created_at = getattr(campaign, 'created_at', None) or datetime.utcnow()
        test_duration_days = (datetime.utcnow() - created_at).days
        
        # Generate recommendations
        recommendations = []
        
        if summary['winner']:
            recommendations.append(
                f"Variant {summary['winner']} is the clear winner with "
                f"{summary['confidence_level']:.1%} confidence. "
                f"Consider using this variant for future campaigns."
            )
        elif summary['variant_a']['messages_sent'] < 100 or summary['variant_b']['messages_sent'] < 100:
            recommendations.append(
                "Continue test to gather more data. "
                "At least 100 messages per variant recommended for reliable results."
            )
        else:
            recommendations.append(
                "No significant difference detected between variants. "
                "Consider testing more distinct variations."
            )
        
        # Determine test status
        test_status = 'completed' if summary['winner'] else 'ongoing'
        if getattr(campaign, 'status', '') == 'running':
            test_status = 'ongoing'
        
        report = {
            'campaign_info': {
                'id': campaign_id,
                'name': getattr(campaign, 'name', 'Unknown'),
                'created_at': created_at.isoformat(),
                'status': getattr(campaign, 'status', 'unknown')
            },
            'test_duration_days': test_duration_days,
            'variant_performance': {
                'variant_a': summary['variant_a'],
                'variant_b': summary['variant_b']
            },
            'statistical_analysis': {
                'winner': summary['winner'],
                'confidence_level': summary['confidence_level'],
                'significant_difference': summary['significant_difference'],
                'test_status': test_status
            },
            'recommendations': recommendations
        }
        
        return Result.success(report)
