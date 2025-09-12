# Search API Reference

The search category provides multi-faceted search across Zulip with analytics and insights from message data.

## Tool Overview

| Function | Purpose | Identity Support |
|----------|---------|------------------|
| [`advanced_search()`](#advanced_search) | Multi-faceted search across Zulip | User |
| [`analytics()`](#analytics) | Analytics and insights from message data | User |

## Functions

### `advanced_search()`

Multi-faceted search across messages, users, streams, and topics with advanced filtering and aggregations.

#### Signature
```python
async def advanced_search(
    query: str,
    search_type: Optional[List[Literal["messages", "users", "streams", "topics"]]] = None,
    narrow: Optional[List[NarrowFilter]] = None,
    
    # Advanced search options
    highlight: bool = True,
    aggregations: Optional[List[str]] = None,
    time_range: Optional[TimeRange] = None,
    sort_by: Literal["newest", "oldest", "relevance"] = "relevance",
    limit: int = 100,
    
    # Performance options
    use_cache: bool = True,
    timeout: int = 30
) -> Dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`query`** (str): Search query string

##### Search Options
- **`search_type`** (List[Literal]): Types of content to search (defaults to ["messages"])
  - `"messages"`: Search message content
  - `"users"`: Search user names and emails
  - `"streams"`: Search stream names and descriptions
  - `"topics"`: Search topic names
- **`narrow`** (List[NarrowFilter]): Additional narrow filters for message search

##### Advanced Options
- **`highlight`** (bool): Whether to include search term highlights (default: True)
- **`aggregations`** (List[str]): List of aggregation types to compute
  - `"count_by_user"`: Message count by user
  - `"count_by_stream"`: Message count by stream
  - `"count_by_time"`: Message count over time
  - `"word_frequency"`: Word frequency analysis
  - `"emoji_usage"`: Emoji usage statistics
- **`time_range`** (TimeRange): Time range specification for search
- **`sort_by`** (Literal): Sort order for results ("newest", "oldest", "relevance")
- **`limit`** (int): Maximum number of results to return (1-1000, default: 100)

##### Performance Options
- **`use_cache`** (bool): Whether to use cached results (default: True)
- **`timeout`** (int): Search timeout in seconds (default: 30)

#### Examples

**Basic message search**:
```python
result = await advanced_search("python deployment", search_type=["messages"])
```

**Multi-faceted search with aggregations**:
```python
from zulipchat_mcp.core.validation import NarrowFilter
from zulipchat_mcp.tools.search_v25 import TimeRange

result = await advanced_search(
    query="bug report",
    search_type=["messages", "topics"],
    aggregations=["count_by_user", "count_by_stream"],
    time_range=TimeRange(days=7)
)
```

**Advanced search with filters**:
```python
narrow_filters = [
    NarrowFilter(operator="stream", operand="development")
]

result = await advanced_search(
    query="code review",
    search_type=["messages"],
    narrow=narrow_filters,
    highlight=True,
    sort_by="newest",
    limit=50
)
```

**Search across all content types**:
```python
result = await advanced_search(
    query="project alpha",
    search_type=["messages", "users", "streams", "topics"],
    aggregations=["count_by_user", "word_frequency", "emoji_usage"],
    use_cache=True
)
```

#### Response Format
```python
{
    "status": "success",
    "query": "python deployment",
    "search_types": ["messages"],
    "results": {
        # Messages results (if "messages" in search_type)
        "messages": {
            "count": 47,
            "messages": [
                {
                    # Standard Zulip message object
                    "id": 123456,
                    "content": "Working on Python deployment...",
                    "sender_full_name": "Alice Johnson",
                    # ... other message fields
                    
                    # Highlights (if highlight=True)
                    "highlights": [
                        "Python deployment pipeline",
                        "deployment script ready"
                    ]
                }
            ],
            "has_more": False
        },
        
        # Users results (if "users" in search_type)
        "users": {
            "count": 3,
            "users": [...],  # Matching user objects
            "has_more": False
        },
        
        # Streams results (if "streams" in search_type)
        "streams": {
            "count": 2,
            "streams": [...],  # Matching stream objects
            "has_more": False
        },
        
        # Topics results (if "topics" in search_type)
        "topics": {
            "count": 5,
            "topics": [
                {
                    "name": "deployment",
                    "stream_name": "development",
                    "stream_id": 123,
                    "max_id": 456789,
                    "count": 15
                }
            ],
            "has_more": False
        }
    },
    
    # Aggregations (if requested)
    "aggregations": {
        "messages": {
            "count_by_user": {
                "Alice Johnson": 12,
                "Bob Smith": 8
            },
            "count_by_stream": {
                "development": 15,
                "general": 5
            },
            "count_by_time": {
                "2024-01-15 10:00": 3,
                "2024-01-15 11:00": 5
            },
            "word_frequency": {
                "python": 23,
                "deployment": 18
            },
            "emoji_usage": {
                "thumbs_up": 5,
                "rocket": 3
            }
        }
    },
    
    "metadata": {
        "total_results": 47,
        "search_time": "2024-01-15T10:30:00Z",
        "sort_by": "relevance",
        "limit": 100,
        "from_cache": False
    }
}
```


### `analytics()`

Analytics and insights from message data including activity patterns, sentiment analysis, topic analysis, and participation metrics.

#### Signature
```python
async def analytics(
    metric: Literal["activity", "sentiment", "topics", "participation"],
    narrow: Optional[List[NarrowFilter]] = None,
    group_by: Optional[Literal["user", "stream", "day", "hour"]] = None,
    time_range: Optional[TimeRange] = None,
    
    # Output options
    format: Literal["summary", "detailed", "chart_data"] = "summary",
    include_stats: bool = True
) -> Dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`metric`** (Literal): Type of analytics to compute
  - `"activity"`: Message activity patterns
  - `"sentiment"`: Sentiment analysis (simple word-based)
  - `"topics"`: Topic distribution analysis
  - `"participation"`: User participation metrics

##### Optional Parameters
- **`narrow`** (List[NarrowFilter]): Narrow filters to limit data scope
- **`group_by`** (Literal): How to group the analytics data
  - `"user"`: Group by user
  - `"stream"`: Group by stream
  - `"day"`: Group by day
  - `"hour"`: Group by hour
- **`time_range`** (TimeRange): Time range for analysis (defaults to last 7 days)

##### Output Options
- **`format`** (Literal): Output format for results
  - `"summary"`: Basic summary
  - `"detailed"`: Detailed insights
  - `"chart_data"`: Data formatted for charts
- **`include_stats`** (bool): Whether to include statistical summaries (default: True)

#### Examples

**Activity analysis for last week**:
```python
from zulipchat_mcp.tools.search_v25 import TimeRange

result = await analytics(
    metric="activity",
    time_range=TimeRange(days=7),
    group_by="day"
)
```

**Sentiment analysis for specific stream**:
```python
from zulipchat_mcp.core.validation import NarrowFilter

narrow_filters = [NarrowFilter(operator="stream", operand="general")]
result = await analytics(
    metric="sentiment",
    narrow=narrow_filters,
    format="detailed"
)
```

**Topic analysis with chart data**:
```python
result = await analytics(
    metric="topics",
    time_range=TimeRange(days=30),
    format="chart_data"
)
```

**Participation metrics by user**:
```python
result = await analytics(
    metric="participation",
    group_by="user",
    include_stats=True
)
```

#### Response Format

The response structure varies based on the selected metric:

**Activity Metric Response**:
```python
{
    "status": "success",
    "metric": "activity",
    "time_range": {"days": 7},
    "group_by": "day",
    "format": "summary",
    "data": {
        "activity": {
            "2024-01-08": 23,
            "2024-01-09": 18,
            "2024-01-10": 31
            # ... more days
        },
        "statistics": {  # If include_stats=True
            "total_messages": 156,
            "average": 22.3,
            "max": 31,
            "min": 12,
            "unique_contributors": 8
        }
    },
    "metadata": {
        "analysis_time": "2024-01-15T10:30:00Z",
        "total_messages_analyzed": 156
    }
}
```

**Sentiment Metric Response**:
```python
{
    "status": "success",
    "metric": "sentiment",
    "data": {
        "sentiment": {
            "general": {  # Or grouped by user/stream/day
                "positive": 45,
                "negative": 20,
                "neutral": 35,
                "total": 100,
                "positive_ratio": 0.45,
                "negative_ratio": 0.20
            }
        },
        "overall_distribution": {
            "positive": 45,
            "negative": 20,
            "neutral": 35
        }
    },
    # If format="detailed", includes simple insights
    "detailed_insights": [
        "Overall sentiment: 45.0% positive, 20.0% negative",
        "Generally positive communication tone detected"
    ]
}
```

**Topics Metric Response**:
```python
{
    "status": "success",
    "metric": "topics",
    "data": {
        "topics": {
            "topic_distribution": {
                "meetings": 12,
                "project_management": 8,
                "technical_issues": 15,
                "releases": 3,
                "questions": 7
            },
            "top_words": [
                ["project", 45],
                ["meeting", 32],
                ["deploy", 28]
                # ... more words
            ],
            "total_messages_analyzed": 156
        }
    }
}
```

**Participation Metric Response**:
```python
{
    "status": "success",
    "metric": "participation",
    "group_by": "user",
    "data": {
        "participation": {
            "Alice Johnson": {
                "message_count": 34,
                "unique_topics": 12,
                "unique_streams": 3,
                "avg_message_length": 156.7,
                "total_characters": 5328
            },
            # ... more users
        }
    }
}
```

**Chart Data Format** (when format="chart_data"):
```python
{
    # ... standard response fields ...
    "chart_data": {
        "type": "activity",
        "group_by": "day",
        "series": [
            {"name": "2024-01-08", "value": 23},
            {"name": "2024-01-09", "value": 18}
            # ... more data points
        ]
    }
}
```


## Performance & Caching

### Caching Strategy
- **Search results**: Cached with simple LRU strategy (last 100 searches)
- **Cache key generation**: Based on query, search_type, narrow filters, and options
- **Cache cleanup**: Automatic when cache exceeds 100 entries

### Search Optimization
- **Multi-type search**: Searches across messages, users, streams, and topics in parallel
- **Result limiting**: Each search type respects the limit parameter
- **Stream topic search**: Limited to first 20 streams to prevent timeout

### Performance Considerations
- **Timeout**: Default 30 seconds for search operations
- **Message analysis**: Limited to 1000 messages for analytics
- **Aggregations**: Computed in-memory after retrieval

## Best Practices

### Search Query Design
1. **Use specific terms** - More specific queries return better results
2. **Combine narrow filters** - Use narrow parameter for focused searches
3. **Enable caching** - Use use_cache=True for repeated queries
4. **Set reasonable limits** - Balance between completeness and performance

### Analytics Usage
1. **Use appropriate time ranges** - Smaller ranges perform better
2. **Select single metric** - Each analytics call focuses on one metric type
3. **Group data meaningfully** - Choose group_by that matches your analysis needs
4. **Include stats selectively** - Statistical summaries add processing time

### Aggregations
1. **Request only needed aggregations** - Each aggregation type adds processing
2. **Combine with narrow filters** - Reduce data set before aggregation
3. **Use with appropriate search types** - Aggregations only work with message searches

### Sentiment Analysis Notes
1. **Simple word-based approach** - Uses positive/negative word lists
2. **Not AI-powered** - Basic sentiment detection only
3. **Best for general tone** - May not be accurate for technical content

## Integration Examples

### Search Dashboard
```python
from zulipchat_mcp.tools.search_v25 import TimeRange
from zulipchat_mcp.core.validation import NarrowFilter

async def create_search_dashboard(topics: List[str]):
    dashboard_data = {}
    
    for topic in topics:
        # Search with aggregations
        search_results = await advanced_search(
            query=topic,
            search_type=["messages"],
            aggregations=["count_by_user", "count_by_stream"],
            time_range=TimeRange(days=7),
            use_cache=True
        )
        
        # Generate analytics
        activity_data = await analytics(
            metric="activity",
            time_range=TimeRange(days=7),
            group_by="day"
        )
        
        dashboard_data[topic] = {
            "total_messages": search_results["metadata"]["total_results"],
            "top_contributors": list(search_results["aggregations"]["messages"]["count_by_user"].keys())[:3],
            "daily_average": activity_data["data"].get("statistics", {}).get("average", 0)
        }
    
    return dashboard_data
```

### Team Activity Monitor
```python
async def monitor_team_activity():
    from zulipchat_mcp.core.validation import NarrowFilter
    
    # Set up filters for team stream
    narrow = [NarrowFilter(operator="stream", operand="team")]
    
    # Get participation metrics
    participation = await analytics(
        metric="participation",
        narrow=narrow,
        group_by="user",
        time_range=TimeRange(days=30)
    )
    
    # Get sentiment analysis
    sentiment = await analytics(
        metric="sentiment",
        narrow=narrow,
        format="detailed"
    )
    
    # Get activity patterns
    activity = await analytics(
        metric="activity",
        narrow=narrow,
        group_by="day",
        include_stats=True
    )
    
    return {
        "participation": participation["data"]["participation"],
        "sentiment": sentiment["data"]["overall_distribution"],
        "activity_stats": activity["data"].get("statistics", {}),
        "insights": sentiment.get("detailed_insights", [])
    }
```

### Topic Tracker
```python
async def track_topics_over_time(stream: str):
    narrow = [NarrowFilter(operator="stream", operand=stream)]
    
    # Get topic distribution
    topics = await analytics(
        metric="topics",
        narrow=narrow,
        time_range=TimeRange(days=30)
    )
    
    # Search for top topics
    top_topics = topics["data"]["topics"]["topic_distribution"]
    search_results = {}
    
    for topic_type in list(top_topics.keys())[:3]:  # Top 3 topic types
        results = await advanced_search(
            query=topic_type,
            search_type=["messages", "topics"],
            narrow=narrow,
            limit=10,
            sort_by="newest"
        )
        search_results[topic_type] = results["results"]
    
    return {
        "topic_distribution": top_topics,
        "top_words": topics["data"]["topics"]["top_words"][:10],
        "recent_discussions": search_results
    }
```

---

**Related**: [Messaging API](messaging.md) | [Events API](events.md) | [Streams API](streams.md)