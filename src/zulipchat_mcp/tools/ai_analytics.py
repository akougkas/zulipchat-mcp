"""AI-powered analytics tools for ZulipChat MCP.

High-level analytical tools that generate insights with a server-side LLM
provider (src/zulipchat_mcp/core/llm.py). MCP sampling was deprecated in the
2026-07-28 protocol, so analytics run against a provider owned by
this server (ANTHROPIC_API_KEY) instead of delegating generation to the
client.
"""

import asyncio
from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from ..config import bind_client, get_client
from ..core.llm import LLMUnavailableError, generate
from .registration import register_tool


def _excerpt(content: str, limit: int) -> str:
    return content[:limit] + ("..." if len(content) > limit else "")


def _sampling_metadata(
    messages: list[dict[str, Any]],
    excerpts: list[dict[str, Any]],
    *,
    char_limit: int,
    fetch_limit: int,
    requested_streams: list[str],
    included_streams: list[str],
    custom_prompt: str | None,
) -> dict[str, Any]:
    """Describe the bounded summary without implying an exhaustive analysis."""
    data_in_prompt = not custom_prompt or "{data}" in custom_prompt
    return {
        "fetched_message_count": len(messages),
        "excerpt_count": len(excerpts),
        "omitted_message_count": len(messages) - len(excerpts),
        "truncated_excerpt_count": sum(
            len(message["content"]) > char_limit for message in excerpts
        ),
        "excerpt_char_limit": char_limit,
        "fetch_limit_per_stream": fetch_limit,
        "requested_streams": requested_streams,
        "included_streams": included_streams,
        "omitted_streams": [
            stream for stream in requested_streams if stream not in included_streams
        ],
        "exhaustive": False,
        "data_in_prompt": data_in_prompt,
        "llm_input_excerpt_count": len(excerpts) if data_in_prompt else 0,
    }


