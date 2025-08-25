"""
EngagementScoreRepository - Data access layer for EngagementScore entities
Handles all database operations for engagement scoring and analytics
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, and_, or_, desc, asc, String, case
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import EngagementScore, Contact, Campaign
from utils.datetime_utils import utc_now, ensure_utc
import logging
import statistics

logger = logging.getLogger(__name__)


class EngagementScoreRepository(BaseRepository[EngagementScore]):
    """Repository for EngagementScore data access"""
    
    def __init__(self, session: Session):
        """Initialize repository with database session"""
        super().__init__(session, EngagementScore)
    
    def create(self, **kwargs) -> EngagementScore:
        """
        Create a new engagement score with validation.
        
        Args:
            **kwargs: Score attributes including:
                - contact_id: Required contact ID
                - campaign_id: Optional campaign ID
                - overall_score: Required overall engagement score
                - calculated_at: Timestamp of calculation
                - score_version: Version of scoring algorithm
                - Additional scoring components
        
        Returns:
            Created EngagementScore instance
        
        Raises:
            ValueError: If engagement_probability is not between 0 and 1
            SQLAlchemyError: If database operation fails
        """
        # Validate engagement probability
        if 'engagement_probability' in kwargs:
            prob = kwargs['engagement_probability']
            if prob is not None and (prob < 0 or prob > 1):
                raise ValueError("Engagement probability must be between 0 and 1")
        
        # Validate conversion probability
        if 'conversion_probability' in kwargs:
            prob = kwargs['conversion_probability']
            if prob is not None and (prob < 0 or prob > 1):
                raise ValueError("Conversion probability must be between 0 and 1")
        
        # Ensure timestamp is UTC
        if 'calculated_at' in kwargs:
            kwargs['calculated_at'] = ensure_utc(kwargs['calculated_at'])
        else:
            kwargs['calculated_at'] = utc_now()
        
        # Set default values for optional scores
        kwargs.setdefault('recency_score', 0)
        kwargs.setdefault('frequency_score', 0)
        kwargs.setdefault('monetary_score', 0)
        kwargs.setdefault('engagement_probability', 0)
        
        try:
            return super().create(**kwargs)
        except IntegrityError as e:
            logger.error(f"Integrity error creating engagement score: {e}")
            self.session.rollback()
            raise
    
    def update(self, entity: EngagementScore, **updates) -> EngagementScore:
        """
        Update an existing engagement score.
        
        Args:
            entity: EngagementScore to update
            **updates: Field-value pairs to update
        
        Returns:
            Updated EngagementScore instance
        
        Raises:
            ValueError: If probability values are invalid
            SQLAlchemyError: If database operation fails
        """
        # Validate probabilities if being updated
        if 'engagement_probability' in updates:
            prob = updates['engagement_probability']
            if prob is not None and (prob < 0 or prob > 1):
                raise ValueError("Engagement probability must be between 0 and 1")
        
        if 'conversion_probability' in updates:
            prob = updates['conversion_probability']
            if prob is not None and (prob < 0 or prob > 1):
                raise ValueError("Conversion probability must be between 0 and 1")
        
        # Ensure timestamp is UTC if being updated
        if 'calculated_at' in updates:
            updates['calculated_at'] = ensure_utc(updates['calculated_at'])
        
        return super().update(entity, **updates)
    
    def get_by_contact_and_campaign(self, contact_id: int, campaign_id: int) -> Optional[EngagementScore]:
        """
        Get engagement score for a specific contact and campaign combination.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
        
        Returns:
            EngagementScore instance or None if not found
        """
        try:
            return self.session.query(EngagementScore).filter(
                and_(
                    EngagementScore.contact_id == contact_id,
                    EngagementScore.campaign_id == campaign_id
                )
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting score for contact {contact_id} and campaign {campaign_id}: {e}")
            return None
    
    def get_latest_score_for_contact(self, contact_id: int) -> Optional[EngagementScore]:
        """
        Get the most recent engagement score for a contact across all campaigns.
        
        Args:
            contact_id: Contact ID
        
        Returns:
            Most recent EngagementScore instance or None
        """
        try:
            return self.session.query(EngagementScore).filter(
                EngagementScore.contact_id == contact_id
            ).order_by(desc(EngagementScore.calculated_at)).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting latest score for contact {contact_id}: {e}")
            return None
    
    def get_all_scores_for_contact(self, contact_id: int) -> List[EngagementScore]:
        """
        Get all engagement scores for a contact.
        
        Args:
            contact_id: Contact ID
        
        Returns:
            List of EngagementScore instances ordered by calculation time desc
        """
        try:
            return self.session.query(EngagementScore).filter(
                EngagementScore.contact_id == contact_id
            ).order_by(desc(EngagementScore.calculated_at)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all scores for contact {contact_id}: {e}")
            return []
    
    def get_scores_for_campaign(self, campaign_id: int) -> List[EngagementScore]:
        """
        Get all engagement scores for a specific campaign.
        
        Args:
            campaign_id: Campaign ID
        
        Returns:
            List of EngagementScore instances
        """
        try:
            return self.session.query(EngagementScore).filter(
                EngagementScore.campaign_id == campaign_id
            ).order_by(desc(EngagementScore.overall_score)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting scores for campaign {campaign_id}: {e}")
            return []
    
    def calculate_percentile_ranks(self, campaign_id: int) -> Dict[int, Dict[str, float]]:
        """
        Calculate percentile rankings for all contacts in a campaign.
        
        Args:
            campaign_id: Campaign ID
        
        Returns:
            Dictionary mapping contact_id to their percentile ranks
        """
        try:
            # Get all scores for the campaign
            scores = self.session.query(
                EngagementScore.contact_id,
                EngagementScore.overall_score
            ).filter(
                EngagementScore.campaign_id == campaign_id
            ).all()
            
            if not scores:
                return {}
            
            # Sort scores
            sorted_scores = sorted(scores, key=lambda x: x.overall_score)
            total_count = len(sorted_scores)
            
            # Calculate percentiles
            percentiles = {}
            for index, (contact_id, score) in enumerate(sorted_scores):
                # Calculate percentile (0-100)
                percentile = ((index + 1) / total_count) * 100
                percentiles[contact_id] = {
                    'overall_score': float(score),
                    'percentile': percentile
                }
            
            return percentiles
        except SQLAlchemyError as e:
            logger.error(f"Error calculating percentile ranks for campaign {campaign_id}: {e}")
            return {}
    
    def get_top_scored_contacts(self, campaign_id: int, limit: int = 10) -> List[EngagementScore]:
        """
        Get the top-scored contacts for a campaign.
        
        Args:
            campaign_id: Campaign ID
            limit: Number of top contacts to return (default: 10)
        
        Returns:
            List of EngagementScore instances ordered by score descending
        """
        try:
            return self.session.query(EngagementScore).filter(
                EngagementScore.campaign_id == campaign_id
            ).order_by(desc(EngagementScore.overall_score)).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting top scored contacts for campaign {campaign_id}: {e}")
            return []
    
    def get_score_distribution(self, campaign_id: int) -> Dict[str, float]:
        """
        Get statistical distribution of scores for a campaign.
        
        Args:
            campaign_id: Campaign ID
        
        Returns:
            Dictionary with min, max, mean, median, std_dev, and count
        """
        try:
            # Get all scores
            scores_query = self.session.query(EngagementScore.overall_score).filter(
                EngagementScore.campaign_id == campaign_id
            )
            
            scores = [float(score[0]) for score in scores_query.all()]
            
            if not scores:
                return {
                    'min': 0,
                    'max': 0,
                    'mean': 0,
                    'median': 0,
                    'std_dev': 0,
                    'count': 0
                }
            
            # Calculate statistics
            return {
                'min': min(scores),
                'max': max(scores),
                'mean': statistics.mean(scores),
                'median': statistics.median(scores),
                'std_dev': statistics.stdev(scores) if len(scores) > 1 else 0,
                'count': len(scores)
            }
        except Exception as e:
            logger.error(f"Error calculating score distribution for campaign {campaign_id}: {e}")
            return {
                'min': 0,
                'max': 0,
                'mean': 0,
                'median': 0,
                'std_dev': 0,
                'count': 0
            }
    
    def get_scores_needing_update(self, max_age_hours: int = 48) -> List[EngagementScore]:
        """
        Find scores that are stale and need recalculation.
        
        Args:
            max_age_hours: Maximum age in hours before score is considered stale
        
        Returns:
            List of EngagementScore instances that need updating
        """
        try:
            cutoff_time = utc_now() - timedelta(hours=max_age_hours)
            
            return self.session.query(EngagementScore).filter(
                EngagementScore.calculated_at < cutoff_time
            ).order_by(asc(EngagementScore.calculated_at)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting scores needing update: {e}")
            return []
    
    def bulk_update_scores(self, updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update multiple engagement scores.
        
        Args:
            updates: List of dictionaries containing score_id and update fields
        
        Returns:
            Number of scores updated
        
        Raises:
            ValueError: If any probability values are invalid
        """
        try:
            updated_count = 0
            
            for update_data in updates:
                score_id = update_data.pop('score_id', None)
                if not score_id:
                    continue
                
                # Validate probabilities
                if 'engagement_probability' in update_data:
                    prob = update_data['engagement_probability']
                    if prob is not None and (prob < 0 or prob > 1):
                        raise ValueError(f"Invalid engagement probability for score {score_id}")
                
                if 'conversion_probability' in update_data:
                    prob = update_data['conversion_probability']
                    if prob is not None and (prob < 0 or prob > 1):
                        raise ValueError(f"Invalid conversion probability for score {score_id}")
                
                # Ensure timestamp is UTC
                if 'calculated_at' in update_data:
                    update_data['calculated_at'] = ensure_utc(update_data['calculated_at'])
                
                # Update the score
                score = self.get_by_id(score_id)
                if score:
                    self.update(score, **update_data)
                    updated_count += 1
            
            self.session.flush()
            logger.info(f"Bulk updated {updated_count} engagement scores")
            
            return updated_count
        except Exception as e:
            logger.error(f"Error bulk updating scores: {e}")
            self.session.rollback()
            return 0
    
    def delete_scores_older_than(self, cutoff_date: datetime) -> int:
        """
        Delete scores older than a specified date for data retention.
        
        Args:
            cutoff_date: Date before which scores should be deleted
        
        Returns:
            Number of deleted scores
        """
        try:
            cutoff_date = ensure_utc(cutoff_date)
            
            # Get scores to delete
            scores_to_delete = self.session.query(EngagementScore).filter(
                EngagementScore.calculated_at < cutoff_date
            ).all()
            
            count = len(scores_to_delete)
            
            # Delete scores
            for score in scores_to_delete:
                self.session.delete(score)
            
            self.session.flush()
            logger.info(f"Deleted {count} engagement scores older than {cutoff_date}")
            
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error deleting old engagement scores: {e}")
            self.session.rollback()
            return 0
    
    def get_average_scores_by_segment(self, campaign_id: int, segment_field: str) -> Dict[str, Dict[str, float]]:
        """
        Calculate average scores grouped by contact segments.
        
        Args:
            campaign_id: Campaign ID
            segment_field: Field name in contact metadata to segment by
        
        Returns:
            Dictionary mapping segment values to average scores
        """
        try:
            # Join with Contact table to access metadata
            results = self.session.query(
                func.json_extract(Contact.contact_metadata, f'$.{segment_field}').label('segment'),
                func.avg(EngagementScore.overall_score).label('avg_overall'),
                func.avg(EngagementScore.recency_score).label('avg_recency'),
                func.avg(EngagementScore.frequency_score).label('avg_frequency'),
                func.avg(EngagementScore.monetary_score).label('avg_monetary'),
                func.count(EngagementScore.id).label('count')
            ).join(
                Contact, EngagementScore.contact_id == Contact.id
            ).filter(
                EngagementScore.campaign_id == campaign_id
            ).group_by('segment').all()
            
            # Format results
            segment_averages = {}
            for segment, avg_overall, avg_recency, avg_frequency, avg_monetary, count in results:
                if segment:
                    segment_averages[segment] = {
                        'avg_overall_score': float(avg_overall) if avg_overall else 0,
                        'avg_recency_score': float(avg_recency) if avg_recency else 0,
                        'avg_frequency_score': float(avg_frequency) if avg_frequency else 0,
                        'avg_monetary_score': float(avg_monetary) if avg_monetary else 0,
                        'count': count
                    }
            
            return segment_averages
        except Exception as e:
            logger.error(f"Error calculating average scores by segment: {e}")
            return {}
    
    def upsert_score(self, contact_id: int, campaign_id: int, **score_data) -> EngagementScore:
        """
        Insert or update an engagement score.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
            **score_data: Score attributes to insert or update
        
        Returns:
            Created or updated EngagementScore instance
        """
        try:
            # Check if score exists
            existing_score = self.get_by_contact_and_campaign(contact_id, campaign_id)
            
            if existing_score:
                # Update existing score
                return self.update(existing_score, **score_data)
            else:
                # Create new score
                score_data['contact_id'] = contact_id
                score_data['campaign_id'] = campaign_id
                return self.create(**score_data)
        except Exception as e:
            logger.error(f"Error upserting score for contact {contact_id}, campaign {campaign_id}: {e}")
            raise
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[EngagementScore]:
        """
        Search engagement scores by text query.
        
        Args:
            query: Search query string
            fields: Fields to search in (default: score_metadata)
        
        Returns:
            List of matching EngagementScore instances
        """
        if not query:
            return []
        
        try:
            search_fields = fields or ['score_metadata']
            conditions = []
            
            for field in search_fields:
                if field == 'score_metadata' and hasattr(EngagementScore, 'score_metadata'):
                    # Search in JSON field (PostgreSQL specific)
                    conditions.append(
                        func.cast(EngagementScore.score_metadata, String).ilike(f'%{query}%')
                    )
                elif hasattr(EngagementScore, field):
                    attr = getattr(EngagementScore, field)
                    if hasattr(attr, 'ilike'):
                        conditions.append(attr.ilike(f'%{query}%'))
            
            if not conditions:
                return []
            
            return self.session.query(EngagementScore).filter(
                or_(*conditions)
            ).order_by(desc(EngagementScore.calculated_at)).all()
        except Exception as e:
            logger.error(f"Error searching engagement scores: {e}")
            return []
    
    def get_paginated(self, pagination: PaginationParams,
                     filters: Optional[Dict[str, Any]] = None,
                     order_by: Optional[str] = None,
                     order: SortOrder = SortOrder.DESC) -> PaginatedResult[EngagementScore]:
        """
        Get paginated engagement scores.
        
        Args:
            pagination: Pagination parameters
            filters: Optional filters to apply
            order_by: Field to order by (default: overall_score)
            order: Sort order
        
        Returns:
            PaginatedResult with scores and metadata
        """
        # Default ordering by overall_score
        if not order_by:
            order_by = 'overall_score'
        
        return super().get_paginated(pagination, filters, order_by, order)
    
    def get_score_trends(self, contact_id: int, campaign_id: Optional[int] = None, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Get score trends over time for a contact in a campaign.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID (optional - if None, gets trends across all campaigns)
            days_back: Number of days to look back
        
        Returns:
            List of score snapshots with timestamps
        """
        try:
            cutoff_date = utc_now() - timedelta(days=days_back)
            
            # Build filter conditions
            filters = [
                EngagementScore.contact_id == contact_id,
                EngagementScore.calculated_at >= cutoff_date
            ]
            
            # Add campaign filter if specified
            if campaign_id is not None:
                filters.append(EngagementScore.campaign_id == campaign_id)
            
            scores = self.session.query(
                EngagementScore.overall_score,
                EngagementScore.recency_score,
                EngagementScore.frequency_score,
                EngagementScore.monetary_score,
                EngagementScore.engagement_probability,
                EngagementScore.calculated_at
            ).filter(
                and_(*filters)
            ).order_by(asc(EngagementScore.calculated_at)).all()
            
            # Convert to list of dictionaries
            trends = []
            for score in scores:
                trends.append({
                    'overall_score': float(score.overall_score),
                    'recency_score': float(score.recency_score) if score.recency_score else 0,
                    'frequency_score': float(score.frequency_score) if score.frequency_score else 0,
                    'monetary_score': float(score.monetary_score) if score.monetary_score else 0,
                    'engagement_probability': float(score.engagement_probability) if score.engagement_probability else 0,
                    'calculated_at': score.calculated_at.isoformat()
                })
            
            return trends
        except Exception as e:
            logger.error(f"Error getting score trends: {e}")
            return []
