"""
AB Test Result Repository - Handles A/B test variant assignments and performance tracking
Follows the repository pattern with Result-based error handling
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func, and_, or_
from scipy import stats
import hashlib
import logging

from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult
from services.common.result import Result
from crm_database import ABTestResult, Campaign, Contact

logger = logging.getLogger(__name__)


class ABTestResultRepository(BaseRepository[ABTestResult]):
    """
    Repository for managing A/B test results and variant assignments.
    
    Handles variant assignment tracking, performance metrics collection,
    and statistical analysis of A/B test results.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session and ABTestResult model."""
        super().__init__(session, ABTestResult)
    
    def _validate_variant(self, variant: Any) -> bool:
        """Validate that variant is either 'A' or 'B'."""
        return variant in ['A', 'B']
    
    def _validate_response_type(self, response_type: Any) -> bool:
        """Validate response type."""
        return response_type in ['positive', 'negative', 'neutral']
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[ABTestResult]:
        """
        Search AB test results by text query.
        
        Args:
            query: Search query string
            fields: Fields to search in (default: variant, response_type)
            
        Returns:
            List of matching AB test results
        """
        if not query:
            return []
        
        from sqlalchemy import or_
        
        search_fields = fields or ['variant', 'response_type']
        conditions = []
        
        for field in search_fields:
            if hasattr(ABTestResult, field):
                column = getattr(ABTestResult, field)
                if column is not None:
                    conditions.append(column.ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        try:
            return self.session.query(ABTestResult).filter(or_(*conditions)).all()
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def assign_variant(self, campaign_id: int, contact_id: int, variant: str) -> Result[ABTestResult]:
        """
        Assign a variant to a contact for a campaign.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant to assign ('A' or 'B')
            
        Returns:
            Result containing the assignment or error
        """
        try:
            # Validate variant
            if not self._validate_variant(variant):
                return Result.failure(
                    f"Invalid variant: {variant}. Must be 'A' or 'B'",
                    code="INVALID_VARIANT"
                )
            
            # Check for existing assignment
            existing = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                contact_id=contact_id
            ).first()
            
            if existing:
                # Return existing assignment - don't create duplicate
                return Result.success(existing)
            
            # Create new assignment
            assignment = ABTestResult(
                campaign_id=campaign_id,
                contact_id=contact_id,
                variant=variant,
                assigned_at=utc_now()
            )
            
            self.session.add(assignment)
            self.session.commit()
            
            return Result.success(assignment)
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error assigning variant: {e}")
            return Result.failure(
                f"Database connection error: {str(e)}",
                code="DB_ERROR"
            )
    
    def get_contact_variant(self, campaign_id: int, contact_id: int) -> Result[str]:
        """
        Get the assigned variant for a contact in a campaign.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            
        Returns:
            Result containing the variant ('A' or 'B') or error
        """
        try:
            assignment = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                contact_id=contact_id
            ).first()
            
            if not assignment:
                return Result.failure(
                    "Contact not assigned to any variant",
                    code="VARIANT_NOT_ASSIGNED"
                )
            
            return Result.success(assignment.variant)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting variant: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def get_campaign_assignments(self, campaign_id: int) -> Result[List[ABTestResult]]:
        """
        Get all variant assignments for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result containing list of assignments or error
        """
        try:
            assignments = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id
            ).all()
            
            return Result.success(assignments)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting assignments: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def get_variant_assignments(self, campaign_id: int, variant: str) -> Result[List[ABTestResult]]:
        """
        Get all assignments for a specific variant in a campaign.
        
        Args:
            campaign_id: Campaign ID
            variant: Variant ('A' or 'B')
            
        Returns:
            Result containing list of assignments or error
        """
        try:
            if not self._validate_variant(variant):
                return Result.failure(
                    f"Invalid variant: {variant}",
                    code="INVALID_VARIANT"
                )
            
            assignments = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                variant=variant
            ).all()
            
            return Result.success(assignments)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting variant assignments: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def track_message_sent(self, campaign_id: int, contact_id: int, variant: str, activity_id: int) -> Result[bool]:
        """
        Track that a message was sent to a contact.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant sent
            activity_id: Activity ID for the sent message
            
        Returns:
            Result indicating success or failure
        """
        try:
            assignment = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                contact_id=contact_id,
                variant=variant
            ).first()
            
            if not assignment:
                return Result.failure(
                    "Assignment not found for tracking",
                    code="ASSIGNMENT_NOT_FOUND"
                )
            
            assignment.message_sent = True
            assignment.sent_activity_id = activity_id
            assignment.sent_at = utc_now()
            
            self.session.commit()
            return Result.success(True)
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error tracking message sent: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def track_message_opened(self, campaign_id: int, contact_id: int, variant: str) -> Result[bool]:
        """
        Track that a message was opened by a contact.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant opened
            
        Returns:
            Result indicating success or failure
        """
        try:
            assignment = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                contact_id=contact_id,
                variant=variant
            ).first()
            
            if not assignment:
                return Result.failure(
                    "Assignment not found for tracking",
                    code="ASSIGNMENT_NOT_FOUND"
                )
            
            assignment.message_opened = True
            assignment.opened_at = utc_now()
            
            self.session.commit()
            return Result.success(True)
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error tracking message opened: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def track_link_clicked(self, campaign_id: int, contact_id: int, variant: str, link_url: str) -> Result[bool]:
        """
        Track that a link in the message was clicked.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant with clicked link
            link_url: URL that was clicked
            
        Returns:
            Result indicating success or failure
        """
        try:
            assignment = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                contact_id=contact_id,
                variant=variant
            ).first()
            
            if not assignment:
                return Result.failure(
                    "Assignment not found for tracking",
                    code="ASSIGNMENT_NOT_FOUND"
                )
            
            assignment.link_clicked = True
            assignment.clicked_link_url = link_url
            assignment.clicked_at = utc_now()
            
            self.session.commit()
            return Result.success(True)
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error tracking link clicked: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def track_response_received(self, campaign_id: int, contact_id: int, variant: str, 
                               response_type: str, activity_id: int) -> Result[bool]:
        """
        Track that a response was received from a contact.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: Variant that received response
            response_type: Type of response ('positive', 'negative', 'neutral')
            activity_id: Activity ID for the response
            
        Returns:
            Result indicating success or failure
        """
        try:
            # Validate response type
            if not self._validate_response_type(response_type):
                return Result.failure(
                    f"Invalid response type: {response_type}",
                    code="INVALID_RESPONSE_TYPE"
                )
            
            assignment = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                contact_id=contact_id,
                variant=variant
            ).first()
            
            if not assignment:
                return Result.failure(
                    "Assignment not found for tracking",
                    code="ASSIGNMENT_NOT_FOUND"
                )
            
            assignment.response_received = True
            assignment.response_type = response_type
            assignment.response_activity_id = activity_id
            assignment.responded_at = utc_now()
            
            self.session.commit()
            return Result.success(True)
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error tracking response: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def get_variant_metrics(self, campaign_id: int, variant: str) -> Result[Dict[str, Any]]:
        """
        Get aggregated metrics for a variant.
        
        Args:
            campaign_id: Campaign ID
            variant: Variant to get metrics for
            
        Returns:
            Result containing metrics dictionary or error
        """
        try:
            if not self._validate_variant(variant):
                return Result.failure(
                    f"Invalid variant: {variant}",
                    code="INVALID_VARIANT"
                )
            
            # Get all assignments for this variant
            assignments = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                variant=variant
            ).all()
            
            if not assignments:
                # Return zero metrics if no data
                return Result.success({
                    'messages_sent': 0,
                    'messages_opened': 0,
                    'links_clicked': 0,
                    'responses_received': 0,
                    'positive_responses': 0,
                    'negative_responses': 0,
                    'open_rate': 0.0,
                    'click_rate': 0.0,
                    'response_rate': 0.0,
                    'conversion_rate': 0.0
                })
            
            # Calculate metrics
            total = len(assignments)
            sent = sum(1 for a in assignments if a.message_sent)
            opened = sum(1 for a in assignments if a.message_opened)
            clicked = sum(1 for a in assignments if a.link_clicked)
            responded = sum(1 for a in assignments if a.response_received)
            positive = sum(1 for a in assignments if a.response_received and a.response_type == 'positive')
            negative = sum(1 for a in assignments if a.response_received and a.response_type == 'negative')
            
            # Calculate rates (avoid division by zero)
            open_rate = opened / sent if sent > 0 else 0.0
            click_rate = clicked / sent if sent > 0 else 0.0
            response_rate = responded / sent if sent > 0 else 0.0
            conversion_rate = positive / sent if sent > 0 else 0.0
            
            metrics = {
                'messages_sent': sent,
                'messages_opened': opened,
                'links_clicked': clicked,
                'responses_received': responded,
                'positive_responses': positive,
                'negative_responses': negative,
                'open_rate': open_rate,
                'click_rate': click_rate,
                'response_rate': response_rate,
                'conversion_rate': conversion_rate
            }
            
            return Result.success(metrics)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting variant metrics: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def get_campaign_ab_summary(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Get complete A/B test summary for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result containing summary with both variants' metrics and winner analysis
        """
        try:
            # Get metrics for both variants
            variant_a_result = self.get_variant_metrics(campaign_id, 'A')
            variant_b_result = self.get_variant_metrics(campaign_id, 'B')
            
            if variant_a_result.is_failure:
                return variant_a_result
            if variant_b_result.is_failure:
                return variant_b_result
            
            variant_a_metrics = variant_a_result.data
            variant_b_metrics = variant_b_result.data
            
            # Determine winner and calculate statistical significance
            winner = None
            confidence_level = 0.0
            significant_difference = False
            
            # Only calculate if we have data for both variants
            if variant_a_metrics['messages_sent'] > 0 and variant_b_metrics['messages_sent'] > 0:
                # Use positive responses for chi-square test
                a_positive = variant_a_metrics['positive_responses']
                a_total = variant_a_metrics['messages_sent']
                b_positive = variant_b_metrics['positive_responses']
                b_total = variant_b_metrics['messages_sent']
                
                # Determine winner based on conversion rates regardless of sample size
                if variant_a_metrics['conversion_rate'] > variant_b_metrics['conversion_rate']:
                    winner = 'A'
                elif variant_b_metrics['conversion_rate'] > variant_a_metrics['conversion_rate']:
                    winner = 'B'
                # else winner remains None (tied)
                
                # Create contingency table for chi-square test
                # [[variant_a_success, variant_a_failure], [variant_b_success, variant_b_failure]]
                contingency_table = [
                    [a_positive, a_total - a_positive],
                    [b_positive, b_total - b_positive]
                ]
                
                # Perform chi-square test if we have enough data
                if a_total >= 10 and b_total >= 10:  # Minimum sample size
                    try:
                        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
                        confidence_level = 1 - p_value
                        
                        # Check if difference is significant (p < 0.05 means 95% confidence)
                        if p_value < 0.05:
                            significant_difference = True
                    except Exception as e:
                        logger.warning(f"Statistical test failed: {e}")
                else:
                    # Not enough data for statistical significance, but still show metrics
                    # For small samples, assume significance if the difference is large enough
                    rate_diff = abs(variant_a_metrics['conversion_rate'] - variant_b_metrics['conversion_rate'])
                    if rate_diff > 0.2:  # 20% difference threshold for small samples
                        significant_difference = True
                        confidence_level = 0.8  # Lower confidence for small samples
            
            # Add statistical confidence to variant metrics
            variant_a_metrics['statistical_confidence'] = confidence_level if winner == 'A' else 1 - confidence_level
            variant_b_metrics['statistical_confidence'] = confidence_level if winner == 'B' else 1 - confidence_level
            
            summary = {
                'variant_a': variant_a_metrics,
                'variant_b': variant_b_metrics,
                'winner': winner,
                'confidence_level': confidence_level,
                'significant_difference': significant_difference
            }
            
            return Result.success(summary)
            
        except Exception as e:
            logger.error(f"Error generating campaign summary: {e}")
            return Result.failure(
                f"Error generating summary: {str(e)}",
                code="SUMMARY_ERROR"
            )
    
    def bulk_assign_variants(self, assignments: List[Dict[str, Any]]) -> Result[int]:
        """
        Bulk assign variants to multiple contacts.
        
        Args:
            assignments: List of assignment dictionaries with campaign_id, contact_id, variant
            
        Returns:
            Result containing number of assignments created or error
        """
        try:
            # Prepare assignment objects
            for assignment_data in assignments:
                assignment_data['assigned_at'] = utc_now()
            
            # Bulk insert
            self.session.bulk_insert_mappings(ABTestResult, assignments)
            self.session.commit()
            
            return Result.success(len(assignments))
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Bulk assignment error: {e}")
            return Result.failure(
                f"Bulk insert failed: {str(e)}",
                code="BULK_OPERATION_ERROR"
            )
    
    def bulk_update_metrics(self, updates: List[Dict[str, Any]]) -> Result[int]:
        """
        Bulk update metrics for multiple assignments.
        
        Args:
            updates: List of update dictionaries with id and fields to update
            
        Returns:
            Result containing number of records updated or error
        """
        try:
            self.session.bulk_update_mappings(ABTestResult, updates)
            self.session.commit()
            
            return Result.success(len(updates))
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Bulk update error: {e}")
            return Result.failure(
                f"Bulk update failed: {str(e)}",
                code="BULK_OPERATION_ERROR"
            )
    
    def get_time_series_metrics(self, campaign_id: int, variant: str, 
                               start_date: datetime, end_date: datetime) -> Result[Dict[str, Any]]:
        """
        Get time series metrics for a variant over a date range.
        
        Args:
            campaign_id: Campaign ID
            variant: Variant to analyze
            start_date: Start date
            end_date: End date
            
        Returns:
            Result containing time series data or error
        """
        try:
            assignments = self.session.query(ABTestResult).filter_by(
                campaign_id=campaign_id,
                variant=variant
            ).filter(
                ABTestResult.sent_at >= start_date,
                ABTestResult.sent_at <= end_date
            ).order_by(ABTestResult.sent_at).all()
            
            # Group by day and calculate metrics
            daily_metrics = {}
            cumulative_metrics = {
                'sent': 0,
                'opened': 0,
                'clicked': 0,
                'responded': 0
            }
            
            for assignment in assignments:
                if assignment.sent_at:
                    date_key = assignment.sent_at.date().isoformat()
                    
                    if date_key not in daily_metrics:
                        daily_metrics[date_key] = {
                            'sent': 0,
                            'opened': 0,
                            'clicked': 0,
                            'responded': 0
                        }
                    
                    if assignment.message_sent:
                        daily_metrics[date_key]['sent'] += 1
                        cumulative_metrics['sent'] += 1
                    
                    if assignment.message_opened:
                        daily_metrics[date_key]['opened'] += 1
                        cumulative_metrics['opened'] += 1
                    
                    if assignment.link_clicked:
                        daily_metrics[date_key]['clicked'] += 1
                        cumulative_metrics['clicked'] += 1
                    
                    if assignment.response_received:
                        daily_metrics[date_key]['responded'] += 1
                        cumulative_metrics['responded'] += 1
            
            return Result.success({
                'daily_metrics': daily_metrics,
                'cumulative_metrics': cumulative_metrics
            })
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting time series metrics: {e}")
            return Result.failure(
                f"Database error: {str(e)}",
                code="DB_ERROR"
            )
    
    def cleanup_orphaned_assignments(self) -> Result[int]:
        """
        Clean up assignments for deleted campaigns or contacts.
        
        Returns:
            Result containing number of records deleted or error
        """
        try:
            # Find orphaned assignments
            orphaned = self.session.query(ABTestResult).outerjoin(
                Campaign, ABTestResult.campaign_id == Campaign.id
            ).outerjoin(
                Contact, ABTestResult.contact_id == Contact.id
            ).filter(
                or_(Campaign.id.is_(None), Contact.id.is_(None))
            ).delete(synchronize_session=False)
            
            self.session.commit()
            
            return Result.success(orphaned)
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error cleaning up orphaned assignments: {e}")
            return Result.failure(
                f"Cleanup failed: {str(e)}",
                code="CLEANUP_ERROR"
            )