async def get_daily_summary(
    streams: list[str] | None = None,
    hours_back: int = 24,
) -> dict[str, Any]:
    """Get basic daily message summary (no complex analytics)."""
    client = get_client()

    try:
        summary = await asyncio.to_thread(
            client.get_daily_summary, streams=streams, hours_back=hours_back
        )

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
    """Fetch stream data and analyze with LLM for sophisticated insights.

    Requires a server-side LLM provider (ANTHROPIC_API_KEY); MCP sampling was
    deprecated in the 2026-07-28 protocol.
    """
    with bind_client(get_client()):
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
            excerpts = messages[:20]
            sampling = _sampling_metadata(
                messages,
                excerpts,
                char_limit=150,
                fetch_limit=100,
                requested_streams=[stream_name],
                included_streams=[stream_name] if excerpts else [],
                custom_prompt=custom_prompt,
            )
            if not messages:
                return {
                    "status": "success",
                    "analysis": "No messages found for analysis",
                    "message_count": 0,
                    "sampling": sampling,
                }

            # Prepare data for LLM
            data_summary = (
                f"Stream: #{stream_name} ({time_period}); fetched sample: {len(messages)} "
                f"messages; showing {len(excerpts)} excerpts, at most 150 characters each. "
                "This is not an exhaustive history.\n\n"
            )
            for i, msg in enumerate(excerpts):
                data_summary += (
                    f"{i+1}. {msg['sender']}: {_excerpt(msg['content'], 150)}\n"
                )

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
                analysis_prompt = default_prompts.get(
                    analysis_type,
                    f"Analyze this stream data for {analysis_type}:\n\n{data_summary}",
                )

            # Use server-side LLM provider for analysis
            try:
                analysis_result = await generate(analysis_prompt)
            except LLMUnavailableError as e:
                return {
                    "status": "success",
                    "stream": stream_name,
                    "analysis_type": analysis_type,
                    "time_period": time_period,
                    "message_count": len(messages),
                    "sampling": sampling,
                    "analysis": None,
                    "llm_unavailable": True,
                    "data_summary": data_summary,
                    "note": str(e),
                    "generated_at": datetime.now().isoformat(),
                }
            except Exception as e:
                return {"status": "error", "error": f"LLM analysis failed: {str(e)}"}

            if not analysis_result:
                return {
                    "status": "error",
                    "error": "LLM response missing text content",
                }

            return {
                "status": "success",
                "stream": stream_name,
                "analysis_type": analysis_type,
                "time_period": time_period,
                "message_count": len(messages),
                "sampling": sampling,
                "analysis": analysis_result,
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
    """Analyze team activity across multiple streams with LLM insights.

    Requires a server-side LLM provider (ANTHROPIC_API_KEY).
    """
    with bind_client(get_client()):
        try:
            # Fetch messages from all team streams
            all_messages: list[dict[str, Any]] = []
            for stream in team_streams:
                from .search import search_messages

                search_result = await search_messages(
                    stream=stream,
                    last_hours=days_back * 24,
                    limit=50,  # Token-efficient per stream
                )
                if search_result.get("status") != "success":
                    return {
                        "status": "error",
                        "error": f"Unable to analyze stream '{stream}': {search_result.get('error', 'Search failed')}",
                    }
                if search_result.get("status") == "success":
                    messages = search_result.get("messages", [])
                    all_messages.extend({**msg, "stream": stream} for msg in messages)

            if not all_messages:
                return {
                    "status": "success",
                    "analysis": "No team activity found for analysis",
                    "total_messages": 0,
                    "streams_analyzed": 0,
                    "sampling": _sampling_metadata(
                        [],
                        [],
                        char_limit=100,
                        fetch_limit=50,
                        requested_streams=team_streams,
                        included_streams=[],
                        custom_prompt=custom_prompt,
                    ),
                }

            # Group by stream
            by_stream: dict[str, list[dict[str, Any]]] = {}
            for msg in all_messages:
                stream = msg.get("stream", "Unknown")
                if stream not in by_stream:
                    by_stream[stream] = []
                by_stream[stream].append(msg)

            selected_streams = list(by_stream.items())[:5]
            excerpts = [msg for _, msgs in selected_streams for msg in msgs[:5]]
            sampling = _sampling_metadata(
                all_messages,
                excerpts,
                char_limit=100,
                fetch_limit=50,
                requested_streams=team_streams,
                included_streams=[stream for stream, _ in selected_streams],
                custom_prompt=custom_prompt,
            )
            data_summary = (
                f"Team Activity ({days_back} days); fetched sample: {len(all_messages)} "
                f"messages across {len(team_streams)} requested streams. Showing "
                f"{len(excerpts)} excerpts from the first {len(selected_streams)} nonempty "
                "streams in request order, at most 100 characters each. "
                "This is not an exhaustive history.\n\n"
            )
            for stream, msgs in selected_streams:
                data_summary += (
                    f"#{stream} ({len(msgs)} fetched; {len(msgs[:5])} excerpts):\n"
                )
                for msg in msgs[:5]:  # Top 5 messages per stream
                    data_summary += (
                        f"  - {msg['sender']}: {_excerpt(msg['content'], 100)}\n"
                    )
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
                analysis_prompt = default_prompts.get(
                    analysis_focus,
                    f"Analyze team activity for {analysis_focus}:\n\n{data_summary}",
                )

            # Use server-side LLM provider for analysis
            try:
                analysis_result = await generate(analysis_prompt)
            except LLMUnavailableError as e:
                return {
                    "status": "success",
                    "team_streams": team_streams,
                    "analysis_focus": analysis_focus,
                    "days_back": days_back,
                    "total_messages": len(all_messages),
                    "streams_analyzed": 0,
                    "sampling": sampling,
                    "analysis": None,
                    "llm_unavailable": True,
                    "data_summary": data_summary,
                    "note": str(e),
                    "generated_at": datetime.now().isoformat(),
                }
            except Exception as e:
                return {"status": "error", "error": f"LLM analysis failed: {str(e)}"}

            if not analysis_result:
                return {
                    "status": "error",
                    "error": "LLM response missing text content",
                }

            return {
                "status": "success",
                "team_streams": team_streams,
                "analysis_focus": analysis_focus,
                "days_back": days_back,
                "total_messages": len(all_messages),
                "streams_analyzed": (
                    len(selected_streams) if sampling["data_in_prompt"] else 0
                ),
                "sampling": sampling,
                "analysis": analysis_result,
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}


async def intelligent_report_generator(
    report_type: Literal["standup", "weekly", "retrospective", "custom"],
    target_streams: list[str],
    custom_focus: str | None = None,
) -> dict[str, Any]:
    """Generate intelligent reports using LLM analysis of team data.

    Requires a server-side LLM provider (ANTHROPIC_API_KEY).
    """
    try:
        # Fetch recent team activity
        team_activity = await analyze_team_activity_with_llm(
            team_streams=target_streams,
            analysis_focus=custom_focus or report_type,
            days_back=1 if report_type == "standup" else 7,
        )

        if team_activity.get("status") != "success":
            return {
                "status": "error",
                "error": team_activity.get(
                    "error", "Failed to gather team activity data"
                ),
            }

        # If the LLM was unavailable for the underlying analysis, a second LLM
        # call to format a report cannot succeed either. Surface the structured
        # data so the caller can present it directly.
        if team_activity.get("llm_unavailable"):
            return {
                "status": "success",
                "report_type": report_type,
                "target_streams": target_streams,
                "report_content": None,
                "llm_unavailable": True,
                "team_activity": team_activity,
                "note": team_activity.get("note", ""),
                "generated_at": datetime.now().isoformat(),
            }

        sampling = team_activity.get("sampling", {})
        analysis = team_activity.get("analysis", "")
        if sampling:
            analysis += (
                f"\n\nSource coverage: {sampling['llm_input_excerpt_count']} message "
                f"excerpts from a fetched sample of {sampling['fetched_message_count']} "
                "messages, not exhaustive history. Preserve this limitation in the report."
            )

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

        # Generate report with server-side LLM provider
        try:
            report_content = await generate(report_prompt)
        except LLMUnavailableError as e:
            return {
                "status": "success",
                "report_type": report_type,
                "target_streams": target_streams,
                "report_content": None,
                "llm_unavailable": True,
                "team_activity": team_activity,
                "note": str(e),
                "generated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"status": "error", "error": f"Report generation failed: {str(e)}"}

        if not report_content:
            return {
                "status": "error",
                "error": "LLM response missing text content",
            }

        return {
            "status": "success",
            "report_type": report_type,
            "target_streams": target_streams,
            "report_content": report_content,
            "data_analyzed": sampling.get(
                "llm_input_excerpt_count", team_activity.get("total_messages", 0)
            ),
            "sampling": sampling,
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_ai_analytics_tools(mcp: FastMCP) -> None:
    """Register AI-powered analytics tools with the MCP server."""
    register_tool(
        mcp,
        get_daily_summary,
        name="get_daily_summary",
        description="Get basic daily message summary",
        title="Get daily summary",
        idempotent=True,
    )
    register_tool(
        mcp,
        analyze_stream_with_llm,
        name="analyze_stream_with_llm",
        description="Fetch stream data and analyze with LLM for sophisticated insights",
        title="Analyze stream with LLM",
        idempotent=True,
    )
    register_tool(
        mcp,
        analyze_team_activity_with_llm,
        name="analyze_team_activity_with_llm",
        description="Analyze team activity across multiple streams with LLM insights",
        title="Analyze team activity with LLM",
        idempotent=True,
    )
    register_tool(
        mcp,
        intelligent_report_generator,
        name="intelligent_report_generator",
        description="Generate intelligent reports using LLM analysis of team data",
        title="Generate report with LLM",
        idempotent=True,
    )
