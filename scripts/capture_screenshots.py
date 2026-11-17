"""Playwright screenshot capture script for ResolveX AI.

Captures high-resolution screenshots of all 10 UI pages for documentation and presentations:
1. Login Page
2. Employee AI Chat
3. USM Dashboard
4. Incidents Queue
5. Pending Approvals
6. Agent Command Center
7. MCP Server Monitor
8. SLA Compliance
9. Asset CMDB
10. Knowledge Base Admin

Prerequisites:
    pip install playwright
    playwright install chromium

Usage:
    python scripts/capture_screenshots.py --url http://localhost:3000 --output docs/screenshots/
"""

import os
import sys
import time
import argparse
import asyncio

PAGES_TO_CAPTURE = [
    {"name": "01_login_page", "page_id": "login", "title": "Login & Role Selection"},
    {"name": "02_employee_chat", "page_id": "chat", "title": "Employee AI Chat Interface"},
    {"name": "03_usm_dashboard", "page_id": "dashboard", "title": "USM Executive Dashboard"},
    {"name": "04_incidents_queue", "page_id": "incidents", "title": "Incidents Queue & Filtering"},
    {"name": "05_pending_approvals", "page_id": "approvals", "title": "Pending Approvals Workflow"},
    {"name": "06_agent_command_center", "page_id": "command-center", "title": "Agent Command Center (React Flow)"},
    {"name": "07_mcp_monitor", "page_id": "mcp-monitor", "title": "MCP Server Monitor & Tool Audit Log"},
    {"name": "08_sla_compliance", "page_id": "sla", "title": "SLA Policies & Compliance Tracking"},
    {"name": "09_asset_cmdb", "page_id": "assets", "title": "Asset CMDB & Device Diagnostics"},
    {"name": "10_knowledge_base", "page_id": "knowledge", "title": "Knowledge Base & Runbook Admin"},
]

async def capture_all(base_url: str, output_dir: str):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[ERROR] Playwright is not installed. Install with:")
        print("    pip install playwright && playwright install chromium")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    print(f"[INFO] Capturing ResolveX screenshots from {base_url} into {output_dir}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,  # Retina resolution
        )
        page = await context.new_page()

        # 1. Capture Login Page
        print("  -> Capturing 01_login_page.png...")
        await page.goto(base_url)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(output_dir, "01_login_page.png"))

        # 2. Login as Administrator to unlock all platform tabs
        print("  -> Logging in as Administrator...")
        # Click Administrator role button on login page
        admin_button = page.locator("button:has-text('Administrator')")
        if await admin_button.count() > 0:
            await admin_button.click()
            await page.wait_for_timeout(1500)

        # 3. Capture all navigation pages
        for p_info in PAGES_TO_CAPTURE[1:]:
            filename = f"{p_info['name']}.png"
            target_path = os.path.join(output_dir, filename)
            print(f"  -> Capturing {filename} ({p_info['title']})...")

            # Click navigation item in sidebar
            nav_item = page.locator(f"aside button:has-text('{p_info['title'].split(' ')[0]}')")
            if await nav_item.count() > 0:
                await nav_item.first.click()
                await page.wait_for_timeout(1200)

            await page.screenshot(path=target_path)

        await browser.close()
        print(f"[SUCCESS] All screenshots saved to {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Capture ResolveX AI screenshots.")
    parser.add_argument("--url", default="http://localhost:3000", help="Frontend URL")
    parser.add_argument("--output", default="docs/screenshots", help="Output directory")
    args = parser.parse_args()

    asyncio.run(capture_all(args.url, args.output))

if __name__ == "__main__":
    main()

