"""Narrow filter utilities for simplified narrow construction.

This module provides enhanced narrow building utilities ported from the legacy
messaging_simple.py implementation, combining the simplicity of legacy helpers
with the type safety and power of v2.5.0 architecture.

Key features:
- Simple narrow builders for common use cases
- Progressive complexity from basic to advanced narrow construction
- Time-based filter helpers
- Integration with existing NarrowFilter types
- User-friendly narrow construction
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal, Optional, Union, List, Dict

from ..core.validation import NarrowFilter, NarrowOperator
from ..utils.logging import get_logger

logger = get_logger(__name__)


class NarrowHelper:
    """Enhanced narrow filter helpers combining legacy simplicity with v2.5.0 power.
    
    This class provides both simple static methods for quick narrow building
    and more advanced features for complex filtering scenarios.
    """

    # ===== BASIC NARROW BUILDERS =====
    
    @staticmethod
    def stream(name: str, negated: bool = False) -> NarrowFilter:
        """Create a stream filter.
        
        Args:
            name: Stream name to filter by
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for the stream
            
        Example:
            filter = NarrowHelper.stream("general")
        """
        return NarrowFilter(
            operator=NarrowOperator.STREAM,
            operand=name,
            negated=negated
        )
    
    @staticmethod
    def topic(name: str, negated: bool = False) -> NarrowFilter:
        """Create a topic filter.
        
        Args:
            name: Topic name to filter by
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for the topic
            
        Example:
            filter = NarrowHelper.topic("deployment")
        """
        return NarrowFilter(
            operator=NarrowOperator.TOPIC,
            operand=name,
            negated=negated
        )
    
    @staticmethod
    def sender(email: str, negated: bool = False) -> NarrowFilter:
        """Create a sender filter.
        
        Args:
            email: Sender email to filter by
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for the sender
            
        Example:
            filter = NarrowHelper.sender("user@example.com")
        """
        return NarrowFilter(
            operator=NarrowOperator.SENDER,
            operand=email,
            negated=negated
        )
    
    @staticmethod
    def search_text(text: str, negated: bool = False) -> NarrowFilter:
        """Create a text search filter.
        
        Args:
            text: Text to search for
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for text search
            
        Example:
            filter = NarrowHelper.search_text("bug fix")
        """
        return NarrowFilter(
            operator=NarrowOperator.SEARCH,
            operand=text,
            negated=negated
        )
    
    @staticmethod
    def has_attachment(negated: bool = False) -> NarrowFilter:
        """Create an attachment filter.
        
        Args:
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for messages with attachments
            
        Example:
            filter = NarrowHelper.has_attachment()
        """
        return NarrowFilter(
            operator=NarrowOperator.HAS,
            operand="attachment",
            negated=negated
        )
    
    @staticmethod
    def has_link(negated: bool = False) -> NarrowFilter:
        """Create a link filter.
        
        Args:
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for messages with links
            
        Example:
            filter = NarrowHelper.has_link()
        """
        return NarrowFilter(
            operator=NarrowOperator.HAS,
            operand="link",
            negated=negated
        )
    
    @staticmethod
    def has_image(negated: bool = False) -> NarrowFilter:
        """Create an image filter.
        
        Args:
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for messages with images
            
        Example:
            filter = NarrowHelper.has_image()
        """
        return NarrowFilter(
            operator=NarrowOperator.HAS,
            operand="image",
            negated=negated
        )
    
    @staticmethod
    def is_private(negated: bool = False) -> NarrowFilter:
        """Create a private message filter.
        
        Args:
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for private messages
            
        Example:
            filter = NarrowHelper.is_private()
        """
        return NarrowFilter(
            operator=NarrowOperator.IS,
            operand="private",
            negated=negated
        )
    
    @staticmethod
    def is_starred(negated: bool = False) -> NarrowFilter:
        """Create a starred message filter.
        
        Args:
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for starred messages
            
        Example:
            filter = NarrowHelper.is_starred()
        """
        return NarrowFilter(
            operator=NarrowOperator.IS,
            operand="starred",
            negated=negated
        )
    
    @staticmethod
    def is_mentioned(negated: bool = False) -> NarrowFilter:
        """Create a mentioned filter.
        
        Args:
            negated: Whether to negate the filter
            
        Returns:
            NarrowFilter for messages where user is mentioned
            
        Example:
            filter = NarrowHelper.is_mentioned()
        """
        return NarrowFilter(
            operator=NarrowOperator.IS,
            operand="mentioned",
            negated=negated
        )

    # ===== TIME-BASED FILTERS =====
    
    @staticmethod
    def after_time(when: Union[datetime, str]) -> NarrowFilter:
        """Create an 'after time' filter.
        
        Args:
            when: DateTime or ISO string for the cutoff time
            
        Returns:
            NarrowFilter for messages after the specified time
            
        Example:
            filter = NarrowHelper.after_time(datetime.now() - timedelta(hours=24))
        """
        if isinstance(when, datetime):
            time_str = when.isoformat()
        else:
            time_str = when
            
        return NarrowFilter(
            operator=NarrowOperator.SEARCH,
            operand=f"after:{time_str}"
        )
    
    @staticmethod
    def before_time(when: Union[datetime, str]) -> NarrowFilter:
        """Create a 'before time' filter.
        
        Args:
            when: DateTime or ISO string for the cutoff time
            
        Returns:
            NarrowFilter for messages before the specified time
            
        Example:
            filter = NarrowHelper.before_time(datetime.now())
        """
        if isinstance(when, datetime):
            time_str = when.isoformat()
        else:
            time_str = when
            
        return NarrowFilter(
            operator=NarrowOperator.SEARCH,
            operand=f"before:{time_str}"
        )
    
    @staticmethod
    def last_hours(hours: int) -> NarrowFilter:
        """Create a filter for messages from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            NarrowFilter for messages in the last N hours
            
        Example:
            filter = NarrowHelper.last_hours(24)
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return NarrowHelper.after_time(cutoff_time)
    
    @staticmethod
    def last_days(days: int) -> NarrowFilter:
        """Create a filter for messages from the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            NarrowFilter for messages in the last N days
            
        Example:
            filter = NarrowHelper.last_days(7)
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        return NarrowHelper.after_time(cutoff_time)
    
    @staticmethod
    def time_range(start: Union[datetime, str], end: Union[datetime, str]) -> List[NarrowFilter]:
        """Create filters for a time range.
        
        Args:
            start: Start time for the range
            end: End time for the range
            
        Returns:
            List of NarrowFilters defining the time range
            
        Example:
            filters = NarrowHelper.time_range(
                datetime.now() - timedelta(days=7),
                datetime.now()
            )
        """
        return [
            NarrowHelper.after_time(start),
            NarrowHelper.before_time(end)
        ]

    # ===== COMPOSITE NARROW BUILDERS =====
    
    @classmethod
    def build_basic_narrow(
        cls,
        stream: Optional[str] = None,
        topic: Optional[str] = None,
        sender: Optional[str] = None,
        text: Optional[str] = None,
        # Additional common filters
        has_attachment: Optional[bool] = None,
        has_link: Optional[bool] = None,
        has_image: Optional[bool] = None,
        is_private: Optional[bool] = None,
        is_starred: Optional[bool] = None,
        is_mentioned: Optional[bool] = None,
        # Time-based filters
        last_hours: Optional[int] = None,
        last_days: Optional[int] = None,
        after_time: Optional[Union[datetime, str]] = None,
        before_time: Optional[Union[datetime, str]] = None,
    ) -> List[NarrowFilter]:
        """Build a basic narrow filter from common parameters.
        
        This is the main utility function that makes narrow building much simpler
        by accepting common parameters and building the appropriate filter list.
        
        Args:
            stream: Stream name to filter by
            topic: Topic name to filter by
            sender: Sender email to filter by
            text: Text to search for
            has_attachment: Filter for messages with attachments
            has_link: Filter for messages with links
            has_image: Filter for messages with images
            is_private: Filter for private messages
            is_starred: Filter for starred messages
            is_mentioned: Filter for mentioned messages
            last_hours: Filter for messages in last N hours
            last_days: Filter for messages in last N days
            after_time: Filter for messages after specific time
            before_time: Filter for messages before specific time
            
        Returns:
            List of NarrowFilter objects
            
        Examples:
            # Simple stream and topic filter
            narrow = NarrowHelper.build_basic_narrow(
                stream="general", 
                topic="deployment"
            )
            
            # Text search with time range
            narrow = NarrowHelper.build_basic_narrow(
                text="bug fix",
                last_days=7
            )
            
            # Complex filter
            narrow = NarrowHelper.build_basic_narrow(
                stream="development",
                sender="dev@example.com",
                has_attachment=True,
                last_hours=24
            )
        """
        narrow: List[NarrowFilter] = []

        # Basic content filters
        if stream:
            narrow.append(cls.stream(stream))
        if topic:
            narrow.append(cls.topic(topic))
        if sender:
            narrow.append(cls.sender(sender))
        if text:
            narrow.append(cls.search_text(text))

        # Content type filters
        if has_attachment is not None:
            narrow.append(cls.has_attachment(negated=not has_attachment))
        if has_link is not None:
            narrow.append(cls.has_link(negated=not has_link))
        if has_image is not None:
            narrow.append(cls.has_image(negated=not has_image))

        # Message state filters
        if is_private is not None:
            narrow.append(cls.is_private(negated=not is_private))
        if is_starred is not None:
            narrow.append(cls.is_starred(negated=not is_starred))
        if is_mentioned is not None:
            narrow.append(cls.is_mentioned(negated=not is_mentioned))

        # Time-based filters (only one time filter is applied)
        if last_hours is not None:
            narrow.append(cls.last_hours(last_hours))
        elif last_days is not None:
            narrow.append(cls.last_days(last_days))
        elif after_time is not None and before_time is not None:
            narrow.extend(cls.time_range(after_time, before_time))
        elif after_time is not None:
            narrow.append(cls.after_time(after_time))
        elif before_time is not None:
            narrow.append(cls.before_time(before_time))

        return narrow

    @classmethod
    def build_stream_narrow(
        cls,
        stream: str,
        topic: Optional[str] = None,
        sender: Optional[str] = None,
        **kwargs
    ) -> List[NarrowFilter]:
        """Build a narrow focused on a specific stream.
        
        Convenience method for stream-based searches.
        
        Args:
            stream: Stream name (required)
            topic: Optional topic within the stream
            sender: Optional sender filter
            **kwargs: Additional parameters passed to build_basic_narrow
            
        Returns:
            List of NarrowFilter objects
            
        Example:
            narrow = NarrowHelper.build_stream_narrow(
                "general",
                topic="announcements",
                last_days=3
            )
        """
        return cls.build_basic_narrow(
            stream=stream,
            topic=topic,
            sender=sender,
            **kwargs
        )

    @classmethod
    def build_user_narrow(
        cls,
        sender: str,
        stream: Optional[str] = None,
        **kwargs
    ) -> List[NarrowFilter]:
        """Build a narrow focused on a specific user.
        
        Convenience method for user-based searches.
        
        Args:
            sender: Sender email (required)
            stream: Optional stream to limit search to
            **kwargs: Additional parameters passed to build_basic_narrow
            
        Returns:
            List of NarrowFilter objects
            
        Example:
            narrow = NarrowHelper.build_user_narrow(
                "alice@example.com",
                stream="development",
                last_hours=48
            )
        """
        return cls.build_basic_narrow(
            sender=sender,
            stream=stream,
            **kwargs
        )

    @classmethod  
    def build_search_narrow(
        cls,
        text: str,
        stream: Optional[str] = None,
        **kwargs
    ) -> List[NarrowFilter]:
        """Build a narrow focused on text search.
        
        Convenience method for text-based searches.
        
        Args:
            text: Search text (required)
            stream: Optional stream to limit search to
            **kwargs: Additional parameters passed to build_basic_narrow
            
        Returns:
            List of NarrowFilter objects
            
        Example:
            narrow = NarrowHelper.build_search_narrow(
                "docker deployment",
                stream="devops",
                last_days=14
            )
        """
        return cls.build_basic_narrow(
            text=text,
            stream=stream,
            **kwargs
        )

    # ===== CONVERSION UTILITIES =====
    
    @staticmethod
    def to_api_format(narrow_filters: List[NarrowFilter]) -> List[Dict[str, Any]]:
        """Convert NarrowFilter objects to Zulip API format.
        
        Args:
            narrow_filters: List of NarrowFilter objects
            
        Returns:
            List of dictionaries in Zulip API format
            
        Example:
            filters = NarrowHelper.build_basic_narrow(stream="general")
            api_narrow = NarrowHelper.to_api_format(filters)
        """
        return [f.to_dict() for f in narrow_filters]
    
    @staticmethod
    def from_dict_list(dict_list: List[Dict[str, Any]]) -> List[NarrowFilter]:
        """Convert dictionary list to NarrowFilter objects.
        
        Args:
            dict_list: List of dictionaries in Zulip API format
            
        Returns:
            List of NarrowFilter objects
            
        Example:
            api_narrow = [{"operator": "stream", "operand": "general"}]
            filters = NarrowHelper.from_dict_list(api_narrow)
        """
        return [NarrowFilter.from_dict(d) for d in dict_list]
    
    @staticmethod
    def combine_narrows(*narrow_lists: List[NarrowFilter]) -> List[NarrowFilter]:
        """Combine multiple narrow filter lists.
        
        Args:
            *narrow_lists: Variable number of narrow filter lists
            
        Returns:
            Combined list of NarrowFilter objects
            
        Example:
            stream_narrow = NarrowHelper.build_stream_narrow("general")
            time_narrow = [NarrowHelper.last_days(7)]
            combined = NarrowHelper.combine_narrows(stream_narrow, time_narrow)
        """
        result: List[NarrowFilter] = []
        for narrow_list in narrow_lists:
            result.extend(narrow_list)
        return result

    # ===== VALIDATION AND HELPERS =====
    
    @staticmethod
    def validate_narrow_filters(narrow_filters: List[NarrowFilter]) -> bool:
        """Validate narrow filter list.
        
        Args:
            narrow_filters: List of NarrowFilter objects to validate
            
        Returns:
            True if all filters are valid, False otherwise
            
        Example:
            filters = NarrowHelper.build_basic_narrow(stream="general")
            is_valid = NarrowHelper.validate_narrow_filters(filters)
        """
        try:
            for narrow_filter in narrow_filters:
                # Basic validation - ensure required fields are present
                if not narrow_filter.operator or narrow_filter.operand is None:
                    logger.error(f"Invalid narrow filter: {narrow_filter}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error validating narrow filters: {e}")
            return False
    
    @staticmethod
    def describe_narrow(narrow_filters: List[NarrowFilter]) -> str:
        """Generate a human-readable description of narrow filters.
        
        Args:
            narrow_filters: List of NarrowFilter objects
            
        Returns:
            Human-readable description string
            
        Example:
            filters = NarrowHelper.build_basic_narrow(stream="general", topic="news")
            description = NarrowHelper.describe_narrow(filters)
            # Returns: "stream:general, topic:news"
        """
        if not narrow_filters:
            return "no filters"
        
        descriptions = []
        for narrow_filter in narrow_filters:
            negation = "not " if narrow_filter.negated else ""
            descriptions.append(f"{negation}{narrow_filter.operator.value}:{narrow_filter.operand}")
        
        return ", ".join(descriptions)


# ===== CONVENIENCE FUNCTIONS =====

def build_basic_narrow(
    stream: Optional[str] = None,
    topic: Optional[str] = None,
    sender: Optional[str] = None,
    text: Optional[str] = None,
    **kwargs
) -> List[NarrowFilter]:
    """Convenience function for building basic narrow filters.
    
    This function provides the same interface as the legacy NarrowHelper.build_basic_narrow()
    while leveraging the enhanced v2.5.0 implementation.
    
    Args:
        stream: Stream name to filter by
        topic: Topic name to filter by  
        sender: Sender email to filter by
        text: Text to search for
        **kwargs: Additional filter parameters
        
    Returns:
        List of NarrowFilter objects
        
    Examples:
        # Legacy-compatible usage
        narrow = build_basic_narrow(stream="general", topic="deployment")
        
        # Enhanced usage with new features
        narrow = build_basic_narrow(
            stream="development",
            text="bug fix", 
            has_attachment=True,
            last_days=7
        )
    """
    return NarrowHelper.build_basic_narrow(
        stream=stream,
        topic=topic,
        sender=sender,
        text=text,
        **kwargs
    )


def simple_narrow(
    stream: Optional[str] = None,
    topic: Optional[str] = None,
    sender: Optional[str] = None,
    text: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Create a simple narrow in Zulip API format.
    
    This is the most basic interface, matching the legacy implementation
    exactly while returning the API format directly.
    
    Args:
        stream: Stream name to filter by
        topic: Topic name to filter by
        sender: Sender email to filter by
        text: Text to search for
        
    Returns:
        List of dictionaries in Zulip API format
        
    Example:
        # Drop-in replacement for legacy NarrowHelper.build_basic_narrow()
        narrow = simple_narrow(stream="general", text="deployment")
        # Returns: [{"operator": "stream", "operand": "general"}, 
        #           {"operator": "search", "operand": "deployment"}]
    """
    filters = build_basic_narrow(stream=stream, topic=topic, sender=sender, text=text)
    return NarrowHelper.to_api_format(filters)