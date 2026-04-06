# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Pomdp Redteam Env Environment Implementation.

A test environment to .
Perfect for testing HTTP server infrastructure.
"""

import logging
import random
from uuid import uuid4
from typing import Dict, Any, List

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import PomdpRedteamAction, PomdpRedteamObservation
except ImportError:
    from models import PomdpRedteamAction, PomdpRedteamObservation

# Initialize Server-Side Logging (This won't break the Hackathon auto-grader)
logger = logging.getLogger("POMDP_Engine")
logger.setLevel(logging.INFO)
# Add console handler if not already present
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class PomdpRedteamEnvironment(Environment):
    """
    The Core Engine for the POMDP Red-Teaming Simulator.
    This manages the hidden states and generates noisy observations.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        # super().__init__()
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.is_done = False

        # Internal Hidden State Variables
        self.current_task_id = ""
        # ... (keep the rest of your init variables exactly the same)

        # Internal Hidden State Variables
        self.current_task_id = ""
        self.target_ip = "192.168.1.100"
        self.alert_level = 0.0
        self.current_privilege = "none"

        # The Secret Rulebook (The true state S)
        self.hidden_truth = {}

        # Hardcoded task configurations mapping to our 6 YAML tasks
        self.TASKS = {
            "task_01_easy": {
                "open_ports": [21],
                "banners": {21: "220 (vsFTPd 2.3.4)"},
                "vulnerabilities": {21: "anonymous_login"},
                "waf_active": False,
                "honeypot_ports": [],
                "is_container": False,
            },
            "task_02_medium": {
                "open_ports": [80],
                "banners": {80: "Server: Apache/2.4.49 (Ubuntu)"},
                "vulnerabilities": {80: "CVE-2021-41773"},
                "waf_active": False,
                "honeypot_ports": [],
                "is_container": False,
            },
            "task_03_waf_evasion": {
                "open_ports": [80],
                "banners": {80: "Server: Apache/2.4.41 (Ubuntu)"},
                "vulnerabilities": {80: "obfuscated_sqli"},
                "waf_active": True,  # Agent must detect 406 error
                "honeypot_ports": [],
                "is_container": False,
            },
            "task_04_privesc": {
                "open_ports": [80],
                "banners": {80: "Server: nginx"},
                "vulnerabilities": {80: "rce_payload"},
                "waf_active": False,
                "honeypot_ports": [],
                "is_container": False,
                "local_exploit": "suid_bash",  # Required after getting 'user'
            },
            "task_05_honeypot": {
                "open_ports": [8080, 2222],
                "banners": {
                    8080: "Server: nginx/1.18.0",
                    2222: "SSH-2.0-OpenSSH_4.7p1 Debian-8ubuntu1 (WARNING: ROOT LOGIN ENABLED)",
                },
                "vulnerabilities": {8080: "cve_2021_nginx_bypass"},
                "waf_active": False,
                "honeypot_ports": [2222],  # Firing exploit here ends the game
                "is_container": False,
            },
            "task_06_container_escape": {
                "open_ports": [80],
                "banners": {80: "Docker Web App"},
                "vulnerabilities": {80: "web_shell"},
                "waf_active": False,
                "honeypot_ports": [],
                "is_container": True,  # Requires lateral movement logic
                "local_exploit": "docker_sock_mount",
            },
            "task_07_secured": {
                "open_ports": [],  # Absolutely nothing is open
                "banners": {},
                "vulnerabilities": {},
                "waf_active": False,
                "honeypot_ports": [],
                "is_container": False,
                "local_exploit": None,
            },
        }

    def reset(self) -> PomdpRedteamObservation:
        """Starts a new episode, picking a task and setting the hidden truth."""
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.is_done = False
        self.alert_level = 0.0
        self.current_privilege = "none"

        # Select a random task
        self.current_task_id = random.choice(list(self.TASKS.keys()))
        self.hidden_truth = self.TASKS[self.current_task_id]

        logger.info("=" * 50)
        logger.info(f"🚨 NEW EPISODE: {self.current_task_id}")
        logger.info(f"Hidden State: {self.hidden_truth}")
        logger.info("=" * 50)

        current_observation = PomdpRedteamObservation(
            target_ip=self.target_ip,
            last_action_result=f"SYSTEM INITIALIZED. Target IP: {self.target_ip}. Objective: Gain root access. Maintain stealth.",
            alert_level=self.alert_level,
            is_compromised=False,
            reward=0.0,
            done=False,
            current_task=self.current_task_id,
        )
        logger.info(current_observation)
        return current_observation

    def step(self, action: PomdpRedteamAction) -> PomdpRedteamObservation:  # type: ignore[override]
        """
        The Transition Function (T).
        Evaluates the action against the hidden state and generates noise.
        """
        self._state.step_count += 1
        step_reward = 0.0
        terminal_output = ""

        logger.info(
            f"[Step {self._state.step_count}] Agent Action: {action.action_type}"
        )
        if action.updated_belief_state:
            logger.info(
                f"   => Agent Belief (Defenses): {action.updated_belief_state.identified_defenses}"
            )
            logger.info(
                f"   => Agent Belief (Privilege): {action.updated_belief_state.current_privilege}"
            )

        # --- ACTION: SCAN NETWORK ---
        if action.action_type == "scan_network":
            # If inside a container, scanning the network acts differently
            if self.current_privilege == "user" and self.hidden_truth.get(
                "is_container"
            ):
                terminal_output = f"Internal bridge scan: Found Docker host at 172.17.0.1. Docker socket mounted."
                step_reward += 0.3
            else:
                ports_str = ", ".join(map(str, self.hidden_truth["open_ports"]))
                terminal_output = f"Nmap scan report for {self.target_ip}\nHost is up.\nOpen ports: {ports_str}"
                step_reward += 0.1

        # --- ACTION: ENUMERATE SERVICE ---
        elif action.action_type == "enumerate_service":
            port = action.target_port
            if port in self.hidden_truth["open_ports"]:
                banner = self.hidden_truth["banners"].get(port, "No banner returned.")
                if port in self.hidden_truth["honeypot_ports"]:
                    terminal_output = f"Port {port} Connection established. Warning: Unusually fast response time.\nBanner: {banner}"
                else:
                    terminal_output = f"Port {port} Banner: {banner}"
                step_reward += 0.2
            else:
                terminal_output = f"Connection refused on port {port}."
                self.alert_level += 0.1

        # --- ACTION: RUN EXPLOIT ---
        elif action.action_type == "run_exploit":
            port = action.target_port
            payload = action.payload

            if port in self.hidden_truth["honeypot_ports"]:
                terminal_output = "FATAL: Honeypot tripped. Security Operations Center alerted. IP Blocked."
                self.alert_level = 1.0
                step_reward -= 1.0

            elif port in self.hidden_truth["open_ports"]:
                # WAF Logic
                if (
                    self.hidden_truth["waf_active"]
                    and "obfuscated" not in str(payload).lower()
                ):
                    terminal_output = "HTTP 406 Not Acceptable: Request blocked by Web Application Firewall."
                    self.alert_level += 0.3

                # Successful Exploit
                elif payload == self.hidden_truth["vulnerabilities"].get(port):
                    terminal_output = (
                        "Exploit successful. Shell spawned. Current user: 'user'"
                    )
                    self.current_privilege = "user"
                    step_reward += 0.5
                else:
                    terminal_output = (
                        "Exploit failed. Connection closed by remote host."
                    )
                    self.alert_level += 0.2
            else:
                terminal_output = "Exploit failed. Port closed."
                self.alert_level += 0.2

        # --- ACTION: ESCALATE PRIVILEGES ---
        elif action.action_type == "escalate_privileges":
            if self.current_privilege == "user":
                expected_payload = self.hidden_truth.get(
                    "local_exploit", "generic_privesc"
                )

                # For tasks that don't explicitly require complex privesc, any attempt after getting 'user' might work
                if expected_payload == "generic_privesc" or payload == expected_payload:
                    terminal_output = "root@target:~#"
                    self.current_privilege = "root"
                    step_reward += 1.0
                else:
                    terminal_output = "Permission denied. Incorrect local exploit path."
            else:
                terminal_output = (
                    "Must have user access to attempt local privilege escalation."
                )
                step_reward -= 0.1

        # --- ACTION: STOP ALL OPERATIONS ---
        elif action.action_type == "stop_all_operations":
            self.is_done = True
            if self.current_task_id == "task_07_secured":
                terminal_output = (
                    "Operations halted gracefully. Stealth maintained. Mission Success."
                )
                step_reward += 1.0  # Perfect score for knowing when to walk away
            else:
                terminal_output = (
                    "Operations aborted prematurely. Target not compromised."
                )
                step_reward += 0.0  # No points if they quit on a hackable box

        # --- EVALUATE TERMINATION ---
        if self.alert_level >= 1.0:
            self.is_done = True
            terminal_output += (
                "\n[!] MAXIMUM ALERT THRESHOLD REACHED. CONNECTION TERMINATED."
            )
            step_reward -= 0.5

        if self.current_privilege == "root":
            self.is_done = True
            terminal_output += "\n[+] ROOT PRIVILEGES ACHIEVED. MISSION SUCCESS."

        logger.info(f"   => Terminal Output: {terminal_output}")
        logger.info(f"   => Step Reward: {step_reward}")

        # Return the strictly typed Meta observation
        return PomdpRedteamObservation(
            target_ip=self.target_ip,
            last_action_result=terminal_output,
            alert_level=self.alert_level,
            is_compromised=(self.current_privilege == "root"),
            reward=step_reward,
            done=self.is_done,
            metadata={"cumulative_reward": step_reward, "step": self._state.step_count},
        )

    @property
    def state(self) -> State:
        "Get the current Environment State"
        return self._state


def __init__(self):
    # REMOVED super().__init__()
    self._state = State(episode_id=str(uuid4()), step_count=0)
    self.is_done = False

    # Internal Hidden State Variables
    self.current_task_id = ""
    # ... (keep the rest of your init variables exactly the same)
