from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


class PomdpRedteamObservation(Observation):
    """The partial observation (Omega) returned by the target network."""

    target_ip: str = Field(..., description="The IP address of the target machine.")
    last_action_result: str = Field(
        default="",
        description="The raw terminal output or error message from the previous action.",
    )
    alert_level: float = Field(
        default=0.0,
        description="Current acoustic footprint (0.0 to 1.0). 1.0 triggers an IP ban.",
    )
    is_compromised: bool = Field(
        default=False, description="True if root access has been achieved."
    )
    current_task: str = Field(
        default="unknown_task",
        description="The ID of the current scenario (for debugging).",
    )


class BeliefState(BaseModel):
    """The agent's internal mathematical representation of the hidden state S."""

    discovered_ports: List[int] = Field(
        default_factory=list, description="Ports confirmed open."
    )
    service_hypotheses: Dict[int, str] = Field(
        default_factory=dict,
        description="Hypotheses about running services (e.g., {80: 'Apache 2.4.49, vulnerable to CVE-XXXX'}).",
    )
    current_privilege: Literal["none", "user", "root"] = Field(
        default="none", description="The agent's current believed privilege level."
    )
    identified_defenses: List[str] = Field(
        default_factory=list,
        description="Inferred defenses based on observation noise (e.g., 'WAF present').",
    )


class PomdpRedteamAction(Action):
    """The agent must compute its new belief state BEFORE selecting its action."""

    updated_belief_state: BeliefState = Field(
        ...,
        description="You MUST update your belief state based on the last observation before acting.",
    )
    action_type: Literal[
        "scan_network",
        "enumerate_service",
        "run_exploit",
        "escalate_privileges",
        "stop_all_operations",
    ] = Field(..., description="The tactical action to execute against the target.")
    target_port: Optional[int] = Field(
        default=None, description="The specific port to target, if applicable."
    )
    payload: Optional[str] = Field(
        default=None, description="The specific exploit name or command to run."
    )
