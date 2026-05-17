"""
Agent Communication Protocol — in-memory message bus for inter-agent messaging.

Enables agents to send/receive messages during execution, supporting true
multi-agent collaboration beyond simple parallel dispatch.
"""
import uuid, time, queue, threading
from dataclasses import dataclass, field
from typing import Any
from core.logger import log


@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str         # agent name or "*" for broadcast
    type: str             # "request" | "response" | "broadcast" | "handoff"
    payload: Any
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)


class AgentBus:
    """Thread-safe in-memory message bus for agents.

    Each agent gets its own queue. Agents can send to specific agents
    or broadcast to all. Used by AgentSwarm for collaborative execution.
    """

    def __init__(self):
        self._queues: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()

    def _ensure_queue(self, agent_name: str) -> queue.Queue:
        with self._lock:
            if agent_name not in self._queues:
                self._queues[agent_name] = queue.Queue()
            return self._queues[agent_name]

    def send(self, msg: AgentMessage) -> bool:
        """Send a message to a specific agent. Returns True if delivered."""
        try:
            q = self._ensure_queue(msg.to_agent)
            q.put(msg, block=False)
            log.debug(f"AgentBus: {msg.from_agent} -> {msg.to_agent}: {msg.type}")
            return True
        except Exception:
            return False

    def broadcast(self, from_agent: str, payload: Any, msg_type: str = "broadcast") -> int:
        """Send to all agents except sender. Returns count of recipients."""
        count = 0
        with self._lock:
            recipients = [a for a in self._queues.keys() if a != from_agent]
        for agent in recipients:
            msg = AgentMessage(from_agent=from_agent, to_agent=agent, type=msg_type, payload=payload)
            if self.send(msg):
                count += 1
        return count

    def receive(self, agent_name: str, timeout: float = 30) -> AgentMessage | None:
        """Receive next message for agent. Returns None on timeout."""
        try:
            q = self._ensure_queue(agent_name)
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    def pending(self, agent_name: str) -> int:
        """Number of unread messages for agent."""
        with self._lock:
            q = self._queues.get(agent_name)
            return q.qsize() if q else 0

    def clear(self, agent_name: str) -> int:
        """Clear all messages for agent. Returns count removed."""
        count = 0
        with self._lock:
            q = self._queues.get(agent_name)
            if q:
                while not q.empty():
                    try:
                        q.get_nowait()
                        count += 1
                    except queue.Empty:
                        break
        return count
