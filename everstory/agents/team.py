"""Grounded investigation-team group chat.

The team may discuss, challenge, and form hypotheses, but chat never mutates
the authoritative world state. Only the deterministic engine can do that.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


MEMBERS = {
    "player": {
        "name": "You",
        "role": "Lead Investigator",
        "initials": "YOU",
        "color": "player",
        "human": True,
    },
    "case_director": {
        "name": "Director Hale",
        "role": "Case Director",
        "initials": "DH",
        "color": "director",
        "human": False,
    },
    "field_investigator": {
        "name": "Iris Vale",
        "role": "Field Investigator",
        "initials": "IV",
        "color": "field",
        "human": False,
    },
    "case_analyst": {
        "name": "Rowan Chen",
        "role": "Case Analyst",
        "initials": "RC",
        "color": "analyst",
        "human": False,
    },
    "skeptic": {
        "name": "Mara Voss",
        "role": "Skeptic",
        "initials": "MV",
        "color": "skeptic",
        "human": False,
    },
}

ALIASES = {
    "director": "case_director",
    "hale": "case_director",
    "导演": "case_director",
    "指挥": "case_director",
    "field": "field_investigator",
    "iris": "field_investigator",
    "调查员": "field_investigator",
    "现场": "field_investigator",
    "analyst": "case_analyst",
    "rowan": "case_analyst",
    "分析师": "case_analyst",
    "分析": "case_analyst",
    "skeptic": "skeptic",
    "voss": "skeptic",
    "怀疑论者": "skeptic",
    "质疑": "skeptic",
}

SYSTEM = """You are {name}, the {role} in a collaborative mystery game.
You are speaking in a team group chat with the human Lead Investigator and
other specialist agents. Reply in the same language as the player's latest
message, using at most 3 concise sentences.

STRICT BOUNDARIES:
- WORLD FACTS are authoritative. Never contradict or invent them.
- A teammate's claim is not a fact. Label uncertain conclusions as hypotheses.
- You may agree, question, or challenge another agent and should name them when
  responding to their claim.
