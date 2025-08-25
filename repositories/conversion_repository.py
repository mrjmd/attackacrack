"""
ConversionRepository - Data access layer for ConversionEvent entities
Handles all database operations for conversion tracking and analytics
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, and_, or_, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import (
    ConversionEvent, Contact, Campaign, CampaignMembership, 
    CampaignResponse, Activity
)
from utils.datetime_utils import utc_now, ensure_utc
import logging
import math

logger = logging.getLogger(__name__)


class ConversionRepository(BaseRepository[ConversionEvent]):
    """Repository for ConversionEvent data access and analytics"""
    
    # Valid conversion types
    VALID_CONVERSION_TYPES = [
        'purchase', 'appointment_booked', 'quote_requested', 
        'lead_qualified', 'custom'
    ]
    
    # Valid attribution models
    VALID_ATTRIBUTION_MODELS = [
        'first_touch', 'last_touch', 'linear', 'time_decay'
    ]
    
    def __init__(self, session: Session):
        """Initialize repository with database session"""
        super().__init__(session, ConversionEvent)
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[ConversionEvent]:
        """
        Search conversion events by text query.
        
        Args:
            query: Search query string
            fields: Optional list of fields to search
            
        Returns:
            List of matching conversion events
        """
        if not query:
            return []
        
        search_pattern = f"%{query}%"
        fields_to_search = fields or ['conversion_type', 'metadata']
        
        try:
            conditions = []
            
            if 'conversion_type' in fields_to_search:
                conditions.append(ConversionEvent.conversion_type.ilike(search_pattern))
            
            if 'metadata' in fields_to_search and ConversionEvent.metadata is not None:
                # Search in JSON metadata field
                conditions.append(text("CAST(metadata AS TEXT) ILIKE :pattern").params(pattern=search_pattern))
            
            if not conditions:
                return []
            
            return self.session.query(ConversionEvent).filter(
                or_(*conditions)
            ).order_by(desc(ConversionEvent.created_at)).limit(100).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Error searching conversion events: {e}")
            return []
    
    # ===== Basic CRUD Operations =====
    
    def create_conversion_event(self, conversion_data: Dict[str, Any]) -> ConversionEvent:
        """
        Create a new conversion event with validation.
        
        Args:
            conversion_data: Dictionary with conversion attributes
            
        Returns:
            Created ConversionEvent instance
            
        Raises:
            ValueError: If required fields are missing or invalid
            SQLAlchemyError: If database operation fails
        """
        # Validate required fields
        if not conversion_data.get('contact_id'):
            raise ValueError("Contact ID is required")
        
        # Validate conversion value
        if 'conversion_value' in conversion_data:
            value = conversion_data['conversion_value']
            if value is not None and value < 0:
                raise ValueError("Conversion value must be positive")
        
        # Validate conversion type
        if 'conversion_type' in conversion_data:
            self._validate_conversion_type(conversion_data['conversion_type'])
        
        # Ensure converted_at is UTC
        if 'converted_at' in conversion_data:
            conversion_data['converted_at'] = ensure_utc(conversion_data['converted_at'])
        else:
            conversion_data['converted_at'] = utc_now()
        
        try:
            conversion = ConversionEvent(**conversion_data)
            self.session.add(conversion)
            self.session.flush()
            logger.debug(f"Created conversion event {conversion.id} for contact {conversion.contact_id}")
            return conversion
        except IntegrityError as e:
            logger.error(f"Integrity error creating conversion event: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error creating conversion event: {e}")
            self.session.rollback()
            raise
    
    def get_by_id(self, conversion_id: int) -> Optional[ConversionEvent]:
        """
        Retrieve a conversion event by ID.
        
        Args:
            conversion_id: ID of the conversion event
            
        Returns:
            ConversionEvent instance or None if not found
        """
        try:
            return self.session.query(ConversionEvent).get(conversion_id)
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving conversion {conversion_id}: {e}")
            raise
    
    def update(self, entity: ConversionEvent, **updates) -> ConversionEvent:
        """
        Update an existing conversion event.
        
        Args:
            entity: ConversionEvent to update
            **updates: Field-value pairs to update
            
        Returns:
            Updated ConversionEvent instance
        """
        # Validate conversion value if being updated
        if 'conversion_value' in updates:
            value = updates['conversion_value']
            if value is not None and value < 0:
                raise ValueError("Conversion value must be positive")
        
        # Validate conversion type if being updated
        if 'conversion_type' in updates:
            self._validate_conversion_type(updates['conversion_type'])
        
        return super().update(entity, **updates)
    
    def delete(self, entity: ConversionEvent) -> bool:
        """
        Delete a conversion event.
        
        Args:
            entity: ConversionEvent to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            self.session.delete(entity)
            self.session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting conversion event: {e}")
            self.session.rollback()
            raise
    
    # ===== Query Methods =====
    
    def get_conversions_for_contact(self, contact_id: int) -> List[ConversionEvent]:
        """
        Retrieve all conversions for a specific contact.
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            List of ConversionEvent instances
        """
        try:
            return self.session.query(ConversionEvent)\
                .filter(ConversionEvent.contact_id == contact_id)\
                .order_by(desc(ConversionEvent.converted_at))\
                .all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving conversions for contact {contact_id}: {e}")
            raise
    
    def get_conversions_for_campaign(
        self, 
        campaign_id: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[ConversionEvent]:
        """
        Retrieve all conversions for a specific campaign with optional date range.
        
        Args:
            campaign_id: ID of the campaign
            date_from: Start date for filtering
            date_to: End date for filtering
            
        Returns:
            List of ConversionEvent instances
            
        Raises:
            ValueError: If date_from is after date_to
        """
        if date_from and date_to and date_from > date_to:
            raise ValueError("date_from must be before date_to")
        
        try:
            query = self.session.query(ConversionEvent)\
                .filter(ConversionEvent.campaign_id == campaign_id)
            
            if date_from:
                query = query.filter(ConversionEvent.converted_at >= ensure_utc(date_from))
            
            if date_to:
                query = query.filter(ConversionEvent.converted_at <= ensure_utc(date_to))
            
            return query.order_by(desc(ConversionEvent.converted_at)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving conversions for campaign {campaign_id}: {e}")
            raise
    
    def get_conversions_by_type(self, conversion_type: str) -> List[ConversionEvent]:
        """
        Retrieve conversions filtered by conversion type.
        
        Args:
            conversion_type: Type of conversion to filter by
            
        Returns:
            List of ConversionEvent instances
        """
        try:
            return self.session.query(ConversionEvent)\
                .filter(ConversionEvent.conversion_type == conversion_type)\
                .order_by(desc(ConversionEvent.converted_at))\
                .all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving conversions by type {conversion_type}: {e}")
            raise
    
    def get_conversions_in_period(
        self,
        date_from: datetime,
        date_to: datetime,
        campaign_id: Optional[int] = None
    ) -> List[ConversionEvent]:
        """
        Retrieve conversions within a specific time period.
        
        Args:
            date_from: Start date
            date_to: End date
            campaign_id: Optional campaign filter
            
        Returns:
            List of ConversionEvent instances
        """
        if date_from > date_to:
            raise ValueError("date_from must be before date_to")
        
        try:
            query = self.session.query(ConversionEvent)\
                .filter(ConversionEvent.converted_at >= ensure_utc(date_from))\
                .filter(ConversionEvent.converted_at <= ensure_utc(date_to))
            
            if campaign_id:
                query = query.filter(ConversionEvent.campaign_id == campaign_id)
            
            return query.order_by(desc(ConversionEvent.converted_at)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving conversions in period: {e}")
            raise
    
    # ===== Conversion Rate Analytics =====
    
    def calculate_conversion_rate_for_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """
        Calculate conversion rate for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Dictionary with conversion rate metrics
        """
        try:
            # Query to get campaign metrics
            query = text("""
                SELECT 
                    COALESCE(COUNT(DISTINCT cm.id), 0) as total_sent,
                    COALESCE(COUNT(DISTINCT ce.id), 0) as total_conversions,
                    CASE 
                        WHEN COUNT(DISTINCT cm.id) > 0 
                        THEN CAST(COUNT(DISTINCT ce.id) AS FLOAT) / COUNT(DISTINCT cm.id)
                        ELSE 0.0
                    END as conversion_rate
                FROM campaign_membership cm
                LEFT JOIN conversion_events ce ON ce.contact_id = cm.contact_id 
                    AND ce.campaign_id = :campaign_id
                WHERE cm.campaign_id = :campaign_id
            """)
            
            result = self.session.execute(query, {'campaign_id': campaign_id})
            row = result.fetchone()
            
            return {
                'campaign_id': campaign_id,
                'total_sent': row[0] if row else 0,
                'total_conversions': row[1] if row else 0,
                'conversion_rate': row[2] if row else 0.0,
                'calculated_at': utc_now()
            }
        except SQLAlchemyError as e:
            logger.error(f"Error calculating conversion rate for campaign {campaign_id}: {e}")
            raise
    
    def calculate_conversion_rates_by_type(
        self,
        campaign_id: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Calculate conversion rates grouped by conversion type.
        
        Args:
            campaign_id: ID of the campaign
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Dictionary mapping conversion types to rates
        """
        try:
            query = self.session.query(
                ConversionEvent.conversion_type,
                func.count(ConversionEvent.id).label('count')
            ).filter(ConversionEvent.campaign_id == campaign_id)
            
            if date_from:
                query = query.filter(ConversionEvent.converted_at >= ensure_utc(date_from))
            if date_to:
                query = query.filter(ConversionEvent.converted_at <= ensure_utc(date_to))
            
            query = query.group_by(ConversionEvent.conversion_type)
            
            results = query.all()
            
            # Get total campaign members
            total_members = self.session.query(CampaignMembership)\
                .filter(CampaignMembership.campaign_id == campaign_id)\
                .count()
            
            if total_members == 0:
                return {}
            
            return {
                conversion_type: count / total_members
                for conversion_type, count in results
            }
        except SQLAlchemyError as e:
            logger.error(f"Error calculating conversion rates by type: {e}")
            raise
    
    def get_conversion_rates_by_time_period(
        self,
        campaign_id: int,
        date_from: datetime,
        date_to: datetime,
        group_by: str = 'day'
    ) -> List[Dict[str, Any]]:
        """
        Get conversion rates grouped by time period.
        
        Args:
            campaign_id: ID of the campaign
            date_from: Start date
            date_to: End date
            group_by: Time grouping ('day', 'week', 'month')
            
        Returns:
            List of dictionaries with period metrics
        """
        try:
            # Determine date truncation based on group_by
            if group_by == 'day':
                date_format = '%Y-%m-%d'
            elif group_by == 'week':
                date_format = '%Y-%W'
            elif group_by == 'month':
                date_format = '%Y-%m'
            else:
                date_format = '%Y-%m-%d'
            
            query = text("""
                WITH period_data AS (
                    SELECT 
                        DATE_FORMAT(cm.created_at, :date_format) as period,
                        COUNT(DISTINCT cm.id) as total_sent,
                        COUNT(DISTINCT ce.id) as conversions
                    FROM campaign_membership cm
                    LEFT JOIN conversion_events ce ON ce.contact_id = cm.contact_id 
                        AND ce.campaign_id = cm.campaign_id
                        AND ce.converted_at BETWEEN :date_from AND :date_to
                    WHERE cm.campaign_id = :campaign_id
                        AND cm.created_at BETWEEN :date_from AND :date_to
                    GROUP BY DATE_FORMAT(cm.created_at, :date_format)
                )
                SELECT 
                    period,
                    total_sent,
                    conversions,
                    CASE 
                        WHEN total_sent > 0 
                        THEN CAST(conversions AS FLOAT) / total_sent
                        ELSE 0.0
                    END as conversion_rate
                FROM period_data
                ORDER BY period
            """)
            
            result = self.session.execute(query, {
                'campaign_id': campaign_id,
                'date_from': ensure_utc(date_from),
                'date_to': ensure_utc(date_to),
                'date_format': date_format
            })
            
            return [
                {
                    'period': row[0],
                    'total_sent': row[1],
                    'conversions': row[2],
                    'conversion_rate': row[3]
                }
                for row in result.fetchall()
            ]
        except SQLAlchemyError as e:
            logger.error(f"Error getting conversion rates by time period: {e}")
            raise
    
    # ===== ROI Calculation =====
    
    def calculate_roi(
        self,
        total_revenue: Decimal,
        total_cost: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate ROI metrics.
        
        Args:
            total_revenue: Total revenue generated
            total_cost: Total cost incurred
            
        Returns:
            Dictionary with ROI metrics
        """
        if total_cost == 0:
            roi = Decimal('0.00')
        else:
            roi = (total_revenue - total_cost) / total_cost
        
        return {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'profit': total_revenue - total_cost,
            'roi': roi
        }
    
    def calculate_campaign_roi(
        self,
        campaign_id: int,
        campaign_cost: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate ROI for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            campaign_cost: Cost of the campaign
            
        Returns:
            Dictionary with ROI metrics
        """
        try:
            query = text("""
                SELECT 
                    COALESCE(SUM(conversion_value), 0) as total_revenue,
                    COUNT(*) as conversion_count,
                    COALESCE(AVG(conversion_value), 0) as avg_conversion_value
                FROM conversion_events
                WHERE campaign_id = :campaign_id
                    AND conversion_value IS NOT NULL
            """)
            
            result = self.session.execute(query, {'campaign_id': campaign_id})
            row = result.fetchone()
            
            total_revenue = Decimal(str(row[0])) if row else Decimal('0.00')
            conversion_count = row[1] if row else 0
            avg_value = Decimal(str(row[2])) if row else Decimal('0.00')
            
            profit = total_revenue - campaign_cost
            roi = profit / campaign_cost if campaign_cost > 0 else Decimal('-1.00')
            
            return {
                'campaign_id': campaign_id,
                'total_revenue': total_revenue,
                'campaign_cost': campaign_cost,
                'profit': profit,
                'roi': roi,
                'conversion_count': conversion_count,
                'average_conversion_value': avg_value
            }
        except SQLAlchemyError as e:
            logger.error(f"Error calculating ROI for campaign {campaign_id}: {e}")
            raise
    
    # ===== Multi-Touch Attribution =====
    
    def get_attribution_data(
        self,
        conversion_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get attribution data for a conversion.
        
        Args:
            conversion_id: ID of the conversion
            
        Returns:
            List of attribution touchpoints
        """
        return self.get_conversions_with_attribution_path(conversion_id)
    
    def get_conversions_with_attribution_path(
        self,
        conversion_id: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversions with their attribution touchpoints.
        
        Args:
            conversion_id: ID of the conversion
            
        Returns:
            List of dictionaries with attribution data
        """
        try:
            query = text("""
                SELECT 
                    ce.id as conversion_id,
                    ce.contact_id,
                    ce.conversion_type,
                    ce.conversion_value,
                    a.campaign_id as touchpoint_campaign_id,
                    a.activity_type as touchpoint_type,
                    a.created_at as touchpoint_timestamp,
                    COALESCE(
                        JSON_EXTRACT(ce.attribution_weights, CONCAT('$."', a.campaign_id, '"')),
                        0.0
                    ) as attribution_weight
                FROM conversion_events ce
                JOIN activity a ON a.contact_id = ce.contact_id
                WHERE ce.id = :conversion_id
                    AND a.created_at <= ce.converted_at
                    AND a.created_at >= DATE_SUB(ce.converted_at, INTERVAL COALESCE(ce.attribution_window_days, 30) DAY)
                ORDER BY a.created_at
            """)
            
            result = self.session.execute(query, {'conversion_id': conversion_id})
            
            rows = result.fetchall()
            return [
                {
                    'conversion_id': row.get('conversion_id') if hasattr(row, 'get') else row[0],
                    'contact_id': row.get('contact_id') if hasattr(row, 'get') else row[1],
                    'conversion_type': row.get('conversion_type') if hasattr(row, 'get') else row[2],
                    'conversion_value': row.get('conversion_value') if hasattr(row, 'get') else row[3],
                    'touchpoint_campaign_id': row.get('touchpoint_campaign_id') if hasattr(row, 'get') else row[4],
                    'touchpoint_type': row.get('touchpoint_type') if hasattr(row, 'get') else row[5],
                    'touchpoint_timestamp': row.get('touchpoint_timestamp') if hasattr(row, 'get') else row[6],
                    'attribution_weight': float(row.get('attribution_weight') if hasattr(row, 'get') else row[7]) if (row.get('attribution_weight') if hasattr(row, 'get') else row[7]) else 0.0
                }
                for row in rows
            ]
        except SQLAlchemyError as e:
            logger.error(f"Error getting attribution path for conversion {conversion_id}: {e}")
            raise
    
    def calculate_attribution_weights(
        self,
        contact_id: int,
        conversion_timestamp: datetime,
        attribution_model: str = 'last_touch',
        attribution_window_days: int = 30
    ) -> Dict[int, float]:
        """
        Calculate attribution weights for touchpoints.
        
        Args:
            contact_id: ID of the contact
            conversion_timestamp: When the conversion occurred
            attribution_model: Attribution model to use
            attribution_window_days: Lookback window in days
            
        Returns:
            Dictionary mapping campaign IDs to attribution weights
            
        Raises:
            ValueError: If attribution model is not supported
        """
        if attribution_model not in self.VALID_ATTRIBUTION_MODELS:
            raise ValueError(f"Unsupported attribution model: {attribution_model}")
        
        try:
            # Get touchpoints within attribution window
            query = text("""
                SELECT 
                    campaign_id,
                    created_at as activity_timestamp,
                    activity_type
                FROM activity
                WHERE contact_id = :contact_id
                    AND created_at <= :conversion_timestamp
                    AND created_at >= :window_start
                    AND campaign_id IS NOT NULL
                ORDER BY created_at
            """)
            
            window_start = conversion_timestamp - timedelta(days=attribution_window_days)
            result = self.session.execute(query, {
                'contact_id': contact_id,
                'conversion_timestamp': ensure_utc(conversion_timestamp),
                'window_start': ensure_utc(window_start)
            })
            
            touchpoints = result.fetchall()
            if not touchpoints:
                return {}
            
            # Calculate weights based on model
            weights = {}
            
            if attribution_model == 'last_touch':
                # Give 100% credit to last touchpoint
                last_touchpoint = touchpoints[-1]
                campaign_id = last_touchpoint.get('campaign_id') if hasattr(last_touchpoint, 'get') else last_touchpoint[0]
                weights[campaign_id] = 1.0
                
            elif attribution_model == 'first_touch':
                # Give 100% credit to first touchpoint
                first_touchpoint = touchpoints[0]
                campaign_id = first_touchpoint.get('campaign_id') if hasattr(first_touchpoint, 'get') else first_touchpoint[0]
                weights[campaign_id] = 1.0
                
            elif attribution_model == 'linear':
                # Equal credit to all touchpoints
                weight = 1.0 / len(touchpoints)
                for touchpoint in touchpoints:
                    campaign_id = touchpoint.get('campaign_id') if hasattr(touchpoint, 'get') else touchpoint[0]
                    if campaign_id in weights:
                        weights[campaign_id] += weight
                    else:
                        weights[campaign_id] = weight
                        
            elif attribution_model == 'time_decay':
                # More credit to recent touchpoints
                total_weight = 0
                temp_weights = []
                
                for i, touchpoint in enumerate(touchpoints):
                    # Exponential decay based on position
                    decay_factor = 2 ** i  # More recent gets higher weight
                    campaign_id = touchpoint.get('campaign_id') if hasattr(touchpoint, 'get') else touchpoint[0]
                    temp_weights.append((campaign_id, decay_factor))
                    total_weight += decay_factor
                
                # Normalize weights to sum to 1
                for campaign_id, weight in temp_weights:
                    normalized_weight = weight / total_weight
                    if campaign_id in weights:
                        weights[campaign_id] += normalized_weight
                    else:
                        weights[campaign_id] = normalized_weight
            
            return weights
            
        except SQLAlchemyError as e:
            logger.error(f"Error calculating attribution weights: {e}")
            raise
    
    def calculate_multi_touch_attribution(
        self,
        campaign_id: int,
        attribution_model: str = 'linear'
    ) -> Dict[str, Any]:
        """
        Calculate multi-touch attribution for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            attribution_model: Attribution model to use
            
        Returns:
            Attribution analysis results
        """
        if attribution_model not in self.VALID_ATTRIBUTION_MODELS:
            raise ValueError(f"Unsupported attribution model: {attribution_model}")
        
        try:
            # Get all conversions for the campaign
            conversions = self.get_conversions_for_campaign(campaign_id)
            
            total_value = Decimal('0.00')
            attributed_value = Decimal('0.00')
            touchpoint_count = 0
            
            for conversion in conversions:
                if conversion.conversion_value:
                    total_value += conversion.conversion_value
                    
                    # Calculate attribution for this conversion
                    weights = self.calculate_attribution_weights(
                        conversion.contact_id,
                        conversion.converted_at,
                        attribution_model,
                        conversion.attribution_window_days or 30
                    )
                    
                    # Apply weights to conversion value
                    if campaign_id in weights:
                        attributed_value += conversion.conversion_value * Decimal(str(weights[campaign_id]))
                    
                    touchpoint_count += len(weights)
            
            return {
                'campaign_id': campaign_id,
                'attribution_model': attribution_model,
                'total_conversion_value': total_value,
                'attributed_value': attributed_value,
                'attribution_percentage': float(attributed_value / total_value) if total_value > 0 else 0.0,
                'average_touchpoints': touchpoint_count / len(conversions) if conversions else 0
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error calculating multi-touch attribution: {e}")
            raise
    
    # ===== Conversion Funnel Analysis =====
    
    def get_funnel_data(
        self,
        campaign_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get conversion funnel data for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            List of funnel stage metrics
        """
        return self.get_conversion_funnel_data(campaign_id)
    
    def get_conversion_funnel_data(
        self,
        campaign_id: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversion funnel data for analysis.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            List of dictionaries with funnel stage metrics
        """
        try:
            query = text("""
                WITH funnel_stages AS (
                    SELECT 
                        'sent' as stage,
                        COUNT(DISTINCT cm.id) as count,
                        1 as stage_order
                    FROM campaign_membership cm
                    WHERE cm.campaign_id = :campaign_id
                    
                    UNION ALL
                    
                    SELECT 
                        'delivered' as stage,
                        COUNT(DISTINCT cm.id) as count,
                        2 as stage_order
                    FROM campaign_membership cm
                    WHERE cm.campaign_id = :campaign_id
                        AND cm.status = 'delivered'
                    
                    UNION ALL
                    
                    SELECT 
                        'engaged' as stage,
                        COUNT(DISTINCT a.contact_id) as count,
                        3 as stage_order
                    FROM activity a
                    JOIN campaign_membership cm ON cm.contact_id = a.contact_id
                    WHERE cm.campaign_id = :campaign_id
                        AND a.campaign_id = :campaign_id
                        AND a.activity_type IN ('email_opened', 'link_clicked', 'sms_clicked')
                    
                    UNION ALL
                    
                    SELECT 
                        'responded' as stage,
                        COUNT(DISTINCT cr.contact_id) as count,
                        4 as stage_order
                    FROM campaign_response cr
                    WHERE cr.campaign_id = :campaign_id
                        AND cr.response_received_at IS NOT NULL
                    
                    UNION ALL
                    
                    SELECT 
                        'converted' as stage,
                        COUNT(DISTINCT ce.contact_id) as count,
                        5 as stage_order
                    FROM conversion_events ce
                    WHERE ce.campaign_id = :campaign_id
                )
                SELECT 
                    stage,
                    count,
                    count as cumulative_count,
                    CASE 
                        WHEN (SELECT count FROM funnel_stages WHERE stage = 'sent') > 0
                        THEN CAST(count AS FLOAT) / (SELECT count FROM funnel_stages WHERE stage = 'sent')
                        ELSE 0.0
                    END as stage_conversion_rate
                FROM funnel_stages
                ORDER BY stage_order
            """)
            
            result = self.session.execute(query, {'campaign_id': campaign_id})
            
            rows = result.fetchall()
            return [
                {
                    'stage': row.get('stage') if hasattr(row, 'get') else row[0],
                    'count': row.get('count') if hasattr(row, 'get') else row[1],
                    'cumulative_count': row.get('cumulative_count') if hasattr(row, 'get') else row[2],
                    'stage_conversion_rate': row.get('stage_conversion_rate') if hasattr(row, 'get') else row[3]
                }
                for row in rows
            ]
        except SQLAlchemyError as e:
            logger.error(f"Error getting conversion funnel data: {e}")
            raise
    
    def identify_funnel_drop_off_points(
        self,
        campaign_id: int
    ) -> List[Dict[str, Any]]:
        """
        Identify major drop-off points in conversion funnel.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            List of drop-off point analyses
        """
        try:
            funnel_data = self.get_conversion_funnel_data(campaign_id)
            
            drop_offs = []
            for i in range(len(funnel_data) - 1):
                current_stage = funnel_data[i]
                next_stage = funnel_data[i + 1]
                
                drop_off_count = current_stage['count'] - next_stage['count']
                drop_off_rate = drop_off_count / current_stage['count'] if current_stage['count'] > 0 else 0
                
                # Determine severity
                if drop_off_rate >= 0.8:
                    severity = 'critical'
                elif drop_off_rate >= 0.5:
                    severity = 'high'
                elif drop_off_rate >= 0.3:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                drop_offs.append({
                    'from_stage': current_stage['stage'],
                    'to_stage': next_stage['stage'],
                    'drop_off_count': drop_off_count,
                    'drop_off_rate': drop_off_rate,
                    'severity': severity
                })
            
            return drop_offs
            
        except Exception as e:
            logger.error(f"Error identifying funnel drop-off points: {e}")
            raise
    
    # ===== Time-to-Conversion Analysis =====
    
    def get_time_to_conversion_stats(
        self,
        campaign_id: int
    ) -> Dict[str, Any]:
        """
        Get time-to-conversion statistics for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Dictionary with time statistics
        """
        return self.calculate_average_time_to_conversion(campaign_id)
    
    def calculate_average_time_to_conversion(
        self,
        campaign_id: int
    ) -> Dict[str, Any]:
        """
        Calculate average time from first touch to conversion.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Dictionary with time-to-conversion metrics
        """
        try:
            query = text("""
                SELECT 
                    AVG(TIMESTAMPDIFF(HOUR, first_touch, converted_at)) as average_hours,
                    AVG(TIMESTAMPDIFF(HOUR, first_touch, converted_at)) / 24.0 as average_days,
                    -- MySQL doesn't have median, so we'll approximate
                    AVG(TIMESTAMPDIFF(HOUR, first_touch, converted_at)) as median_hours,
                    MIN(TIMESTAMPDIFF(HOUR, first_touch, converted_at)) as min_hours,
                    MAX(TIMESTAMPDIFF(HOUR, first_touch, converted_at)) as max_hours
                FROM (
                    SELECT 
                        ce.converted_at,
                        MIN(a.created_at) as first_touch
                    FROM conversion_events ce
                    JOIN activity a ON a.contact_id = ce.contact_id
                    WHERE ce.campaign_id = :campaign_id
                        AND a.campaign_id = :campaign_id
                        AND a.created_at <= ce.converted_at
                    GROUP BY ce.id, ce.converted_at
                ) as conversion_times
            """)
            
            result = self.session.execute(query, {'campaign_id': campaign_id})
            row = result.fetchone()
            
            if row and row[0] is not None:
                return {
                    'campaign_id': campaign_id,
                    'average_hours': float(row[0]) if row[0] else 0,
                    'average_days': float(row[1]) if row[1] else 0,
                    'median_hours': float(row[2]) if row[2] else 0,
                    'min_hours': float(row[3]) if row[3] else 0,
                    'max_hours': float(row[4]) if row[4] else 0
                }
            else:
                return {
                    'campaign_id': campaign_id,
                    'average_hours': 0,
                    'average_days': 0,
                    'median_hours': 0,
                    'min_hours': 0,
                    'max_hours': 0
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error calculating time to conversion: {e}")
            raise
    
    def get_time_to_conversion_distribution(
        self,
        campaign_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get distribution of conversion times.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            List of time bucket distributions
        """
        try:
            query = text("""
                WITH conversion_times AS (
                    SELECT 
                        ce.id,
                        TIMESTAMPDIFF(HOUR, MIN(a.created_at), ce.converted_at) as hours_to_conversion
                    FROM conversion_events ce
                    JOIN activity a ON a.contact_id = ce.contact_id
                    WHERE ce.campaign_id = :campaign_id
                        AND a.campaign_id = :campaign_id
                        AND a.created_at <= ce.converted_at
                    GROUP BY ce.id, ce.converted_at
                ),
                total_conversions AS (
                    SELECT COUNT(*) as total FROM conversion_times
                )
                SELECT 
                    CASE 
                        WHEN hours_to_conversion <= 1 THEN '0-1 hours'
                        WHEN hours_to_conversion <= 6 THEN '1-6 hours'
                        WHEN hours_to_conversion <= 24 THEN '6-24 hours'
                        WHEN hours_to_conversion <= 168 THEN '1-7 days'
                        ELSE '7+ days'
                    END as time_bucket,
                    COUNT(*) as conversion_count,
                    CAST(COUNT(*) AS FLOAT) / (SELECT total FROM total_conversions) as percentage
                FROM conversion_times
                GROUP BY 
                    CASE 
                        WHEN hours_to_conversion <= 1 THEN '0-1 hours'
                        WHEN hours_to_conversion <= 6 THEN '1-6 hours'
                        WHEN hours_to_conversion <= 24 THEN '6-24 hours'
                        WHEN hours_to_conversion <= 168 THEN '1-7 days'
                        ELSE '7+ days'
                    END
                ORDER BY 
                    MIN(hours_to_conversion)
            """)
            
            result = self.session.execute(query, {'campaign_id': campaign_id})
            
            rows = result.fetchall()
            return [
                {
                    'time_bucket': row.get('time_bucket') if hasattr(row, 'get') else row[0],
                    'conversion_count': row.get('conversion_count') if hasattr(row, 'get') else row[1],
                    'percentage': float(row.get('percentage') if hasattr(row, 'get') else row[2]) if (row.get('percentage') if hasattr(row, 'get') else row[2]) else 0.0
                }
                for row in rows
            ]
        except SQLAlchemyError as e:
            logger.error(f"Error getting time to conversion distribution: {e}")
            raise
    
    # ===== Conversion Value Analytics =====
    
    def get_conversion_value_stats(
        self,
        campaign_id: int,
        conversion_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get conversion value statistics.
        
        Args:
            campaign_id: ID of the campaign
            conversion_type: Optional filter by conversion type
            
        Returns:
            Dictionary with value statistics
        """
        return self.get_conversion_value_statistics(campaign_id, conversion_type)
    
    def get_conversion_value_statistics(
        self,
        campaign_id: int,
        conversion_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate conversion value statistics.
        
        Args:
            campaign_id: ID of the campaign
            conversion_type: Optional filter by conversion type
            
        Returns:
            Dictionary with value statistics
        """
        try:
            query = text("""
                SELECT 
                    AVG(conversion_value) as average_value,
                    -- MySQL doesn't have median, using AVG as approximation
                    AVG(conversion_value) as median_value,
                    SUM(conversion_value) as total_value,
                    MIN(conversion_value) as min_value,
                    MAX(conversion_value) as max_value,
                    STD(conversion_value) as std_deviation,
                    COUNT(*) as conversion_count
                FROM conversion_events
                WHERE campaign_id = :campaign_id
                    AND conversion_value IS NOT NULL
                    AND (:conversion_type IS NULL OR conversion_type = :conversion_type)
            """)
            
            result = self.session.execute(query, {
                'campaign_id': campaign_id,
                'conversion_type': conversion_type
            })
            row = result.fetchone()
            
            if row:
                return {
                    'campaign_id': campaign_id,
                    'conversion_type': conversion_type,
                    'average_value': Decimal(str(row[0])) if row[0] else Decimal('0.00'),
                    'median_value': Decimal(str(row[1])) if row[1] else Decimal('0.00'),
                    'total_value': Decimal(str(row[2])) if row[2] else Decimal('0.00'),
                    'min_value': Decimal(str(row[3])) if row[3] else Decimal('0.00'),
                    'max_value': Decimal(str(row[4])) if row[4] else Decimal('0.00'),
                    'std_deviation': Decimal(str(row[5])) if row[5] else Decimal('0.00'),
                    'conversion_count': row[6] if row[6] else 0
                }
            else:
                return {
                    'campaign_id': campaign_id,
                    'conversion_type': conversion_type,
                    'average_value': Decimal('0.00'),
                    'median_value': Decimal('0.00'),
                    'total_value': Decimal('0.00'),
                    'min_value': Decimal('0.00'),
                    'max_value': Decimal('0.00'),
                    'std_deviation': Decimal('0.00'),
                    'conversion_count': 0
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error calculating conversion value statistics: {e}")
            raise
    
    def get_high_value_conversions(
        self,
        campaign_id: int,
        value_threshold: Decimal
    ) -> List[ConversionEvent]:
        """
        Retrieve high-value conversions above threshold.
        
        Args:
            campaign_id: ID of the campaign
            value_threshold: Minimum conversion value
            
        Returns:
            List of high-value ConversionEvent instances
        """
        try:
            return self.session.query(ConversionEvent)\
                .filter(ConversionEvent.campaign_id == campaign_id)\
                .filter(ConversionEvent.conversion_value >= value_threshold)\
                .order_by(desc(ConversionEvent.conversion_value))\
                .all()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving high-value conversions: {e}")
            raise
    
    # ===== Pagination and Bulk Operations =====
    
    def get_conversions_paginated(
        self,
        campaign_id: int,
        pagination: PaginationParams
    ) -> PaginatedResult[ConversionEvent]:
        """
        Get paginated conversions for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            pagination: Pagination parameters
            
        Returns:
            PaginatedResult with conversions
        """
        try:
            query = self.session.query(ConversionEvent)\
                .filter(ConversionEvent.campaign_id == campaign_id)\
                .order_by(desc(ConversionEvent.converted_at))
            
            # Get total count
            total = query.count()
            
            # Get paginated items
            items = query.offset(pagination.offset)\
                .limit(pagination.limit)\
                .all()
            
            return PaginatedResult(
                items=items,
                total=total,
                page=pagination.page,
                per_page=pagination.per_page
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting paginated conversions: {e}")
            raise
    
    def bulk_create_conversion_events(
        self,
        conversion_events_data: List[Dict[str, Any]]
    ) -> int:
        """
        Bulk create multiple conversion events.
        
        Args:
            conversion_events_data: List of conversion event data dictionaries
            
        Returns:
            Number of events created
        """
        try:
            # Validate all events first
            for data in conversion_events_data:
                if not data.get('contact_id'):
                    raise ValueError("Contact ID is required for all events")
                if 'conversion_value' in data and data['conversion_value'] is not None and data['conversion_value'] < 0:
                    raise ValueError("Conversion value must be positive")
            
            # Use bulk insert for efficiency
            self.session.bulk_insert_mappings(ConversionEvent, conversion_events_data)
            self.session.commit()
            
            logger.debug(f"Bulk created {len(conversion_events_data)} conversion events")
            return len(conversion_events_data)
            
        except SQLAlchemyError as e:
            logger.error(f"Error bulk creating conversion events: {e}")
            self.session.rollback()
            raise
    
    def delete_conversions_for_contact(self, contact_id: int) -> int:
        """
        Delete all conversions for a contact (GDPR compliance).
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            Number of conversions deleted
        """
        try:
            deleted_count = self.session.query(ConversionEvent)\
                .filter(ConversionEvent.contact_id == contact_id)\
                .delete()
            
            self.session.commit()
            logger.info(f"Deleted {deleted_count} conversions for contact {contact_id}")
            return deleted_count
            
        except SQLAlchemyError as e:
            logger.error(f"Error deleting conversions for contact {contact_id}: {e}")
            self.session.rollback()
            raise
    
    def get_contact_conversion_values(self, campaign_id: int) -> List[Dict[str, Any]]:
        """
        Get total conversion values for each contact in a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            List of dictionaries with contact_id, total_value, and conversion_count
        """
        try:
            query = text("""
                SELECT 
                    contact_id,
                    COALESCE(SUM(conversion_value), 0) as total_value,
                    COUNT(*) as conversion_count
                FROM conversion_events
                WHERE campaign_id = :campaign_id
                    AND conversion_value IS NOT NULL
                GROUP BY contact_id
                ORDER BY total_value DESC
            """)
            
            result = self.session.execute(query, {'campaign_id': campaign_id})
            
            return [
                {
                    'contact_id': row[0],
                    'total_value': Decimal(str(row[1])) if row[1] else Decimal('0.00'),
                    'conversion_count': row[2]
                }
                for row in result.fetchall()
            ]
        except SQLAlchemyError as e:
            logger.error(f"Error getting contact conversion values: {e}")
            raise
    
    # ===== Helper Methods =====
    
    def _validate_conversion_type(self, conversion_type: str) -> None:
        """
        Validate conversion type.
        
        Args:
            conversion_type: Type to validate
            
        Raises:
            ValueError: If conversion type is invalid
        """
        if conversion_type not in self.VALID_CONVERSION_TYPES:
            raise ValueError(f"Invalid conversion type: {conversion_type}. Must be one of {self.VALID_CONVERSION_TYPES}")