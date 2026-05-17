import sys, os, time, json, argparse, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _wait_loop(desc="Running"):
    """Common wait loop with KeyboardInterrupt handling."""
    print(f'  {desc}. Ctrl+C to stop.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('  Stopping...')


def cmd_run(args):
    if args.service == 'all':
        from core.plugin_loader import PluginLoader
        loader = PluginLoader()
        loader.discover()
        loader.start_all()
        _wait_loop("Running all plugins")
        print('  Stopping...')
        loader.stop_all()
    elif args.service == 'server':
        from plugins.server import start
        start()
        _wait_loop("Server plugin (HTTP)")
    elif args.service == 'telegram':
        from plugins.telegram import start
        start()
        _wait_loop("Telegram bot")
    elif args.service == 'agent':
        from plugins.agent import start, get_swarm
        start()
        swarm = get_swarm()
        if swarm:
            print(f'  Agent swarm ready: {len(swarm.agents)} agents')
        _wait_loop("Agent swarm")
    elif args.service == 'discord':
        from plugins.discord import start
        start()
        _wait_loop("Discord bot")


def cmd_cmd(args):
    """Generate PowerShell commands from natural language via Ollama."""
    from cli.nl2cmd import generate_command
    try:
        command = generate_command(args.prompt)
        print(command)
        if args.exec:
            import subprocess
            confirm = input("Execute? [y/N]: ").strip().lower()
            if confirm in ('y', 'yes'):
                from core.logger import log
                log.info(f"nl2cmd executing: {command}")
                result = subprocess.run(
                    ["powershell", "-Command", command],
                    capture_output=True, text=True, timeout=60
                )
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                if result.returncode != 0:
                    print(f"Exit code: {result.returncode}")
    except Exception as e:
        print(f"Error: {e}")


def cmd_data(args):
    from core.db import DB
    if args.action == 'stats':
        print(json.dumps(DB.stats(), ensure_ascii=False, indent=2))
    elif args.action == 'build':
        from core.config import CFG
        samples = DB.get_samples('default', limit=args.limit)
        import random
        random.seed(42)
        random.shuffle(samples)
        n = len(samples)
        base = 'distill_' + time.strftime('%Y%m%d')
        exp = CFG.DATA / 'training' / 'exports'
        exp.mkdir(parents=True, exist_ok=True)
        for part, i, j in [('train', 0, int(n * 0.8)),
                           ('val', int(n * 0.8), int(n * 0.9)),
                           ('test', int(n * 0.9), n)]:
            chunk = samples[i:j]
            if not chunk:
                continue
            path = exp / f'{base}_{part}.jsonl'
            with open(path, 'w', encoding='utf-8') as f:
                for s in chunk:
                    f.write(json.dumps({'instruction': s['instruction'], 'output': s['output']}, ensure_ascii=False) + '\n')
            print(f'  [{part}] {len(chunk)} -> {path}')
        print(f'  Done: {n} samples')
    elif args.action == 'export':
        from core.config import CFG
        from core.db import DB
        rows = DB.conn.execute(
            "SELECT session_id, role, content, created_at FROM conversations ORDER BY id ASC"
        ).fetchall()
        sessions: dict[str, list] = {}
        for r in rows:
            sid = r['session_id']
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(r)
        pairs = []
        for sid, msgs in sessions.items():
            for i in range(len(msgs) - 1):
                if msgs[i]['role'] == 'user' and msgs[i + 1]['role'] == 'assistant':
                    pairs.append({'instruction': msgs[i]['content'], 'output': msgs[i + 1]['content']})
        exp = CFG.DATA / 'training' / 'exports'
        exp.mkdir(parents=True, exist_ok=True)
        path = exp / f'conversations_{time.strftime("%Y%m%d_%H%M%S")}.jsonl'
        with open(path, 'w', encoding='utf-8') as f:
            for p in pairs:
                f.write(json.dumps(p, ensure_ascii=False) + '\n')
        print(f'  Exported {len(pairs)} pairs -> {path}')


def cmd_plugin(args):
    from core.plugin_loader import PluginLoader
    loader = PluginLoader()
    names = loader.discover()
    print(f'Plugins: {len(names)}')
    for n in names:
        info = loader.infos.get(n)
        if info:
            print(f'  {info.name} v{info.version} - {info.description}')


def cmd_db(args):
    from core.db import DB
    print(json.dumps(DB.stats(), ensure_ascii=False, indent=2))


def cmd_agent(args):
    if args.action == 'list':
        from plugins.agent import AgentSwarm
        swarm = AgentSwarm()
        print(f'Available agents ({len(swarm.agents)}):')
        for name, agent in swarm.agents.items():
            print(f'  - {name}: {agent.role}')
    elif args.action == 'run':
        if not args.task:
            print('Usage: riycol agent run "<task>"')
            return
        from plugins.agent import AgentSwarm
        swarm = AgentSwarm()
        print(f' Processing: {args.task}')
        print('=' * 50)
        result = swarm.run(args.task)
        print('=' * 50)
        print(result)
    elif args.action == 'review':
        if not args.task:
            print('Usage: riycol agent review "<task>"')
            return
        from plugins.agent import AgentSwarm
        swarm = AgentSwarm()
        print(f' Processing (self-review): {args.task}')
        print('=' * 50)
        result = swarm.run_with_review(args.task)
        print('=' * 50)
        print(result)
    elif args.action == 'record':
        if not args.task:
            print('Usage: riycol agent record "<prompt>"')
            return
        from plugins.agent import AgentSwarm
        swarm = AgentSwarm()
        print(f' Recording: {args.task}')
        print('=' * 50)
        result = swarm.run_with_review(args.task)
        print('=' * 50)
        print(result)


def cmd_crew(args):
    if args.action == 'list':
        print('=' * 50)
        print('Multi-Role Crew (ReAct + Task Decomposition)')
        print('=' * 50)
        print()
        print('Commands:')
        print('  riycol crew run "<task>"         Run with auto-detected roles')
        print('  riycol crew run "<task>" --roles riycol reviewer coder')
        print('  riycol crew roles                  List available roles')
        print()
        print('5 roles available — use --roles to pick')
        from plugins.agent.crew_agent import list_roles as _lr
        for r in _lr():
            print(f"  {r['name']}: {r['goal']}")
    elif args.action == 'roles':
        from plugins.agent.crew_agent import list_roles as _lr
        print('Available crew roles:')
        for r in _lr():
            print(f"  {r['name']}: {r['goal']}")
            print(f"    {r['backstory']}")
            print()
    elif args.action == 'run':
        if not args.task:
            print('Usage: riycol crew run "<task>" [--roles riycol reviewer]')
            return
        from plugins.agent.crew_agent import run_crew, decompose_task
        chosen_roles = args.roles if args.roles else None
        if not chosen_roles:
            subtasks = decompose_task(args.task)
            chosen_roles = [s["role"] for s in subtasks]
            print(f'Auto-detected roles: {chosen_roles}')
        print(f'Task: {args.task}')
        print(f'Roles: {chosen_roles}')
        print('=' * 50)
        result = run_crew(args.task, roles=chosen_roles, model=args.model,
                         process=args.process)
        if result["status"] == "ok":
            for step in result["steps"]:
                print(f"\n--- Step {step['step']}: {step['role']} ---")
                print(step["output"])
            print(f"\n{'=' * 50}")
            print(f'Final result ({len(result["result"])} chars):')
            print(result["result"])
        else:
            print(f"Error: {result}")


def cmd_kb(args):
    if args.action == 'refresh':
        from plugins.server.kb import KnowledgeBase
        from core.config import CFG
        kb = KnowledgeBase(docs_dir=str(CFG.DOCS))
        kb.refresh()
        print(f'KB refreshed: {len(kb.all_chunks)} chunks')
    elif args.action == 'stats':
        from plugins.server.kb import KnowledgeBase
        from core.config import CFG
        kb = KnowledgeBase(docs_dir=str(CFG.DOCS))
        print(json.dumps(kb.stats(), ensure_ascii=False, indent=2))


VERSION = "2.2.0"


def main():
    parser = argparse.ArgumentParser(
        prog='riycol',
        description='Riycol Agent — Multi-agent AI service framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''\
            Examples:
              riycol run all            Start all services
              riycol run server         Start HTTP server only
              riycol run discord        Start Discord bot
              riycol cmd "list all files"  AI->PowerShell (nl2cmd)
              riycol agent run "AI的未来是什么？"
              riycol crew run "写一篇市场调研报告" --roles researcher writer reviewer
              riycol data build --limit 5000
              riycol data export        Export training data
              riycol kb refresh         Refresh knowledge base
        '''))
    parser.add_argument('-v', '--version', action='version',
                        version=f'riycol {VERSION}')
    sub = parser.add_subparsers(dest='command', help='Available commands')

    # ---- run ----
    p_run = sub.add_parser('run', help='Start services')
    p_run.add_argument('service', nargs='?', default='all',
                       choices=['all', 'server', 'telegram', 'agent', 'discord'],
                       help='Service to start (default: all)')
    p_run.set_defaults(func=cmd_run)

    # ---- cmd (nl2cmd) ----
    p_cmd = sub.add_parser('cmd', help='Generate PowerShell commands from natural language via Ollama')
    p_cmd.add_argument('prompt', help='Natural language description of the desired command')
    p_cmd.add_argument('--exec', action='store_true', help='Execute the generated command after confirmation')
    p_cmd.set_defaults(func=cmd_cmd)

    # ---- data ----
    p_data = sub.add_parser('data', help='Data management')
    p_data.add_argument('action', nargs='?', default='stats',
                        choices=['stats', 'build', 'export'],
                        help='Action (default: stats)')
    p_data.add_argument('--limit', type=int, default=10000,
                        help='Max samples for build (default: 10000)')
    p_data.set_defaults(func=cmd_data)

    # ---- plugin ----
    p_plugin = sub.add_parser('plugin', help='Plugin management')
    p_plugin.add_argument('action', nargs='?', default='list',
                          choices=['list'], help='Action (default: list)')
    p_plugin.set_defaults(func=cmd_plugin)

    # ---- db ----
    p_db = sub.add_parser('db', help='Database stats')
    p_db.set_defaults(func=cmd_db)

    # ---- agent ----
    p_agent = sub.add_parser('agent', help='Agent swarm commands')
    p_agent.add_argument('action', nargs='?', default='list',
                         choices=['list', 'run', 'review', 'record'], help='Action (default: list)')
    p_agent.add_argument('task', nargs='?', default='',
                         help='Task for agent (required when action=run/review/record)')
    p_agent.set_defaults(func=cmd_agent)

    # ---- crew ----
    p_crew = sub.add_parser('crew', help='Multi-role crew collaboration (ReAct + task decomposition)')
    p_crew.add_argument('action', nargs='?', default='list',
                        choices=['list', 'run', 'roles'], help='Action (default: list)')
    p_crew.add_argument('task', nargs='?', default='',
                        help='Task for crew (required when action=run)')
    p_crew.add_argument('--roles', nargs='*', default=None,
                        help='Roles to use (e.g. --roles riycol reviewer coder). Default: auto-detect.')
    p_crew.add_argument('--model', default='auto',
                        choices=['auto', 'ollama', 'deepseek', 'local'],
                        help='LLM backend (default: auto)')
    p_crew.add_argument('--process', default='sequential',
                        choices=['sequential'], help='Crew process mode')
    p_crew.set_defaults(func=cmd_crew)

    # ---- kb ----
    p_kb = sub.add_parser('kb', help='Knowledge base commands')
    p_kb.add_argument('action', nargs='?', default='stats',
                      choices=['refresh', 'stats'], help='Action (default: stats)')
    p_kb.set_defaults(func=cmd_kb)

    # ---- validate ----
    p_validate = sub.add_parser('validate', help='Validate configuration')
    p_validate.set_defaults(func=cmd_validate)

    # ---- version ----
    p_version = sub.add_parser('version', help='Show version')
    p_version.set_defaults(func=cmd_version)

    # ---- scheduler ----
    p_sched = sub.add_parser('scheduler', help='Task scheduler status')
    p_sched.set_defaults(func=cmd_scheduler)

    # ---- sync ----
    p_sync = sub.add_parser('sync', help='Sync Notion <-> local knowledge base & session state')
    p_sync.add_argument('target', nargs='?', default='all',
                         choices=['all', 'notion', 'session', 'status'],
                         help='Sync target (default: all)')
    p_sync.add_argument('--direction', default='pull', choices=['pull', 'push', 'bidirectional'],
                         help='Notion sync direction (default: pull)')
    p_sync.add_argument('--task', default='', help='Task to register in session state')
    p_sync.set_defaults(func=cmd_sync)

    # ---- skill ----
    p_skill = sub.add_parser('skill', help='Skill plugin management')
    p_skill.add_argument('action', nargs='?', default='list',
                         choices=['list', 'load', 'discover'], help='Action (default: list)')
    p_skill.add_argument('name', nargs='?', default='', help='Skill name (for load)')
    p_skill.set_defaults(func=cmd_skill)

    # ---- eval ----
    p_eval = sub.add_parser('eval', help='Evaluate agent quality with test suites')
    p_eval.add_argument('suite', nargs='?', default='all',
                         choices=['all', 'basic', 'tool_use', 'reasoning', 'safety', 'code'],
                         help='Test suite (default: all)')
    p_eval.add_argument('--model', default='auto', choices=['auto', 'deepseek', 'ollama', 'mock'],
                         help='Model backend (default: auto)')
    p_eval.set_defaults(func=cmd_eval)

    # ---- memory ----
    p_mem = sub.add_parser('memory', help='Agent memory store stats')
    p_mem.set_defaults(func=cmd_memory)

    # ---- model ----
    p_model = sub.add_parser('model', help='Model management')
    p_model.add_argument('action', nargs='?', default='list',
                         choices=['list', 'download', 'check'], help='Action (default: list)')
    p_model.add_argument('key', nargs='?', default='', help='Model key (for download)')
    p_model.set_defaults(func=cmd_model)

    # ---- finetune ----
    p_ft = sub.add_parser('finetune', help='Fine-tuning pipeline')
    p_ft.add_argument('action', nargs='?', default='stats',
                      choices=['stats', 'prepare', 'clean', 'validate', 'convert', 'config', 'all'],
                      help='Pipeline step (default: stats)')
    p_ft.add_argument('--limit', type=int, default=50000,
                      help='Max samples for prepare (default: 50000)')
    p_ft.set_defaults(func=cmd_finetune)

    # ---- tokens ----
    p_tokens = sub.add_parser('tokens', help='Show token consumption stats')
    p_tokens.add_argument('--watch', action='store_true', help='Continuous refresh (3s interval)')
    p_tokens.add_argument('--limit', type=int, default=20, help='Recent records to show (default: 20)')
    p_tokens.add_argument('--set-baseline', type=float, metavar='COST',
                          help='Set historical baseline cost (e.g. 5.71 for DeepSeek platform)')
    p_tokens.set_defaults(func=cmd_tokens)

    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        return
    args.func(args)


def cmd_version(args):
    print(f"riycol {VERSION}")

def cmd_scheduler(args):
    from core.scheduler import scheduler as sched
    snap = sched.snapshot()
    print(f"Scheduler: {'running' if snap['running'] else 'stopped'} ({snap['task_count']} tasks)")
    for t in snap["tasks"]:
        status = "enabled" if t["enabled"] else "disabled"
        last = time.strftime("%H:%M:%S", time.localtime(t["last_run"])) if t["last_run"] else "never"
        trigger = f"every {t['interval']}s" if t["interval"] else f"daily at {t['cron']}"
        print(f"  {t['name']}: {status} | {trigger} | last={last} | "
              f"runs={t['run_count']} errs={t['error_count']}")

def cmd_tokens(args):
    """Display real-time token consumption statistics."""
    from core.token_tracker import tracker

    if args.set_baseline is not None:
        tracker.set_baseline(args.set_baseline)
        print(f"  ✓ 基线费用已设为 ¥{args.set_baseline:.2f}")
        print("    下次 snapshot 将计入该金额")
        return

    snap = tracker.snapshot(limit=args.limit)
    t = snap["total"]
    print("=" * 56)
    print("  Token 实时消耗统计")
    print("=" * 56)
    print(f"  总调用:      {t['calls']:>8} 次")
    print(f"  Prompt:      {t['prompt_tokens']:>8} tok")
    print(f"  Completion:  {t['completion_tokens']:>8} tok")
    print(f"  总计:        {t['total_tokens']:>8} tok")
    print(f"  估算费用:    ${t['cost']:>8.4f}")
    print("-" * 56)
    if snap["by_source"]:
        print("  按来源:")
        for src, s in sorted(snap["by_source"].items()):
            print(f"    {src:12s}  {s['calls']:>4}次  {s['prompt']:>6} in  {s['completion']:>6} out")
    if snap["recent"]:
        print("-" * 56)
        print(f"  最近 {len(snap['recent'])} 条记录:")
        print(f"  {'时间':>8s}  {'来源':>8s}  {'模型':>8s}  {'Prompt':>7s}  {'Comp':>7s}  {'总计':>7s}")
        for r in snap["recent"]:
            print(f"  {r['time_str']:>8s}  {r['source']:>8s}  {r['model']:>8s}"
                  f"  {r['prompt_tokens']:>7}  {r['completion_tokens']:>7}  {r['total_tokens']:>7}")
    print("=" * 56)
    if args.watch:
        try:
            while True:
                time.sleep(3)
                snap = tracker.snapshot(limit=args.limit)
                # Clear and re-print
                import sys as _sys
                _sys.stdout.write("\033[2J\033[H")  # ANSI clear
                _sys.stdout.flush()
                t = snap["total"]
                print("=" * 56)
                print("  Token 实时消耗统计  (Ctrl+C 退出)")
                print("=" * 56)
                print(f"  总调用:      {t['calls']:>8} 次")
                print(f"  Prompt:      {t['prompt_tokens']:>8} tok")
                print(f"  Completion:  {t['completion_tokens']:>8} tok")
                print(f"  总计:        {t['total_tokens']:>8} tok")
                print(f"  估算费用:    ${t['cost']:>8.4f}")
                print("-" * 56)
                if snap["recent"]:
                    print(f"  最新:")
                    r = snap["recent"][0]
                    print(f"    {r['source']:>8s} / {r['model']:>8s}"
                          f"  in={r['prompt_tokens']}  out={r['completion_tokens']}  total={r['total_tokens']}")
                print("=" * 56)
        except KeyboardInterrupt:
            print("\n  已停止")

def cmd_model(args):
    from core.model_manager import list_models, download_model, check_model
    if args.action == 'list':
        list_models()
    elif args.action == 'check':
        check_model()
    elif args.action == 'download':
        if not args.key:
            print("Usage: riycol model download <key>")
            list_models()
            return
        download_model(args.key)

def cmd_finetune(args):
    from data.training import train
    cmds = {
        'stats': train.cmd_stats,
        'prepare': train.cmd_prepare,
        'clean': train.cmd_clean,
        'validate': train.cmd_validate,
        'convert': train.cmd_convert,
        'config': train.cmd_config,
        'all': train.cmd_all,
    }
    cmds[args.action]()

def cmd_sync(args):
    from core.sync_notion import sync as notion_sync, pull as notion_pull, push as notion_push
    from core.sync_session import get_session_state, snapshot, sync_task, get_active_tasks

    if args.target in ('all', 'notion'):
        if args.direction == 'pull':
            n = notion_pull()
            print(f"Notion pull: {n} pages")
        elif args.direction == 'push':
            n = notion_push()
            print(f"Notion push: {n} pages")
        else:
            r = notion_sync()
            print(f"Notion sync: pulled={r['pulled']}, pushed={r['pushed']}")

    if args.target in ('all', 'session'):
        snap = snapshot()
        print(f"Session sync: last={snap['last_updated']:.0f}, "
              f"tasks={snap['active_tasks']}, keys={snap['keys']}")
        if snap['active_tasks'] > 0:
            for t in get_active_tasks():
                print(f"  [{t['status']}] {t['task'][:80]}")
        if args.task:
            tid = sync_task(args.task)
            print(f"Session sync: registered task {tid}")

    if args.target == 'status':
        print("=== Sync Status ===")
        snap = snapshot()
        state = get_session_state()
        print(f"Session: last_updated={time.strftime('%H:%M:%S', time.localtime(snap['last_updated'])) if snap['last_updated'] else 'never'}")
        print(f"Active tasks: {snap['active_tasks']}")
        for t in get_active_tasks():
            print(f"  [{t['status']}] {t['task'][:80]}")
        if state.get('handoff_note'):
            print(f"Handoff: {state['handoff_note'][:200]}")
        print(f"Total state keys: {len(snap['keys'])}")


def cmd_skill(args):
    from core.skill_loader import skill_loader
    if args.action == 'discover':
        skill_loader._loaded.clear()
        plugins = skill_loader.discover()
        print(f"Discovered {len(plugins)} skill(s)")
        for p in plugins:
            print(f"  {p.name} v{p.version}: {p.description[:80]} ({len(p.tools)} tools)")
    elif args.action == 'load':
        if not args.name:
            print("Usage: riycol skill load <name>")
            return
        plugin = skill_loader.load(args.name)
        if plugin:
            from core.tools import tool_registry
            n = skill_loader.register_tools(plugin.name, tool_registry)
            print(f"Loaded '{plugin.name}': {n} tools registered")
        else:
            print(f"Skill '{args.name}' not found")
    else:
        if not skill_loader._loaded:
            skill_loader.discover()
        skills = skill_loader.list_all()
        print(f"{len(skills)} skill(s) installed")
        for s in skills:
            print(f"  {s['name']} v{s['version']}: {s['description'][:80]} ({s['tools']} tools)")


def cmd_eval(args):
    from core.eval import AgentEval
    ev = AgentEval(model=args.model)
    if args.suite == 'all':
        reports = ev.run_all()
        total_passed = sum(r.passed for r in reports.values())
        total_cases = sum(r.total for r in reports.values())
        print(f"\n{'='*50}")
        print(f"Agent Evaluation: {total_passed}/{total_cases} passed ({total_passed/max(total_cases,1)*100:.0f}%)")
        print(f"{'='*50}")
        for name, r in reports.items():
            rate = f"{r.passed}/{r.total}" if r.total > 0 else "N/A"
            print(f"  [{name:12s}] {rate:>6s} | avg {r.avg_duration_s:.1f}s | {r.avg_rounds:.1f} rounds")
        print(f"{'='*50}")
        # Log result to Notion
        from core.sync_notion import log_eval_result
        log_eval_result("all", total_passed, total_cases,
                        detail=" | ".join(f"{n}:{r.passed}/{r.total}" for n, r in reports.items()))
    else:
        r = ev.run_suite(args.suite)
        print(f"\nSuite '{args.suite}': {r.passed}/{r.total} passed ({r.avg_duration_s:.1f}s avg)")
        for case in r.results:
            status = 'PASS' if case.passed else 'FAIL'
            print(f"  [{status}] {case.case_id}: misses={case.keywords_missed} error={case.error[:60]}")
        # Log result to Notion
        from core.sync_notion import log_eval_result
        log_eval_result(args.suite, r.passed, r.total)


def cmd_memory(args):
    from core.memory_store import memory_store as mem
    stats = mem.stats()
    print(f"Agent Memory: {stats['total_entries']} entries")
    for agent, count in stats["agents"].items():
        keys = mem.list_keys(agent)
        print(f"  {agent}: {count} keys — {', '.join(keys[:5])}{'...' if len(keys) > 5 else ''}")

def cmd_validate(args):
    from core.config import CFG
    from core.db import DB
    from core.token_counter import count_name
    from core.model_router import get_available_models
    print("=== Configuration Validation ===\n")
    warnings = CFG.validate()
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  [!] {w}")
    else:
        print("  [OK] All checks passed.")
    models = get_available_models()
    print(f"\n  ROOT:       {CFG.ROOT}")
    print(f"  PORT:       {CFG.PORT}")
    print(f"  DEBUG:      {CFG.DEBUG}")
    print(f"  USE_KB:     {CFG.USE_KB}")
    print(f"  USE_DB:     {CFG.USE_DB}")
    print(f"  Tokenizer:  {count_name()}")
    print(f"  Local:      {'LOADED' if models.get('local') else 'not loaded'}")
    print(f"  DeepSeek:   {'configured' if CFG.DEEPSEEK_KEY else 'NOT SET'}")
    print(f"  Telegram:   {'configured' if CFG.TELEGRAM_TOKEN else 'NOT SET'}")
    print(f"  Discord:    {'configured' if CFG.DISCORD_BOT_TOKEN else 'NOT SET'}")
    try:
        stats = DB.stats()
        print(f"\n  DB msgs:    {stats['messages']}")
        print(f"  DB sessions:{stats['sessions']}")
        print(f"  DB samples: {stats['samples']}")
    except Exception as e:
        print(f"\n  DB: error ({e})")


if __name__ == '__main__':
    main()
