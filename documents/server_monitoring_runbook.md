# Server Monitoring & Production‑Outage Runbook

## Overview
Procedures to monitor production servers, detect incidents, and execute the outage run‑book.

## Monitoring Stack
- **Prometheus** scrapes metrics from each service.
- **Grafana** dashboards alert on thresholds (CPU>85%, memory>90%, latency>5s).
- **Alertmanager** routes alerts to Slack #prod‑alerts and creates a ticket via the MCP `check_server_health` tool.

## Run‑book Steps (when an alert fires)
1. **Acknowledge** the alert in Alertmanager.
2. **Run** `check_server_health` via the MCP client – this logs diagnostics.
3. If the issue is **resource‑related** (CPU/Memory), attempt to **restart** the affected service.
4. If the issue is **application‑level**, consult the relevant Run‑book document (e.g., `service_x_runbook.md`).
5. **Escalate** to the on‑call engineer if the service does not recover within 10 min.
6. **Update** the incident ticket with timestamps, actions taken, and root‑cause analysis.
7. **Post‑mortem** – after resolution, complete a post‑mortem form and attach to the ticket.

## Category
Operations

## Metadata
- Document ID: runbook-001
- Title: Server Monitoring & Outage Run‑book
- Category: ops
- Author: IT Operations
- Version: 1.0
