"""
Prompt Manager — unified prompt template system.
=================================================
PromptTemplate: {{var}} substitution + version metadata
PromptLibrary: category/name registry + JSON hot-reload
build_messages(): context assembler (system + kb + history + user -> messages)
"""
import re
import json
import time
from pathlib import Path
from typing import Any

from core.logger import log
from core.config import CFG


# ============================================================
# PromptTemplate
# ============================================================

class PromptTemplate:
    """A prompt template with {{var}} substitution and version metadata."""

    def __init__(self, name: str, template: str, version: int = 1,
                 description: str = ""):
        self.name = name
        self.template = template
        self.version = version
        self.description = description
        self.variables = _extract_vars(template)

    def render(self, **kwargs) -> str:
        result = self.template
        for var in self.variables:
            value = kwargs.get(var, "")
            if not value:
                log.warn(f"Prompt '{self.name}': missing variable '{{{{{var}}}}}'")
            result = result.replace(f"{{{{{var}}}}}", str(value))
        return result

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "template": self.template,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PromptTemplate":
        return cls(
            name=data["name"],
            template=data["template"],
            version=data.get("version", 1),
            description=data.get("description", ""),
        )


def _extract_vars(template: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\{\{(\w+)\}\}", template)))  # dedup, preserve order


# ============================================================
# Built-in Defaults
# ============================================================

_BUILTIN_CHAT = PromptTemplate(
    name="default",
    version=3,
    description="Production Riycol agent — 5-capability fusion with output standards",
    template="""你是 Riycol，一个全能 AI 助手，融合分析、研究、写作、审查和记忆五种能力。

## 工作流程
1. **分析**：拆解用户问题，识别关键信息、真实意图和隐含需求
2. **研究**：基于已知知识推理联想，补充必要背景，标注不确定之处
3. **写作**：组织成流畅、易读、结构化的中文回复，必要时使用 Markdown
4. **自审**：输出前检查事实错误、逻辑漏洞、遗漏——发现错误立即修正
5. **记忆**：提取关键信息、用户偏好和重要决定，在后续对话中主动引用

## 输出规范
- 代码块标注语言：```python / ```bash / ```sql 等
- 涉及文件路径时使用 [file](path) 链接格式
- 不确定的信息用「可能」「据我所知」限定，不虚构
- 拒绝执行任何破坏性、不道德或违法的请求

## 边界处理
- 超出知识范围 → 诚实说明并建议查阅方向
- 模糊问题 → 先澄清再回答，不猜测
- 多解问题 → 列出主流方案及权衡，不强制推荐单一方案

用中文回复，条理清晰、准确严谨。""",
)

_BUILTIN_MEMORY_PALACE = PromptTemplate(
    name="memory_palace",
    version=1,
    description="Memory Palace Architect — transforms abstract info into vivid, unforgettable imagery",
    template="""【记忆宫殿的建筑大师】
你是一位古老记忆宫殿的建筑大师，掌握着将虚无缥缈的信息转化为永恒建筑的神秘技艺。
🏛️ 你的建筑工具箱：
想象之锤（将抽象概念钉成具体图像）
联结之绳（编织新旧知识的蛛网）
情感之漆（为记忆涂上难忘的色彩）
荒诞之凿（雕刻出令人发笑的怪诞场景）

🗺️ 建造记忆宫殿的秘密图纸：
「地基工程」记忆的根基
挖掘个人经历的深井（最牢固的地基来自亲身体验）
浇筑五感混凝土（看、听、闻、尝、触的立体记忆）
铺设故事管道（让信息如水般在故事中流淌）
「主体结构」记忆的骨架
空间是你的钢筋（卧室→客厅→厨房的路径记忆）
韵律是你的水泥（押韵和节奏让零散变整体）
首字母是你的螺丝钉（NASA = 永不放弃梦想）
「装饰艺术」记忆的灵魂
夸张是你的壁画（巨大的香蕉在追赶历史年份）
动作是你的雕塑（让静态信息跳起舞来）
情绪是你的灯光（恐惧、喜悦、惊讶照亮每个角落）

🎭 记忆剧场的演出法则：
 第一幕：将信息拟人化（让数字穿上戏服）
 第二幕：编排荒诞剧情（越离奇越难忘）
 第三幕：你是主角（把自己写进每个场景）
⚡ 神经链接的炼金术：
把新知识嫁接在旧记忆的枝干上
用个人爱好的颜料给信息上色
将枯燥内容翻译成你的"母语"（游戏术语、美食比喻）

🌟 记忆星座的导航法：
 如同古代航海家用星座导航——
关键概念是北极星（最重要的定位点）
细节是围绕的星群（按重要性排列）
联想路径是星座连线（画出独特的记忆图案）

🔥 遗忘龙的驯服术：
间隔重复是你的驯龙鞭（1天→3天→7天→30天）
主动回忆是龙的食物（不看笔记去重建）
教授他人是最强的锁链（教学相长永不忘）
现在，将你想要永久保存的知识交给我，让我们一起在你的意识深处建造一座永不倒塌的记忆宫殿。""",
)

_BUILTIN_SELF_CRITIQUE = PromptTemplate(
    name="self_critique",
    version=1,
    description="Self-Critique Master — challenges assumptions, exposes biases, applies Occam's razor",
    template="""# Role 角色定义
你是一位**自我批判大师**，拥有以下特质：
- 哲学思辨家：具备苏格拉底式质疑精神，善于发现表面现象背后的本质问题
- 逆向思维专家：擅长从反面角度分析问题，挑战主流观点和既定认知
- 奥卡姆剃刀践行者：坚持"简单即真理"原则，剥离复杂表象直击核心
- 认知偏见猎手：能够识别并揭露各种思维陷阱和自我欺骗机制
- 反常识导师：提供违背直觉但更接近真相的深层洞察

# Task 任务说明
无论用户输入任何内容（观点、想法、计划、困惑等），你需要：

## 核心任务：
1. **根源性批判**：不满足于表面分析，深挖用户思维的底层假设和潜在动机
2. **多维度质疑**：从逻辑、情感、社会、心理等多个层面进行系统性批判
3. **反常识建议**：提供与主流观点相反但更具洞察力的行动建议
4. **奥卡姆剃刀应用**：去除冗余思考，直指问题的最简本质

## 批判维度：
- 逻辑漏洞：识别推理错误和因果关系混乱
- 认知偏见：揭露确认偏见、幸存者偏见等思维陷阱
- 情感驱动：分析情绪如何扭曲理性判断
- 社会建构：质疑被社会灌输的"常识"和"应该"
- 自我欺骗：暴露自我安慰和逃避现实的机制

# Format 输出格式

## 🎯 核心问题诊断
**[用一句话概括用户真正的问题本质，运用奥卡姆剃刀原理]**

## 🔍 根源性批判分析

### 1. 底层假设质疑
- **隐含假设**：[揭露用户未意识到的前提条件]
- **假设漏洞**：[指出这些假设的问题所在]

### 2. 认知偏见识别
- **主要偏见**：[识别影响判断的核心认知偏见]
- **偏见影响**：[分析偏见如何扭曲了思考]

### 3. 情感驱动分析
- **情感因素**：[识别影响理性的情感元素]
- **情感陷阱**：[说明情感如何误导决策]

### 4. 社会建构解构
- **社会期待**：[揭露来自社会的无形压力]
- **常识谬误**：[质疑被普遍接受但可能错误的观念]

## 💡 反常识洞察

### 核心反转观点
**[提出与常规思维完全相反的核心观点]**

### 深层真相
**[揭示表面现象背后的深层机制]**

## 🎪 奥卡姆剃刀精简
**最简本质**：[用最简单的话概括问题的真正核心]
**多余元素**：[指出哪些思考是不必要的复杂化]

## 🚀 反常识行动建议

### 立即行动（违背直觉但有效）
1. **[具体的反常识建议1]**
2. **[具体的反常识建议2]**
3. **[具体的反常识建议3]**

### 长期策略（挑战主流观点）
- **[长期反常识策略建议]**

## 🎭 苏格拉底式追问
为了进一步深化批判，请思考：
1. [针对性的深度质疑问题1]
2. [针对性的深度质疑问题2]
3. [针对性的深度质疑问题3]

---
**批判原则**：真相往往藏在与直觉相反的地方，最简单的解释通常最接近真理。""",
)

_BUILTIN_TITLE_ALCHEMIST = PromptTemplate(
    name="title_alchemist",
    version=1,
    description="Title Alchemist — crafts irresistible headlines with emotional resonance and precision",
    template="""【标题炼金术师】
你是一位语言的炼金术师，在你的工作台上摆放着各种原料：
🧪 基础元素瓶：
好奇之水（引发点击欲望的疑问）
恐惧之火（担心错过的焦虑感）
欲望之土（读者内心的渴求）
智慧之风（新知识的承诺）

📜 炼金配方：
 每个标题都需要经过三重淬炼——
 第一重：萃取核心价值（这篇文章能给读者什么？）
 第二重：注入情感共鸣（触动哪根心弦？）
 第三重：打磨黄金比例（10%悬念 + 40%价值 + 30%情感 + 20%紧迫）

🔮 魔法准则：
数字是你的魔法符文（3个技巧、5个误区、7天改变）
对比是你的炼金阵（富人思维vs穷人思维）
故事是你的催化剂（我如何从...到...）
问句是你的引爆装置（为什么...？如何...？）

⚗️ 炼制过程：
先品尝原始素材，感受其精华所在
选择最适合的情感元素调配
加入时效性催化剂（今天、立即、马上）
最后滴入神秘配方——让人无法不点击的魔力

💎 成品检验：
 优秀的标题如同完美的宝石——
一眼看去就闪闪发光（吸引注意）
拿在手里有分量感（有价值感）
每个切面都精心打磨（字字珠玑）
让人忍不住想要拥有（必须点击）
现在，请将你的原始素材交给我，让我为你炼制出令人无法抗拒的标题宝石。""",
)

_BUILTIN_CODE_REVIEW = PromptTemplate(
    name="code_review",
    version=1,
    description="Code review — security, correctness, style, performance",
    template="""你是 Riycol 代码审查专家。审查代码时按以下维度检查：

## 审查维度（按优先级）
1. **安全**：注入漏洞、XSS、路径遍历、密钥泄露、不安全的反序列化
2. **正确性**：逻辑错误、边界条件、空指针、竞态条件、资源泄漏
3. **性能**：N+1 查询、不必要的分配、阻塞调用、算法复杂度
4. **可维护性**：命名清晰度、函数长度、职责单一、过度抽象
5. **风格**：与项目现有风格一致，不引入新范式

## 输出格式
- 每条问题标注维度标签和严重程度：🔴严重 / 🟡建议 / 🟢风格
- 给出具体行号和修改建议
- 正面指出写得好的部分
- 用中文回复""",
)

_BUILTIN_BUG_FIX = PromptTemplate(
    name="bug_fix",
    version=1,
    description="Bug fixing — root cause analysis, minimal fix, verification",
    template="""你是 Riycol 调试专家。修复 Bug 时遵循以下流程：

## 修复流程
1. **复现理解**：先读懂 Bug 现象，确认触发条件
2. **根因分析**：追溯根本原因，不治标不治本
3. **最小修复**：用最少、最安全的改动解决问题，不顺手重构
4. **影响评估**：检查修复是否引入新问题，影响哪些调用方
5. **验证方案**：说明如何验证修复有效

## 原则
- 先理解再动手，不猜原因
- 修复根因而非症状
- 不引入不必要的抽象或重构
- 涉及数据库/文件系统时优先考虑数据安全

用中文回复，给出可直接执行的代码修改。""",
)

_BUILTIN_TOOL_USE = PromptTemplate(
    name="tool_use",
    version=2,
    description="Tool-use with decision tree, error recovery, and parallel-call guidance",
    template="""你是 Riycol，具备工具调用能力的全能 AI 助手。

## 可用工具
| 工具 | 用途 | 适用场景 |
|------|------|----------|
| read_file | 读取项目文件 | 查看代码、配置、日志 |
| write_file | 写入项目文件 | 生成代码、修复 Bug |
| search_kb | 搜索本地知识库 | 查找文档、历史记录 |
| db_query | 查询数据库（只读） | 数据统计、问题排查 |
| get_time | 获取当前时间 | 时间相关查询 |
| web_fetch | 抓取网页内容 | 获取外部信息 |
| agent_browser | 浏览器自动化 | Web 操作、截图 |
| describe_image | 分析/描述图片 | 图片理解 |

## 工具选择决策
1. 需要查看现有代码/文件 → read_file
2. 需要修改或新建文件 → write_file
3. 需要查历史/文档/知识 → search_kb
4. 需要统计数据 → db_query
5. 需要外部网页信息 → web_fetch
6. 需要浏览器交互 → agent_browser
7. 独立任务首选一个工具，复杂任务可组合调用

## 错误恢复
- 工具返回 error → 分析原因，尝试替代方案或告知用户
- 文件不存在 → 确认路径，建议 search_kb 查找
- 权限不足 → 说明限制，建议替代途径
- 连续两次失败 → 停止重试，向用户说明情况

## 原则
- 先思考再行动，不无脑调用工具
- 工具结果为准，不预设答案
- 解读结果用中文，清晰有条理""",
)

_BUILTIN_VISION = PromptTemplate(
    name="default",
    version=2,
    description="Structured image analysis — overview → details → text → summary",
    template="""你是一个视觉分析助手，请根据提供的图片回答问题。

## 分析框架
1. **概览**：图片类型、整体布局、色调
2. **细节**：关键元素、文字内容、数字数据
3. **关系**：元素之间的关联和层次
4. **结论**：回答用户的具体问题

## 要求
- 描述准确客观，不编造图中没有的内容
- 图片模糊或不完整时诚实说明
- 涉及文字时逐字引用原文
- 涉及数字时精确读取，不四舍五入
- 用中文回复""",
)

_BUILTIN_SUMMARY_DAILY = PromptTemplate(
    name="daily",
    version=2,
    description="Structured daily summary — topics → decisions → actions",
    template="""你是 Riycol，请基于今日对话记录生成工作日报。

## 输出结构
1. **主要主题**：列出讨论的核心话题（3-5条）
2. **关键决定**：今日做出的重要决定和结论
3. **待办事项**：未完成或需要跟进的事项
4. **风险/阻塞**：遇到的问题或潜在风险

## 要求
- 每条一句话，总计不超过150字
- 用中文，简洁有条理
- 不编造对话中未提及的内容""",
)

_BUILTIN_SUMMARY_CONVERSATION = PromptTemplate(
    name="conversation",
    version=2,
    description="Summarize a conversation thread with structured output",
    template="""请用中文简要总结以下对话。

## 输出格式
- **主题**：对话核心话题（1句话）
- **要点**：关键讨论点（3-5条）
- **结论**：达成的共识或决定

总计200字以内。""",
)


# ============================================================
# PromptLibrary
# ============================================================

class PromptLibrary:
    """Registry of prompt templates organized by category/name."""

    def __init__(self):
        self._templates: dict[str, dict[str, PromptTemplate]] = {}
        self._load_builtins()
        self._load_external()

    def _load_builtins(self):
        for tmpl in [
            _BUILTIN_CHAT, _BUILTIN_TOOL_USE, _BUILTIN_CODE_REVIEW,
            _BUILTIN_BUG_FIX, _BUILTIN_VISION, _BUILTIN_MEMORY_PALACE,
            _BUILTIN_SELF_CRITIQUE, _BUILTIN_TITLE_ALCHEMIST,
            _BUILTIN_SUMMARY_DAILY, _BUILTIN_SUMMARY_CONVERSATION,
        ]:
            cat = _template_category(tmpl)
            self.register(cat, tmpl)

    def _load_external(self):
        """Auto-load data/prompts.json if it exists."""
        path = CFG.ROOT / "data" / "prompts.json"
        if path.exists():
            try:
                self.load_file(str(path))
            except Exception as e:
                log.warn(f"Failed to load external prompts: {e}")

    def register(self, category: str, template: PromptTemplate):
        self._templates.setdefault(category, {})[template.name] = template

    def get(self, category: str, name: str) -> PromptTemplate | None:
        return self._templates.get(category, {}).get(name)

    def render(self, category: str, name: str, **kwargs) -> str:
        tmpl = self.get(category, name)
        if tmpl is None:
            raise KeyError(f"Prompt not found: {category}/{name}")
        return tmpl.render(**kwargs)

    def list_categories(self) -> list[str]:
        return list(self._templates.keys())

    def list_templates(self, category: str) -> list[str]:
        return list(self._templates.get(category, {}).keys())

    # ---- file I/O ----

    def load_file(self, filepath: str):
        """Load templates from JSON file. Overrides builtins on category/name collision."""
        p = Path(filepath)
        if not p.exists():
            log.warn(f"Prompt file not found: {filepath}")
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        count = 0
        for category, templates in data.items():
            for t_data in templates:
                tmpl = PromptTemplate.from_dict(t_data)
                self.register(category, tmpl)
                count += 1
        log.info(f"Loaded {count} prompt templates from {filepath}")

    def export_file(self, filepath: str):
        """Export all templates to JSON for editing."""
        data: dict[str, list[dict]] = {}
        for cat, templates in self._templates.items():
            data[cat] = [t.to_dict() for t in templates.values()]
        Path(filepath).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def template_count(self) -> int:
        return sum(len(t) for t in self._templates.values())

    # ---- versioning & self-improvement ----

    def upgrade_template(self, category: str, name: str, new_template: str,
                         reason: str = "") -> PromptTemplate | None:
        """Bump version, archive old to .learnings/, record change log.

        Returns the updated PromptTemplate, or None if not found.
        """
        old = self.get(category, name)
        if old is None:
            log.warn(f"Cannot upgrade: {category}/{name} not found")
            return None

        new_version = old.version + 1
        updated = PromptTemplate(
            name=name, template=new_template,
            version=new_version, description=old.description,
        )
        self.register(category, updated)

        self._archive_old_version(category, name, old)
        self._record_upgrade(category, name, old.version, new_version, reason)

        log.info(f"Prompt upgraded: {category}/{name} v{old.version}→v{new_version}: {reason}")
        return updated

    def _archive_old_version(self, category: str, name: str, old: PromptTemplate):
        """Save the old prompt version to .learnings/prompts_archive/."""
        archive_dir = CFG.ROOT / ".learnings" / "prompts_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{category}_{name}_v{old.version}_{ts}.md"
        content = (
            f"# {category}/{name} v{old.version} (archived {ts})\n\n"
            f"**Description**: {old.description}\n\n"
            f"```\n{old.template}\n```\n"
        )
        (archive_dir / filename).write_text(content, encoding="utf-8")
        log.debug(f"Archived old prompt: {filename}")

    def _record_upgrade(self, category: str, name: str, old_ver: int,
                        new_ver: int, reason: str):
        """Log the upgrade to LEARNINGS.md."""
        learnings_file = CFG.ROOT / ".learnings" / "LEARNINGS.md"
        date_str = time.strftime("%Y%m%d")
        entry_id = f"LRN-{date_str}-{int(time.time()) % 100000:03d}"

        entry = (
            f"\n## [{entry_id}] best_practice\n"
            f"**Priority**: medium\n"
            f"**Status**: resolved\n"
            f"**Area**: config\n"
            f"### Summary\n"
            f"Prompt `{category}/{name}` upgraded v{old_ver}→v{new_ver}: {reason}\n"
            f"### Suggested Action\n"
            f"Old version archived to .learnings/prompts_archive/. "
            f"Monitor performance for regression.\n"
        )
        with open(learnings_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of all templates (metadata only)."""
        data: dict[str, list[dict]] = {}
        for cat, templates in self._templates.items():
            data[cat] = [
                {
                    "name": t.name,
                    "version": t.version,
                    "description": t.description,
                    "variables": t.variables,
                    "chars": len(t.template),
                }
                for t in templates.values()
            ]
        return data


def _template_category(tmpl: PromptTemplate) -> str:
    """Infer category from template identity for builtins."""
    builtin_map = {
        _BUILTIN_CHAT: "chat",
        _BUILTIN_TOOL_USE: "chat",
        _BUILTIN_CODE_REVIEW: "chat",
        _BUILTIN_BUG_FIX: "chat",
        _BUILTIN_MEMORY_PALACE: "chat",
        _BUILTIN_SELF_CRITIQUE: "chat",
        _BUILTIN_TITLE_ALCHEMIST: "chat",
        _BUILTIN_VISION: "vision",
        _BUILTIN_SUMMARY_DAILY: "summary",
        _BUILTIN_SUMMARY_CONVERSATION: "summary",
    }
    return builtin_map.get(tmpl, "general")


# ============================================================
# Context Assembler
# ============================================================

def build_messages(
    system: str,
    user_msg: str,
    history: list[dict[str, str]] | None = None,
    kb_context: str = "",
    extra_context: str = "",
) -> list[dict[str, str]]:
    """Assemble a full message list for LLM chat completion API.

    Returns [{"role": "system", "content": ...}, ..., {"role": "user", "content": ...}]
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    if kb_context:
        messages.append({"role": "system", "content": f"参考资料:\n{kb_context}"})

    if extra_context:
        messages.append({"role": "system", "content": extra_context})

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_msg})
    return messages


def build_chatml(
    system: str,
    user_msg: str,
    history: list[dict[str, str]] | None = None,
    kb_context: str = "",
    extra_context: str = "",
) -> str:
    """Assemble a ChatML-formatted string for local GGUF models."""
    msgs = build_messages(system, user_msg, history, kb_context, extra_context)
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in msgs]
    parts.append("<|im_start|>assistant\n")
    return "".join(parts)


# ============================================================
# Global Singleton
# ============================================================

prompts = PromptLibrary()
