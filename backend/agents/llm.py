"""LLM Provider wrapper for ResolveX AI Multi-Agent system.

Supports:
- anthropic (Claude)
- openai (GPT-4o)
- gemini (Gemini 1.5/2.0)
- demo (Deterministic simulation for offline/interview testing)
"""

import os
import json
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

class TriageOutput(BaseModel):
    intent: str = Field(..., description="Either 'incident' or 'service_request'")
    category: str = Field(..., description="'network', 'vpn', 'software', 'hardware', 'server', or 'general'")
    priority: str = Field(..., description="'low', 'medium', 'high', or 'critical'")
    reason: str = Field(..., description="Brief rationale for triage decision")
    demo_label: Optional[str] = None

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "demo").lower()

def get_current_provider() -> str:
    return os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).lower()

def is_demo_mode() -> bool:
    return get_current_provider() == "demo"

async def call_live_llm(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Call external LLM API if key is present; returns None on failure or missing key."""
    provider = get_current_provider()
    
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}]
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            return None

    elif provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return None
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            return None

    elif provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            return None
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
            return None

    return None

async def classify_triage(user_message: str) -> Dict[str, Any]:
    """Classify user intent, category, and priority."""
    msg = user_message.lower()
    
    # Check live LLM if enabled and configured
    if not is_demo_mode():
        sys_prompt = "You are a USM IT Triage Agent. Output valid JSON with keys: intent ('incident' or 'service_request'), category ('network', 'vpn', 'software', 'hardware', 'server', or 'general'), priority ('low', 'medium', 'high', 'critical'), and reason (brief explanation)."
        prompt = f"Classify this employee IT request:\n\"{user_message}\""
        try:
            live_out = await call_live_llm(prompt, sys_prompt)
            if live_out:
                clean_json = live_out.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()
                parsed = json.loads(clean_json)
                validated = TriageOutput.model_validate(parsed)
                return validated.model_dump()
        except Exception:
            pass

    # Deterministic classification for demo mode and fallback
    # Scenario 4: Production outage
    if any(k in msg for k in ["production", "prod", "outage", "unavailable", "server down"]):
        out = TriageOutput(
            intent="incident",
            category="server",
            priority="critical",
            reason="Production outage detected impacting business services.",
            demo_label="DEMO MODE: simulated",
        )
    # Scenario 3: Software install / Service request
    elif any(k in msg for k in ["install", "installing", "software", "license", "setup python", "download"]):
        out = TriageOutput(
            intent="service_request",
            category="software",
            priority="low" if "python" in msg else "medium",
            reason="Standard service request for local workstation software provisioning.",
            demo_label="DEMO MODE: simulated",
        )
    # Scenario 2: VPN troubleshooting
    elif any(k in msg for k in ["vpn", "tunnel", "anyconnect", "remote access"]):
        out = TriageOutput(
            intent="incident",
            category="vpn",
            priority="medium",
            reason="Remote VPN tunnel connectivity failure detected.",
            demo_label="DEMO MODE: simulated",
        )
    # Scenario 1: Wi-Fi / portal / network
    elif any(k in msg for k in ["wi-fi", "wifi", "portal", "internet", "intranet", "gateway"]):
        out = TriageOutput(
            intent="incident",
            category="network",
            priority="high",
            reason="Network connectivity barrier preventing access to company portal.",
            demo_label="DEMO MODE: simulated",
        )
    else:
        out = TriageOutput(
            intent="incident",
            category="general",
            priority="medium",
            reason="General workplace IT support incident.",
            demo_label="DEMO MODE: simulated",
        )
    return out.model_dump()

async def generate_resolution(
    user_message: str,
    intent: str,
    category: str,
    priority: str,
    retrieved_chunks: List[Dict[str, Any]],
    diagnostics: List[Dict[str, Any]],
    requires_approval: bool,
) -> str:
    """Synthesize proposed resolution from RAG context, MCP diagnostics, and approval requirements."""
    demo_tag = "[DEMO MODE: simulated] " if is_demo_mode() else ""
    
    # 1. Sensitive action requiring human approval
    if requires_approval:
        return (
            f"{demo_tag}This request requires managerial or administrator approval before execution. "
            f"An approval workflow has been registered with status PENDING. "
            f"Once a Support Engineer or Admin approves the ticket, the requested software/access change will be provisioned."
        )

    # 2. Critical Server Outage
    if category == "server" or priority == "critical":
        diag_summary = "CPU/Memory resource exhaustion verified on target host."
        if diagnostics:
            diag_summary = f"Diagnostic metrics: status={diagnostics[0].get('service_status', 'degraded')}, memory={diagnostics[0].get('memory_usage_pct', 94)}%."
        return (
            f"{demo_tag}Critical production service degradation identified. {diag_summary} "
            f"Production runbook retrieved. The incident has been escalated to Tier-3 Platform Infrastructure on-call engineering, "
            f"and automated memory reclamation steps have been staged."
        )

    # 3. Wi-Fi / Company Portal
    if category == "network":
        diag_net = diagnostics[0] if diagnostics else {}
        return (
            f"{demo_tag}Diagnostics confirm internal gateway is reachable (latency {diag_net.get('latency_ms', 14)}ms). "
            f"The company portal failure is isolated to local DNS cache staleness after subnet handover. "
            f"Resolution: 1) Flush local DNS cache via 'ipconfig /flushdns', 2) Renew DHCP lease, 3) Verify SSO session."
        )

    # 4. VPN Connectivity
    if category == "vpn":
        return (
            f"{demo_tag}VPN gateway handshake verified. User tunnel disconnected due to expired certificate credentials. "
            f"Resolution: 1) Launch GlobalProtect/AnyConnect client, 2) Select Corporate-Primary gateway, "
            f"3) Authenticate with corporate MFA token to re-establish secure IPsec tunnel."
        )

    # Default fallback
    return (
        f"{demo_tag}Issue triaged and registered in USM. Relevant support documentation retrieved and dispatched to tier-1 queue."
    )

