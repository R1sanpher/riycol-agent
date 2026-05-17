"""
Generate training data by using the Agent Swarm to create diverse Q&A pairs.
Usage: python data/training/generate_data.py [count] [--domain all|coding|writing|qa|tools]
"""
import sys, os, json, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.db import DB
from core.logger import log
from core.config import CFG

SEED_TOPICS = {
    "coding": [
        "写一个Python函数读取JSON文件并返回指定key的值",
        "如何用Python实现LRU缓存",
        "解释Python装饰器的原理并给出示例",
        "如何在Git中撤销最近一次commit",
        "写一个SQL查询找出重复记录",
        "如何用Python异步处理HTTP请求",
        "解释RESTful API设计原则",
        "写一个简单的Flask路由处理文件上传",
        "Python列表推导式和生成器表达式的区别",
        "如何用正则表达式匹配邮箱地址",
    ],
    "writing": [
        "写一封正式的商务邮件通知团队周五有部署",
        "用中文写一篇200字的技术博客摘要",
        "写一份项目的README文档大纲",
        "用3句话总结敏捷开发的核心思想",
        "写一段产品功能介绍文案（面向用户）",
        "如何写好一段代码注释",
        "写一份Bug报告的模板",
        "写一段激励团队的技术分享开场白",
    ],
    "qa": [
        "什么是向量数据库？为什么AI需要它？",
        "解释LoRA微调的原理",
        "RAG和微调有什么区别？各适合什么场景？",
        "什么是Transformer的注意力机制？",
        "解释embedding在NLP中的作用",
        "什么是CI/CD？有什么好处？",
        "Docker和虚拟机有什么区别？",
        "什么是WebSocket？什么时候用它？",
    ],
    "tools": [
        "用Python调用OpenAI API发送一个简单的对话请求",
        "如何用requests库下载文件并显示进度条",
        "用argparse写一个CLI工具的框架",
        "如何用Python操作SQLite数据库",
        "写一个Python脚本监控CPU和内存使用率",
        "如何用subprocess执行系统命令并捕获输出",
    ],
}


def generate_samples(count: int, domains: list[str]):
    from plugins.agent import AgentSwarm
    swarm = AgentSwarm()

    topics: list[tuple[str, str]] = []
    for d in domains:
        for t in SEED_TOPICS.get(d, []):
            topics.append((d, t))
    random.shuffle(topics)
    topics = topics[:count]

    inserted = 0
    for i, (domain, topic) in enumerate(topics):
        try:
            prompt = f"{topic}\n\n请提供清晰、完整的中文回答。"
            result = swarm.run(prompt)
            if result and len(result) > 20:
                DB.add_sample(
                    instruction=topic,
                    output=result,
                    source="agent_generated",
                    dataset=domain,
                    quality=0.8,
                )
                inserted += 1
                log.info(f"[Gen {i+1}/{len(topics)}] {domain}: {topic[:40]}...")
            else:
                log.warn(f"[Gen {i+1}/{len(topics)}] Too short: {len(result)} chars")
        except Exception as e:
            log.error(f"[Gen {i+1}/{len(topics)}] Failed: {e}")

    return inserted


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    domain_arg = sys.argv[2] if len(sys.argv) > 2 else "all"
    domains = ["coding", "writing", "qa", "tools"] if domain_arg == "all" else [domain_arg]

    print(f"Generating {count} training samples across: {domains}")
    print(f"Using Agent Swarm (DeepSeek API)")
    print("=" * 50)

    inserted = generate_samples(count, domains)

    print(f"\nDone: {inserted}/{count} samples added")
    print(f"Run 'python data/training/train.py all' to rebuild the dataset")


if __name__ == "__main__":
    main()
