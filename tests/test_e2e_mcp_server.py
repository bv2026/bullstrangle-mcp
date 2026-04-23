from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bullstrangle_mcp.ingestion import ingest_newsletter


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_server_lists_tools_and_calculates_selectors(tmp_path):
    pdf = Path("data/newsletters/Bull-Strangle-Weekly-Newsletter-For-Week-End-Apr-17-2026.pdf")
    if not pdf.exists():
        pytest.skip(f"Sample newsletter PDF not available: {pdf}")
    db = tmp_path / "bullstrangle.db"
    ingest_newsletter(pdf, db)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "bullstrangle_mcp.mcp_server"],
        env={**os.environ, "BULLSTRANGLE_DB": str(db)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}

            assert "list_newsletters" in tool_names
            assert "calculate_os_selectors" in tool_names
            assert "get_newsletter_by_date" in tool_names
            assert "generate_os_workbook" in tool_names
            assert "ingest_os_workbook" in tool_names
            assert "report_os_run" in tool_names
            assert "aggregate_os_week" in tool_names
            assert "generate_weekend_decisions" in tool_names
            assert "ingest_positions" in tool_names

            result = await session.call_tool(
                "calculate_os_selectors", {"newsletter_date": "2026-04-17"}
            )

    assert result.structuredContent["call_selector_pct"] == 4.0
    assert result.structuredContent["put_selector_pct"] == -3.5
