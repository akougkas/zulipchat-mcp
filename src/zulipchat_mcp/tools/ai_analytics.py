"""AI-powered analytics tools for ZulipChat MCP v2.5.1.

High-level analytical tools that use LLM elicitation for sophisticated insights.
Fetches raw Zulip data and processes with LLM reasoning instead of built-in complexity.
"""

from datetime import datetime, timedelta
from typing import Any, Literal

from fastmcp import FastMCP, Context

from ..core.client import ZulipClientWrapper
from ..config import ConfigManager


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
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Fetch stream data and analyze with LLM for sophisticated insights."""
    if not ctx:
        return {"status": "error", "error": "Context required for LLM analysis"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Calculate time range
        time_periods = {"day": 24, "week": 168, "month": 720}
        hours_back = time_periods.get(time_period, 168)

        # Fetch stream messages
        from .search import search_messages
        search_result = await search_messages(
            stream=stream_name,
            last_hours=hours_back,
            limit=100,  # Token-efficient sample
        )

        if search_result.get("status") != "success":
            return {"status": "error", "error": "Failed to fetch stream data"}

        messages = search_result.get("messages", [])
        if not messages:
            return {"status": "success", "analysis": "No messages found for analysis"}

        # Prepare data for LLM
        data_summary = f"Stream: #{stream_name} ({len(messages)} messages, {time_period})\n\n"
        for i, msg in enumerate(messages[:20]):  # Limit for tokens
            data_summary += f"{i+1}. {msg['sender']}: {msg['content'][:150]}...\n"

        # Create analysis prompt
        if custom_prompt:
            analysis_prompt = custom_prompt.replace("{data}", data_summary)
        else:
            default_prompts = {
                "engagement": f"Analyze engagement patterns in this stream:\n\n{data_summary}\n\nProvide insights on activity levels, participation, and trends.",
                "collaboration": f"Analyze collaboration quality in this stream:\n\n{data_summary}\n\nProvide insights on teamwork, communication patterns, and effectiveness.",
                "sentiment": f"Analyze team sentiment in this stream:\n\n{data_summary}\n\nProvide insights on mood, energy, and team dynamics.",
                "summary": f"Provide a comprehensive summary of this stream:\n\n{data_summary}\n\nInclude key patterns, notable discussions, and insights.",
            }
            analysis_prompt = default_prompts.get(analysis_type, f"Analyze this stream data for {analysis_type}:\n\n{data_summary}")

        # Use LLM for analysis
        try:
            llm_response = await ctx.sample(analysis_prompt)
            analysis_result = llm_response.text.strip()

            return {
                "status": "success",
                "stream": stream_name,
                "analysis_type": analysis_type,
                "time_period": time_period,
                "message_count": len(messages),
                "analysis": analysis_result,
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "error": f"LLM analysis failed: {str(e)}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def analyze_team_activity_with_llm(
    team_streams: list[str],
    analysis_focus: str,
    days_back: int = 7,
    custom_prompt: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Analyze team activity across multiple streams with LLM insights."""
    if not ctx:
        return {"status": "error", "error": "Context required for LLM analysis"}

    config = ConfigManager()
    client = ZulipClientWrapper(config)

    try:
        # Fetch messages from all team streams
        all_messages = []
        for stream in team_streams:
            from .search import search_messages
            search_result = await search_messages(
                stream=stream,
                last_hours=days_back * 24,
                limit=50,  # Token-efficient per stream
            )
            if search_result.get("status") == "success":
                messages = search_result.get("messages", [])
                for msg in messages:
                    msg["stream"] = stream  # Tag with stream
                all_messages.extend(messages)

        if not all_messages:
            return {"status": "success", "analysis": "No team activity found for analysis"}

        # Prepare team data summary
        data_summary = f"Team Activity ({len(all_messages)} messages across {len(team_streams)} streams, {days_back} days):\n\n"

        # Group by stream
        by_stream = {}
        for msg in all_messages:
            stream = msg.get("stream", "Unknown")
            if stream not in by_stream:
                by_stream[stream] = []
            by_stream[stream].append(msg)

        for stream, msgs in list(by_stream.items())[:5]:  # Top 5 streams
            data_summary += f"#{stream} ({len(msgs)} messages):\n"
            for msg in msgs[:5]:  # Top 5 messages per stream
                data_summary += f"  - {msg['sender']}: {msg['content'][:100]}...\n"
            data_summary += "\n"

        # Create analysis prompt
        if custom_prompt:
            analysis_prompt = custom_prompt.replace("{data}", data_summary)
        else:
            default_prompts = {
                "productivity": f"Analyze team productivity from this activity:\n\n{data_summary}\n\nProvide insights on output, focus areas, and productivity patterns.",
                "blockers": f"Identify team blockers and challenges:\n\n{data_summary}\n\nHighlight obstacles, delays, and areas needing support.",
                "energy": f"Assess team energy and morale:\n\n{data_summary}\n\nProvide insights on team spirit, enthusiasm, and well-being.",
                "progress": f"Analyze team progress and achievements:\n\n{data_summary}\n\nIdentify accomplishments, milestones, and forward momentum.",
            }
            analysis_prompt = default_prompts.get(analysis_focus, f"Analyze team activity for {analysis_focus}:\n\n{data_summary}")

        # Use LLM for analysis
        try:
            llm_response = await ctx.sample(analysis_prompt)
            analysis_result = llm_response.text.strip()

            return {
                "status": "success",
                "team_streams": team_streams,
                "analysis_focus": analysis_focus,
                "days_back": days_back,
                "total_messages": len(all_messages),
                "streams_analyzed": len(team_streams),
                "analysis": analysis_result,
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "error": f"LLM analysis failed: {str(e)}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def intelligent_report_generator(
    report_type: Literal["standup", "weekly", "retrospective", "custom"],
    target_streams: list[str],
    custom_focus: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Generate intelligent reports using LLM analysis of team data."""
    if not ctx:
        return {"status": "error", "error": "Context required for report generation"}

    try:
        # Fetch recent team activity
        team_activity = await analyze_team_activity_with_llm(
            team_streams=target_streams,
            analysis_focus=custom_focus or report_type,
            days_back=1 if report_type == "standup" else 7,
            ctx=ctx,
        )

        if team_activity.get("status") != "success":
            return {"status": "error", "error": "Failed to gather team activity data"}

        analysis = team_activity.get("analysis", "")

        # Generate report content based on type
        if report_type == "standup":
            report_prompt = f"""Generate a daily standup report based on this team analysis:

{analysis}

Format as:
**Daily Standup Report**
• Recent accomplishments
• Current focus areas
• Blockers identified
• Team energy level

Keep it concise and actionable."""

        elif report_type == "weekly":
            report_prompt = f"""Generate a weekly team report based on this analysis:

{analysis}

Format as:
**Weekly Team Report**
• Key achievements
• Progress highlights
• Challenges and solutions
• Looking ahead

Make it comprehensive but focused."""

        elif report_type == "retrospective":
            report_prompt = f"""Generate a retrospective analysis based on this team data:

{analysis}

Format as:
**Team Retrospective**
• What went well
• What needs improvement
• Action items
• Team insights

Focus on learning and growth."""

        else:  # custom
            report_prompt = f"""Generate a custom report about: {custom_focus}

Based on this team analysis:
{analysis}

Provide relevant insights and actionable information."""

        # Generate report with LLM
        try:
            llm_response = await ctx.sample(report_prompt)
            report_content = llm_response.text.strip()

            return {
                "status": "success",
                "report_type": report_type,
                "target_streams": target_streams,
                "report_content": report_content,
                "data_analyzed": team_activity.get("total_messages", 0),
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "error": f"Report generation failed: {str(e)}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_ai_analytics_tools(mcp: FastMCP) -> None:
    """Register AI-powered analytics tools with the MCP server."""
    mcp.tool(name="get_daily_summary", description="Get basic daily message summary")(get_daily_summary)
    mcp.tool(name="analyze_stream_with_llm", description="Fetch stream data and analyze with LLM for sophisticated insights")(analyze_stream_with_llm)
    mcp.tool(name="analyze_team_activity_with_llm", description="Analyze team activity across multiple streams with LLM insights")(analyze_team_activity_with_llm)
    mcp.tool(name="intelligent_report_generator", description="Generate intelligent reports using LLM analysis of team data")(intelligent_report_generator)