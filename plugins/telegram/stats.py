from collections import Counter
import time

class MessageStats:
    def __init__(self):
        self.received = Counter()
        self.sent = Counter()
        self.date = time.strftime("%Y-%m-%d")

    def record_received(self, user_id: str):
        self.received[user_id] += 1

    def record_sent(self, user_id: str):
        self.sent[user_id] += 1

    def daily_report(self):
        print("=== " + self.date + " 消息统计 ===")
        print("收到消息总数: " + str(sum(self.received.values())))
        print("发送消息总数: " + str(sum(self.sent.values())))
