"""Tests for core/agent_bus.py — AgentBus message protocol."""
import time, pytest, threading
from core.agent_bus import AgentBus, AgentMessage


class TestAgentBus:
    def test_send_receive(self):
        bus = AgentBus()
        msg = AgentMessage(from_agent="A", to_agent="B", type="request", payload="hello")
        assert bus.send(msg) is True
        received = bus.receive("B", timeout=1)
        assert received is not None
        assert received.from_agent == "A"
        assert received.payload == "hello"

    def test_receive_timeout(self):
        bus = AgentBus()
        result = bus.receive("nobody", timeout=0.1)
        assert result is None

    def test_broadcast(self):
        bus = AgentBus()
        bus._ensure_queue("A")
        bus._ensure_queue("B")
        bus._ensure_queue("C")
        count = bus.broadcast("A", "announcement")
        assert count == 2  # B and C, not A
        for agent in ("B", "C"):
            msg = bus.receive(agent, timeout=1)
            assert msg is not None
            assert msg.from_agent == "A"

    def test_pending_count(self):
        bus = AgentBus()
        assert bus.pending("test") == 0
        bus.send(AgentMessage(from_agent="X", to_agent="test", type="request", payload="1"))
        bus.send(AgentMessage(from_agent="Y", to_agent="test", type="request", payload="2"))
        assert bus.pending("test") == 2

    def test_clear(self):
        bus = AgentBus()
        bus.send(AgentMessage(from_agent="X", to_agent="test", type="request", payload="1"))
        bus.send(AgentMessage(from_agent="X", to_agent="test", type="request", payload="2"))
        assert bus.clear("test") == 2
        assert bus.pending("test") == 0

    def test_thread_safety(self):
        bus = AgentBus()
        results = []

        def sender(n):
            for i in range(n):
                bus.send(AgentMessage(from_agent="sender", to_agent="recv", type="request", payload=i))

        def receiver(n):
            count = 0
            deadline = time.time() + 5
            while count < n and time.time() < deadline:
                msg = bus.receive("recv", timeout=0.5)
                if msg:
                    count += 1
            results.append(count)

        t1 = threading.Thread(target=sender, args=(50,))
        t2 = threading.Thread(target=receiver, args=(50,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert results[0] == 50
