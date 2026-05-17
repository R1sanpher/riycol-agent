"""
token_monitor.py — Token 消耗实时监控桌面程序

启动服务器后运行:
    python token_monitor.py

或连接远程服务器:
    python token_monitor.py --url http://192.168.1.100:8000

监控本身不消耗任何 token —— 仅读取已有统计数据。
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, argparse, threading, queue
from typing import Any

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
except ImportError:
    try:
        import tkinter as tk
        import tkinter.ttk as ttk
        tk  # silence unused
        # Monkey-patch: map ttkbootstrap API to standard tkinter
        ttk = __import__("tkinter.ttk", fromlist=[""])
        ttk.Window = tk.Tk  # type: ignore
        ttk.Frame = tk.Frame  # type: ignore
        ttk.Label = tk.Label  # type: ignore
        ttk.Button = tk.Button  # type: ignore
        ttk.FLAT = tk.FLAT
        ttk.LEFT = tk.LEFT
        ttk.RIGHT = tk.RIGHT
        ttk.X = tk.X
        ttk.Y = tk.Y
        ttk.BOTH = tk.BOTH
        ttk.W = tk.W
        ttk.E = tk.E
        ttk.END = tk.END
        ttk._use_ttkbootstrap = False
    except ImportError:
        print("需要 Tkinter (Python 标准库，通常已内置)")
        sys.exit(1)
else:
    ttk._use_ttkbootstrap = True   # type: ignore[union-attr]
    # Map constants so ttk.X, ttk.LEFT etc. work (same pattern as fallback)
    ttk.X = X; ttk.Y = Y; ttk.BOTH = BOTH
    ttk.LEFT = LEFT; ttk.RIGHT = RIGHT
    ttk.W = W; ttk.E = E; ttk.END = END
    ttk.FLAT = FLAT


# ── 格式化 ──

def fmt(n: int | float) -> str:
    if n is None:
        return "-"
    if isinstance(n, float) and n < 0.01:
        return f"¥{n:.6f}"
    if isinstance(n, float):
        return f"¥{n:.4f}"
    return f"{n:,}"


def source_icon(src: str) -> str:
    return {"server": "\U0001f5a5", "agent": "\U0001f916",
            "telegram": "\U0001f4e1", "planner": "\U0001f9f0",
            "reflection": "\U0001f4ad"}.get(src, "\U00002753")


# ── 数据获取 ──

FETCH_INTERVAL = 3.0        # normal poll interval (seconds)
MAX_BACKOFF = 30.0          # max backoff when server is down
BACKOFF_MULTIPLIER = 1.8    # exponential backoff factor


class DataFetcher:
    """从服务器 API 或持久化文件获取 token 数据。后台线程执行。"""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip("/")
        self._persist_path = os.path.join(
            os.path.dirname(__file__), "data", "token_tracker.json")
        self._last_mtime: float = 0

    def fetch_remote(self) -> dict[str, Any] | None:
        """仅通过 HTTP API 获取。失败返回 None。"""
        try:
            import urllib.request
            resp = urllib.request.urlopen(
                f"{self.server_url}/api/tokens", timeout=3)
            return json.loads(resp.read().decode())
        except Exception:
            return None

    def fetch_file(self) -> dict[str, Any] | None:
        """从持久化文件读取。文件未变更时返回 None。"""
        try:
            if not os.path.exists(self._persist_path):
                return None
            mtime = os.path.getmtime(self._persist_path)
            if mtime == self._last_mtime:
                return None  # unchanged
            self._last_mtime = mtime
            with open(self._persist_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return self._rebuild_snapshot(raw)
        except Exception:
            return None

    def _rebuild_snapshot(self, raw: list[dict]) -> dict[str, Any]:
        total_prompt = sum(r["prompt_tokens"] for r in raw)
        total_completion = sum(r["completion_tokens"] for r in raw)
        total_cost = sum(r["cost"] for r in raw)
        call_count = len(raw)

        by_source: dict[str, dict] = {}
        by_model: dict[str, dict] = {}
        for r in raw:
            s = r["source"]
            ss = by_source.setdefault(s, {"calls": 0, "prompt": 0, "completion": 0})
            ss["calls"] += 1; ss["prompt"] += r["prompt_tokens"]; ss["completion"] += r["completion_tokens"]
            m = r["model"]
            ms = by_model.setdefault(m, {"calls": 0, "prompt": 0, "completion": 0, "cost": 0.0})
            ms["calls"] += 1; ms["prompt"] += r["prompt_tokens"]
            ms["completion"] += r["completion_tokens"]; ms["cost"] = round(ms["cost"] + r["cost"], 4)

        recent = list(reversed(raw[-100:]))
        for r in recent:
            r.setdefault("time_str", time.strftime("%H:%M:%S", time.localtime(r.get("ts", 0))))
            r.setdefault("total_tokens", r.get("prompt_tokens", 0) + r.get("completion_tokens", 0))

        return {
            "total": {"calls": call_count, "prompt_tokens": total_prompt,
                      "completion_tokens": total_completion,
                      "total_tokens": total_prompt + total_completion,
                      "cost": round(total_cost, 4)},
            "by_source": by_source,
            "by_model": by_model,
            "recent": recent,
        }


# ── 主窗口 ──

THEMES = {
    "primary": "#375a7f", "secondary": "#444", "success": "#00bc8c",
    "info": "#3498db", "warning": "#f39c12", "danger": "#e74c3c",
    "light": "#adb5bd", "dark": "#303030",
}
FONT = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_SM = ("Segoe UI", 9)
FONT_BIG = ("Segoe UI", 18, "bold")


class TokenMonitor:
    def __init__(self, server_url: str = ""):
        self.fetcher = DataFetcher(server_url)
        self._data_queue: queue.Queue = queue.Queue()
        self._interval = FETCH_INTERVAL
        self._last_data: dict[str, Any] | None = None
        self._running = True
        self._build_ui()
        threading.Thread(target=self._bg_loop, daemon=True).start()
        self.root.after(100, self._check_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        if getattr(ttk, "_use_ttkbootstrap", False):
            self.root = ttk.Window(themename="superhero", title="Token 消耗监控 — Riycol")
        else:
            self.root = ttk.Window()  # type: ignore[union-attr]
            self.root.title("Token 消耗监控 — Riycol")
        self.root.geometry("820x680")
        self.root.minsize(680, 520)

        # ── Header ──
        header = ttk.Frame(self.root)
        header.pack(fill=ttk.X, padx=14, pady=(10, 4))
        title = ttk.Label(header, text="\U0001f522 Token 消耗监控",
                          font=FONT_TITLE)
        title.pack(side=ttk.LEFT)
        self._status_lbl = ttk.Label(header, text="• 实时", font=FONT_SM,
                                     bootstyle="success")
        self._status_lbl.pack(side=ttk.RIGHT, padx=(6, 0))

        # ── 卡片行 ──
        self._cards: dict[str, ttk.Label] = {}
        card_defs = [
            ("calls",   "总调用次数",       "primary"),
            ("prompt",  "Prompt Tokens",    "success"),
            ("completion", "Completion Tokens", "info"),
            ("total",   "总 Token 数",       "warning"),
            ("cost",    "估算费用 (RMB)",   "danger"),
        ]
        cframe = ttk.Frame(self.root)
        cframe.pack(fill=ttk.X, padx=14, pady=(6, 10))
        cframe.columnconfigure(list(range(5)), weight=1, uniform="card")
        for i, (key, label, bs) in enumerate(card_defs):
            card = ttk.Frame(cframe, bootstyle=bs, padding=6)
            card.grid(row=0, column=i, sticky="nsew", padx=3)
            ttk.Label(card, text=label, font=FONT_SM,
                      bootstyle="light").pack()
            val = ttk.Label(card, text="-", font=FONT_BIG)
            val.pack()
            self._cards[key] = val

        # ── 分解表（按来源 + 按模型）──
        brk = ttk.Frame(self.root)
        brk.pack(fill=ttk.X, padx=14, pady=(0, 6))
        brk.columnconfigure(0, weight=1)
        brk.columnconfigure(1, weight=1)
        sf, self._source_tree = self._make_table(brk, "按来源",
            ["来源", "调用", "Prompt", "Completion"])
        sf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        mf, self._model_tree = self._make_table(brk, "按模型",
            ["模型", "调用", "费用"])
        mf.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # ── 最近记录表 ──
        rframe = ttk.Frame(self.root)
        rframe.pack(fill=ttk.BOTH, expand=True, padx=14, pady=(0, 6))
        ttk.Label(rframe, text="最近调用记录", font=FONT_SM,
                  bootstyle="light").pack(anchor=ttk.W)
        cols = ["时间", "来源", "模型", "Prompt", "Comp", "Total", "费用"]
        self._recent_tree = ttk.Treeview(rframe, columns=cols,
                                           show="headings", height=10)
        self._recent_tree.pack(fill=ttk.BOTH, expand=True)
        for c in cols:
            self._recent_tree.heading(c, text=c)
            anchor = ttk.W if c in ("来源", "模型", "时间") else ttk.E
            width = 58 if c in ("Prompt", "Comp", "Total") else \
                    80 if c == "费用" else \
                    70 if c == "时间" else 80
            self._recent_tree.column(c, width=width, anchor=anchor)
        # Adjust specific column widths
        self._recent_tree.column("来源", width=70)
        self._recent_tree.column("模型", width=70)

        # Treeview tag for row striping
        style = ttk.Style()
        style.configure("Treeview", rowheight=24, font=FONT_SM)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#2a5a8a")])

        # ── Footer ──
        footer = ttk.Frame(self.root)
        footer.pack(fill=ttk.X, padx=14, pady=(0, 8))
        self._footer_lbl = ttk.Label(footer, text="", font=FONT_SM,
                                     bootstyle="light")
        self._footer_lbl.pack(side=ttk.LEFT)
        self._time_lbl = ttk.Label(footer, text="", font=FONT_SM,
                                   bootstyle="light")
        self._time_lbl.pack(side=ttk.RIGHT)

    def _make_table(self, parent, title: str, cols: list[str]) -> tuple:
        frame = ttk.Frame(parent)
        ttk.Label(frame, text=title, font=FONT_SM,
                  bootstyle="light").pack(anchor=ttk.W)
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=4)
        for c in cols:
            tree.heading(c, text=c)
            anchor = ttk.W if c in ("来源", "模型") else ttk.E
            tree.column(c, width=80, anchor=anchor)
        tree.pack(fill=ttk.X, expand=True)
        return frame, tree

    # ── 持久后台线程 + 主线程队列检查 ──

    def _on_close(self):
        """窗口关闭时停止后台线程。"""
        self._running = False
        self.root.destroy()

    def _bg_loop(self):
        """持久后台线程：循环获取数据，不反复创建线程。"""
        while self._running:
            data = self.fetcher.fetch_remote()
            if data is not None:
                self._data_queue.put((data, "remote"))
            else:
                data = self.fetcher.fetch_file()
                self._data_queue.put((data, "file" if data is not None else None))
            time.sleep(self._interval)

    def _check_queue(self):
        """主线程：每 100ms 检查队列并更新 UI。"""
        data = None
        type_ = None
        got_item = False
        try:
            while True:
                data, type_ = self._data_queue.get_nowait()
                got_item = True
        except queue.Empty:
            pass

        if not got_item:
            self.root.after(100, self._check_queue)
            return

        if data is not None:
            self._interval = FETCH_INTERVAL
            self._last_data = data
            self._update_cards(data)
            self._update_breakdowns(data)
            self._update_recent(data)
            if type_ == "remote":
                self._status_lbl.config(text="• 实时")
            else:
                self._status_lbl.config(text="• 离线 (文件)")
        else:
            self._interval = min(self._interval * BACKOFF_MULTIPLIER, MAX_BACKOFF)
            if self._last_data:
                self._update_footer(self._last_data["total"], stale=True)
            else:
                self._clear_display()
                self._footer_lbl.config(text="⚠ 服务器未启动，等待重连中...")

        boot = "success" if data is not None else "secondary"
        if getattr(ttk, "_use_ttkbootstrap", False):
            self._status_lbl.configure(bootstyle=boot)

        self._time_lbl.config(text=f"刷新: {time.strftime('%H:%M:%S')}  |  间隔: {self._interval:.0f}s")
        self.root.after(100, self._check_queue)

    # ── UI 更新 ──

    def _clear_display(self):
        for k in self._cards:
            self._cards[k].config(text="-")
        for t in (self._source_tree, self._model_tree):
            t.delete(*t.get_children())
        self._recent_tree.delete(*self._recent_tree.get_children())

    def _update_cards(self, d: dict):
        t = d["total"]
        self._cards["calls"].config(text=fmt(t["calls"]))
        self._cards["prompt"].config(text=fmt(t["prompt_tokens"]))
        self._cards["completion"].config(text=fmt(t["completion_tokens"]))
        self._cards["total"].config(text=fmt(t["total_tokens"]))
        cost = t["cost"]
        self._cards["cost"].config(text=f"¥{cost:.4f}" if cost >= 0.01 else f"¥{cost:.6f}")
        self._update_footer(t)

    def _update_footer(self, t: dict, stale: bool = False):
        label = f"共 {fmt(t['calls'])} 条"
        if stale:
            label += " · 数据可能不是最新的"
        self._footer_lbl.config(text=label)

    def _update_breakdowns(self, d: dict):
        self._update_tree_incremental(self._source_tree,
            list(sorted(d.get("by_source", {}).items())),
            lambda x: (x[0], fmt(x[1]["calls"]), fmt(x[1]["prompt"]), fmt(x[1]["completion"])))
        self._update_tree_incremental(self._model_tree,
            list(sorted(d.get("by_model", {}).items())),
            lambda x: (x[0], fmt(x[1]["calls"]), fmt(x[1]["cost"])))

    def _update_recent(self, d: dict):
        recent = d.get("recent", [])
        self._update_tree_incremental(self._recent_tree, recent,
            lambda r: (r.get("time_str", ""),
                       f"{source_icon(r.get('source', ''))} {r.get('source', '')}",
                       r.get("model", ""),
                       fmt(r.get("prompt_tokens", 0)),
                       fmt(r.get("completion_tokens", 0)),
                       fmt(r.get("total_tokens", 0)),
                       fmt(r.get("cost", 0))))

    def _update_tree_incremental(self, tree: ttk.Treeview,
                                  items: list[Any],
                                  row_fn) -> None:
        """增量更新 Treeview：只 insert 新行，已有行用 set() 更新。"""
        existing = {tree.set(child, 0): child for child in tree.get_children()}
        seen = set()
        insert_after = ""

        for item in items:
            row = row_fn(item)
            key = str(row[0])
            seen.add(key)
            if key in existing:
                iid = existing[key]
                for col_idx, val in enumerate(row):
                    tree.set(iid, col_idx, val)
                insert_after = iid
                tree.move(iid, "", tree.index(iid))
            else:
                iid = tree.insert("", ttk.END, values=row)
                if insert_after:
                    tree.move(iid, "", tree.index(insert_after) + 1)
                insert_after = iid

        # Remove rows no longer present
        for key, iid in existing.items():
            if key not in seen:
                tree.delete(iid)

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Token 消耗实时监控桌面程序")
    parser.add_argument("--url", default="http://localhost:8000",
                        help="服务器地址 (默认 http://localhost:8000)")
    args = parser.parse_args()

    print("=" * 50)
    print("  Token 监控桌面程序")
    print("=" * 50)
    print(f"  服务器: {args.url}")
    print("  监控本身不消耗任何 token")
    print("  关闭窗口退出\n")

    app = TokenMonitor(server_url=args.url)
    app.run()


if __name__ == "__main__":
    main()
