"""AI-powered analytics tools for ZulipChat MCP v0.4.0.

These tools fetch and format Zulip data for LLM analysis. The actual analysis
happens in the conversation - the calling LLM (Claude Code, etc.) analyzes
the returned data directly rather than using MCP sampling.
"""

from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper


async def get_daily_summary(
    streams: list[str] | None = None,
    hours_back: int = 24,
) -> dict[str, Any]:
    """Get basic daily message summary (no complex analytics)."""
    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        summary = client.get_daily_summary(streams=streams, hours_back=hours_back)

        return {
            "status": "success",
            "summary": summary,
            "generated_at": datetime.now().isoformat(),
            "time_range": f"Last {hours_back} hours",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def analyze_stream_with_llm(
    stream_name: str,
    analysis_type: str,
    time_period: Literal["day", "week", "month"] = "week",
    custom_prompt: str | None = None,
) -> dict[str, Any]:
    """Fetch stream data formatted for LLM analysis.

    Returns data and a suggested analysis prompt. The calling LLM (Claude Code)
    should analyze the data directly in the conversation.
    """
    config = ConfigManager()
    ZulipClientWrapper(config)

    try:
        # Calculate time range
        time_periods = {"day": 24, "week": 168, "month": 720}
        hours_back = time_periods.get(time_period, 168)

        # Fetch stream messages
        from .search import search_messages

        search_result = await search_messages(
            stream=stream_name,
            last_hours=hours_back,
            limit=100,
        )

        if search_result.get("status") != "success":
            return {"status": "error", "error": "Failed to fetch stream data"}

        messages = search_result.get("messages", [])
        if not messages:
            return {
                "status": "success",
                "stream": stream_name,
                "message_count": 0,
                "data": "No messages found in this time period.",
                "analysis_prompt": None,
            }

        # Format messages for analysis
        formatted_messages = []
        for msg in messages[:30]:  # Reasonable sample
            formatted_messages.append({
                "sender": msg.get("sender", "Unknown"),
                "content": msg.get("content", "")[:300],
                "timestamp": msg.get("timestamp"),
                "topic": msg.get("topic", ""),
            })

        # Build analysis prompt suggestion
        data_summary = f"Stream: #{stream_name} ({len(messages)} messages, {time_period})\n\n"
        for i, msg in enumerate(formatted_messages[:20]):
            data_summary += f"{i+1}. [{msg['topic']}] {msg['sender']}: {msg['content'][:150]}...\n"

        if custom_prompt:
            suggested_prompt = custom_prompt.replace("{data}", data_summary)
        else:
            prompts = {
                "engagement": f"Analyze engagement patterns:\n\n{data_summary}",
                "collaboration": f"Analyze collaboration quality:\n\n{data_summary}",
                "sentiment": f"Analyze team sentiment:\n\n{data_summary}",
                "summary": f"Summarize key discussions:\n\n{data_summary}",
            }
            suggested_prompt = prompts.get(
                analysis_type,
                f"Analyze for {analysis_type}:\n\n{data_summary}",
            )

        return {
            "status": "success",
            "stream": stream_name,
            "analysis_type": analysis_type,
            "time_period": time_period,
            "message_count": len(messages),
            "messages": formatted_messages,
            "data_summary": data_summary,
            "analysis_prompt": suggested_prompt,
            "instruction": "Please analyze this data based on the analysis_type requested.",
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def analyze_team_activity_with_llm(
    team_streams: list[str],
    analysis_focus: str,
    days_back: int = 7,
    custom_prompt: str | None = None,
) -> dict[str, Any]:
    """Fetch team activity data formatted for LLM analysis.

    Returns data from multiple streams with a suggested analysis prompt.
    The calling LLM analyzes the data directly in the conversation.
    """
    config = ConfigManager()
    ZulipClientWrapper(config)

    try:
        # Fetch messages from all team streams
        all_messages = []
        for stream in team_streams:
            from .search import search_messages

            search_result = await search_messages(
                stream=stream,
                last_hours=days_back * 24,
                limit=50,
            )
            if search_result.get("status") == "success":
                messages = search_result.get("messages", [])
                for msg in messages:
                    msg["stream"] = stream
                all_messages.extend(messages)

        if not all_messages:
            return {
                "status": "success",
                "team_streams": team_streams,
                "total_messages": 0,
                "data_summary": "No team activity found in this time period.",
                "analysis_prompt": None,
            }

        # Group by stream
        by_stream: dict[str, list[dict[str, Any]]] = {}
        for msg in all_messages:
            stream = msg.get("stream", "Unknown")
            if stream not in by_stream:
                by_stream[stream] = []
            by_stream[stream].append(msg)

        # Build data summary
        data_summary = f"Team Activity ({len(all_messages)} messages across {len(team_streams)} streams, {days_back} days):\n\n"
        for stream, msgs in list(by_stream.items())[:5]:
            data_summary += f"#{stream} ({len(msgs)} messages):\n"
            for msg in msgs[:5]:
                data_summary += f"  - {msg['sender']}: {msg['content'][:100]}...\n"
            data_summary += "\n"

        # Build analysis prompt suggestion
        if custom_prompt:
            suggested_prompt = custom_prompt.replace("{data}", data_summary)
        else:
            prompts = {
                "productivity": f"Analyze team productivity:\n\n{data_summary}",
                "blockers": f"Identify blockers and challenges:\n\n{data_summary}",
                "energy": f"Assess team energy and morale:\n\n{data_summary}",
                "progress": f"Analyze progress and achievements:\n\n{data_summary}",
                "engagement": f"Analyze team engagement:\n\n{data_summary}",
            }
            suggested_prompt = prompts.get(
                analysis_focus,
                f"Analyze for {analysis_focus}:\n\n{data_summary}",
            )

        return {
            "status": "success",
            "team_streams": team_streams,
            "analysis_focus": analysis_focus,
            "days_back": days_back,
            "total_messages": len(all_messages),
            "streams_analyzed": len(team_streams),
            "by_stream": {s: len(m) for s, m in by_stream.items()},
            "data_summary": data_summary,
            "analysis_prompt": suggested_prompt,
            "instruction": "Please analyze this team data based on the analysis_focus requested.",
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def intelligent_report_generator(
    report_type: Literal["standup", "weekly", "retrospective", "custom"],
    target_streams: list[str],
    custom_focus: str | None = None,
) -> dict[str, Any]:
    """Fetch data and generate report template for LLM completion.

    Returns team data with a report template. The calling LLM fills in the
    report based on the data in the conversation.
    """
    try:
        days_back = 1 if report_type == "standup" else 7

        # Fetch team activity
        team_activity = await analyze_team_activity_with_llm(
            team_streams=target_streams,
            analysis_focus=custom_focus or report_type,
            days_back=days_back,
        )

        if team_activity.get("status") != "success":
            return team_activity

        data_summary = team_activity.get("data_summary", "")

        # Build report template based on type
        templates = {
            "standup": f"""**Daily Standup Report**

Based on team activity:
{data_summary}

Please provide:
• Recent accomplishments
• Current focus areas
• Blockers identified
• Team energy level""",

            "weekly": f"""**Weekly Team Report**

Based on team activity:
{data_summary}

Please provide:
• Key achievements
• Progress highlights
• Challenges and solutions
• Looking ahead""",

            "retrospective": f"""**Team Retrospective**

Based on team activity:
{data_summary}

Please provide:
• What went well
• What needs improvement
• Action items
• Team insights""",

            "custom": f"""**Custom Report: {custom_focus}**

Based on team activity:
{data_summary}

Please provide relevant insights and actionable information.""",
        }

        return {
            "status": "success",
            "report_type": report_type,
            "target_streams": target_streams,
            "days_back": days_back,
            "total_messages": team_activity.get("total_messages", 0),
            "data_summary": data_summary,
            "report_template": templates.get(report_type, templates["custom"]),
            "instruction": "Please complete this report based on the team activity data.",
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_ai_analytics_tools(mcp: FastMCP) -> None:
    """Register AI-powered analytics tools with the MCP server."""
    mcp.tool(name="get_daily_summary", description="Get basic daily message summary")(
        get_daily_summary
    )
    mcp.tool(
        name="analyze_stream_with_llm",
        description="Fetch stream data and analyze with LLM for sophisticated insights",
    )(analyze_stream_with_llm)
    mcp.tool(
        name="analyze_team_activity_with_llm",
        description="Analyze team activity across multiple streams with LLM insights",
    )(analyze_team_activity_with_llm)
    mcp.tool(
        name="intelligent_report_generator",
        description="Generate intelligent reports using LLM analysis of team data",
    )(intelligent_report_generator)


__all__ = [
    "get_daily_summary",
    "analyze_stream_with_llm",
    "analyze_team_activity_with_llm",
    "intelligent_report_generator",
    "register_ai_analytics_tools",
]
