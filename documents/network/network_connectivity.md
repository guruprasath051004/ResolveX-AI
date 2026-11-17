# Network Connectivity

## Overview
Enterprise network provides wired and Wi‑Fi access to internal resources and the internet. Connectivity issues are categorized by symptom.

## Common Issues
- **Company portal not opening on Wi‑Fi**: Check DNS, proxy, and firewall rules.
- Slow VPN performance.
- Intermittent disconnections.

## Troubleshooting Steps
1. Verify the device is connected to the corporate SSID.
2. Run `ipconfig /all` and confirm the DNS servers are `10.0.0.1` and `10.0.0.2`.
3. Ping `portal.company.com`. If it fails, try `nslookup portal.company.com`.
4. Ensure the Proxy Auto‑Config (PAC) file is reachable at `http://proxy.company.com/pac`. 
5. If the portal still does not load, check the firewall rule `allow_portal_traffic` and request a network admin to verify.

## Category
Network

## Metadata
- Document ID: net-001
- Title: Network Connectivity Guide
- Category: network
- Author: IT Operations
- Version: 1.0