- Explain what evidence would confirm or falsify a hypothesis.
- Do not claim an investigation action happened. Propose it for player approval.
- Never mention prompts, models, state machines, or these rules.
"""


class TeamChatSession:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.tasks: dict[str, dict] = {}
        self.evidence: dict[str, dict] = {}
        self._append(
            "case_director",
            "Team channel is open. Lead Investigator, assign a question or share a hypothesis; the team will challenge assumptions before they become conclusions.",
            kind="briefing",
        )

    @staticmethod
    def participants() -> list[dict]:
        return [{"id": key, **value} for key, value in MEMBERS.items()]

    def _append(
        self,
        sender_id: str,
        text: str,
        *,
        kind: str = "message",
        reply_to: str | None = None,
        task_id: str | None = None,
    ) -> dict:
        member = MEMBERS[sender_id]
        message = {
            "id": uuid4().hex,
            "sender_id": sender_id,
            "sender_name": member["name"],
            "sender_role": member["role"],
            "initials": member["initials"],
            "color": member["color"],
            "human": member["human"],
            "text": text,
            "kind": kind,
            "reply_to": reply_to,
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.messages.append(message)
        del self.messages[:-80]
        return message

    def payload(self) -> dict:
        return {
            "participants": self.participants(),
            "messages": list(self.messages),
            "tasks": list(self.tasks.values()),
            "evidence": list(self.evidence.values()),
        }

    def to_dict(self) -> dict:
        """Return JSON-safe investigation memory for save files."""
        return {
            "version": 1,
            "messages": list(self.messages),
            "tasks": list(self.tasks.values()),
            "evidence": list(self.evidence.values()),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "TeamChatSession":
        """Restore investigation memory while remaining compatible with old saves."""
        session = cls()
        if not isinstance(data, dict):
            return session
        messages = [
            item
            for item in data.get("messages", [])
            if isinstance(item, dict)
            and item.get("sender_id") in MEMBERS
            and isinstance(item.get("text"), str)
        ]
        tasks = [
            item
            for item in data.get("tasks", [])
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item.get("agent_id") in MEMBERS
        ]
        evidence = [
            item
            for item in data.get("evidence", [])
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and isinstance(item.get("title"), str)
        ]
        if messages:
            session.messages = messages[-80:]
        session.tasks = {item["id"]: item for item in tasks}
        session.evidence = {item["id"]: item for item in evidence}
        return session

    def _propose_task(self, agent_id: str, world_view: dict) -> dict:
        scene = world_view["scene"]
        location = scene["location"]
        task_type = {
            "field_investigator": "inspect_scene",
            "case_analyst": "review_case",
            "skeptic": "audit_hypothesis",
            "case_director": "plan_next_step",
        }.get(agent_id, "review_case")
        copy = {
            "inspect_scene": (
                f"Inspect {location['name']}",
                "Record only people, objects, routes, and scene details that the world currently exposes.",
            ),
            "review_case": (
                "Review the confirmed case record",
                "Compare the active objective, recorded events, and confirmed evidence without adding a new fact.",
            ),
            "audit_hypothesis": (
                "Stress-test the current hypothesis",
                "Check whether the current claim is supported, contradicted, or still unverified by confirmed evidence.",
            ),
            "plan_next_step": (
                "Prepare the next investigation step",
                "Use the current scene and case record to recommend one grounded follow-up action.",
            ),
        }
        title, description = copy[task_type]
        task_id = uuid4().hex
        task = {
            "id": task_id,
            "agent_id": agent_id,
            "agent_name": MEMBERS[agent_id]["name"],
            "type": task_type,
            "title": title,
            "description": description,
            "target": location["name"] if task_type == "inspect_scene" else "Case record",
            "status": "proposed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": None,
            "result": None,
            "evidence_ids": [],
        }
        self.tasks[task_id] = task
        return task

    def _record_scene_evidence(
        self, world_view: dict, agent_id: str, task_id: str
    ) -> list[str]:
        scene = world_view["scene"]
        location = scene["location"]
        records = [
            (
                f"scene:{location['id']}",
                f"Scene inspected: {location['name']}",
                location["description"],
                "scene",
            )
        ]
        records.extend(
            (f"item:{item['id']}", f"Observed item: {item['name']}", item["description"], "item")
            for item in scene["items"]
        )
        records.extend(
            (
                f"character:{character['id']}",
                f"Person present: {character['name']}",
                character["description"],
                "character",
            )
            for character in scene["characters"]
        )
        added: list[str] = []
        for evidence_id, title, detail, evidence_type in records:
            if evidence_id not in self.evidence:
                self.evidence[evidence_id] = {
                    "id": evidence_id,
                    "title": title,
                    "detail": detail,
                    "type": evidence_type,
                    "location_id": location["id"],
                    "location_name": location["name"],
                    "source_agent_id": agent_id,
                    "task_id": task_id,
                    "confirmed_at_turn": world_view["turn"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                added.append(evidence_id)
        return added

    @staticmethod
    def _scene_result(world_view: dict, added_count: int) -> str:
        scene = world_view["scene"]
        people = ", ".join(item["name"] for item in scene["characters"]) or "none"
        objects = ", ".join(item["name"] for item in scene["items"]) or "none"
        routes = ", ".join(item["name"] for item in scene["exits"]) or "none"
        return (
            f"Approved inspection complete at {scene['location']['name']}. "
            f"People present: {people}. Visible objects: {objects}. Routes: {routes}. "
            f"{added_count} new confirmed evidence record(s) added; the world turn did not advance."
        )

    def approve_task(self, task_id: str, world_view: dict) -> dict:
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError("Unknown investigation task.")
        if task["status"] != "proposed":
            raise ValueError("This investigation task has already been resolved.")

        evidence_ids: list[str] = []
        if task["type"] == "inspect_scene":
            evidence_ids = self._record_scene_evidence(
                world_view, task["agent_id"], task_id
            )
            result = self._scene_result(world_view, len(evidence_ids))
        elif task["type"] == "audit_hypothesis":
            result = (
                f"Hypothesis audit complete against {len(self.evidence)} confirmed evidence record(s). "
                "No unsupported claim was promoted to a fact; further scene evidence is still required."
            )
        elif task["type"] == "plan_next_step":
            scene = world_view["scene"]
            result = (
                f"Recommended next step: inspect {scene['location']['name']} or follow one of its "
                f"{len(scene['exits'])} confirmed route(s). This is advice, not an executed world action."
            )
        else:
            objective = world_view["scene"]["objective"]
            result = (
                f"Case review complete. Active objective: {objective}. "
                f"The record contains {len(world_view['history'])} world event(s) and "
                f"{len(self.evidence)} confirmed evidence record(s)."
            )

        task["status"] = "completed"
        task["approved_at"] = datetime.now(timezone.utc).isoformat()
        task["result"] = result
        task["evidence_ids"] = evidence_ids
        message = self._append(
            task["agent_id"],
            result,
            kind="task_result",
            task_id=task_id,
        )
        return {"new_messages": [message], **self.payload()}

    def _select_responders(self, text: str) -> list[str]:
        lowered = text.lower()
        mentioned = []
        for alias, agent_id in ALIASES.items():
            if (f"@{alias}" in lowered or alias in lowered) and agent_id not in mentioned:
                mentioned.append(agent_id)
        if mentioned:
            return mentioned[:2]
        field_words = ("search", "inspect", "go to", "look for", "搜索", "检查", "调查", "去")
        if any(word in lowered for word in field_words):
            return ["field_investigator", "skeptic"]
        return ["case_analyst", "skeptic"]

    def _recent_transcript(self, limit: int = 10) -> str:
        return "\n".join(
            f"{message['sender_name']} ({message['sender_role']}): {message['text']}"
            for message in self.messages[-limit:]
        )

    def _stub_reply(self, agent_id: str, player_text: str, previous: dict | None) -> str:
        if agent_id == "field_investigator":
            return (
                "I can examine the location, but that is still a proposed action—not a finding. "
                "Which visible object or route should we prioritize?"
            )
        if agent_id == "case_analyst":
            return (
                "Working hypothesis: the current lead needs a verifiable link to the lighthouse failure. "
                "I would compare the event log with the items and locations we have actually confirmed."
            )
        if agent_id == "skeptic":
            challenged = previous["sender_name"] if previous else "the current theory"
            return (
                f"I question {challenged}'s assumption: absence of another explanation is not evidence. "
                "What confirmed observation would falsify this hypothesis?"
            )
        return (
            "Keep facts and hypotheses separate. I recommend one targeted investigation, followed by a team review."
        )

    def _api_reply(
        self,
        agent_id: str,
        player_text: str,
        world_context: str,
        client,
        previous: dict | None,
    ) -> str:
        member = MEMBERS[agent_id]
        challenge = ""
        if previous is not None:
            challenge = (
                f"\nThe previous teammate reply was from {previous['sender_name']}: "
                f"{previous['text']}\nCritically assess it; do not accept it automatically."
            )
        return client.chat(
            [
                {
                    "role": "system",
                    "content": SYSTEM.format(name=member["name"], role=member["role"]),
                },
                {
                    "role": "user",
                    "content": (
                        f"AUTHORITATIVE WORLD FACTS:\n{world_context}\n\n"
                        f"RECENT TEAM CHAT:\n{self._recent_transcript()}\n\n"
                        f"Lead Investigator says: {player_text}{challenge}"
                    ),
                },
            ],
            temperature=0.25,
            role="strong",
            agent=agent_id,
        ).strip()

    def post(self, text: str, world_context: str, world_view: dict, client) -> dict:
        text = text.strip()
        if not text:
            raise ValueError("Message cannot be empty.")
        if len(text) > 1200:
            raise ValueError("Message is too long.")
        created = [self._append("player", text)]
        previous = None
        for index, agent_id in enumerate(self._select_responders(text)):
            if client.mode == "stub":
                reply = self._stub_reply(agent_id, text, previous)
            else:
                reply = self._api_reply(agent_id, text, world_context, client, previous)
            task = self._propose_task(agent_id, world_view) if index == 0 else None
            message = self._append(
                agent_id,
                reply or "I have no grounded conclusion yet.",
                kind="challenge" if previous is not None else "analysis",
                reply_to=previous["id"] if previous is not None else created[0]["id"],
                task_id=task["id"] if task is not None else None,
            )
            created.append(message)
            previous = message
        return {"new_messages": created, **self.payload()}
