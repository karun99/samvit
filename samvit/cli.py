"""Command-line interface — Appendix A command set, plus `samvit gui`."""

from __future__ import annotations

import argparse
import json
import sys

from . import HONESTY, __version__


def _banner() -> str:
    return (
        "\n"
        "   ███████╗ █████╗ ███╗   ███╗██╗   ██╗██╗████████╗\n"
        "   ██╔════╝██╔══██╗████╗ ████║██║   ██║██║╚══██╔══╝\n"
        "   ███████╗███████║██╔████╔██║██║   ██║██║   ██║\n"
        "   ╚════██║██╔══██║██║╚██╔╝██║██║   ██║██║   ██║\n"
        "   ███████║██║  ██║██║ ╚═╝ ██║╚██████╔╝██║   ██║\n"
        "   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚══════╝╚═╝   ╚═╝\n"
        "   संवित् — local-first personal AI · VISION · ULTRON\n"
    )


def _print_result(result: dict, json_out: bool = False) -> None:
    if json_out:
        payload = dict(result)
        if "ultron" in payload:
            payload["ultron"] = payload["ultron"].to_dict()
        if "vision" in payload:
            payload["vision"] = payload["vision"].to_dict()
        print(json.dumps(payload, indent=2, default=str))
        return
    mark = result.get("vision")
    ultron = result.get("ultron")
    prefix = ""
    if mark is not None:
        prefix = mark.banner() + " "
    print(prefix + result["text"])
    if ultron is not None:
        print(f"[ultron: {ultron.status}] {ultron.block_reason or ''}".rstrip())


def _speak(text: str) -> None:
    from .voice import speak

    out = speak(text)
    if not out.get("ok"):
        print(f"[voice] TTS unavailable: {out.get('error')}", file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="samvit",
        description="Samvit — personal AI with VISION (accuracy marker) and ULTRON (validation constraint).",
        epilog=HONESTY,
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--profile", default=None, help="profile override for this call")
    parser.add_argument("--fast", action="store_true", help="run critical ULTRON checks only (FM5)")
    parser.add_argument("--authorized", action="store_true",
                        help="declare authorized defensive-security context (FM1)")
    parser.add_argument("--version", action="version", version=f"samvit {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser("init", help="initialize the brain")
    sub.add_parser("chat", help="interactive session")
    sub.add_parser("ask", help="one-shot query").add_argument("query")
    sub.add_parser("say", help="speak text via OS TTS").add_argument("text")
    sub.add_parser("remember", help="store a claim").add_argument("text")

    mem = sub.add_parser("memory", help="memory graph operations")
    memsub = mem.add_subparsers(dest="memory_op")
    p_list = memsub.add_parser("list", help="recent claims")
    p_list.add_argument("--limit", type=int, default=10)
    memsub.add_parser("stats", help="claim counts")
    memrec = memsub.add_parser("recall", help="search claims")
    memrec.add_argument("query")

    per = sub.add_parser("persona", help="persona operations")
    persub = per.add_subparsers(dest="persona_op")
    persub.add_parser("show", help="current persona state")
    persub.add_parser("anchor", help="reset persona to anchor")
    persub.add_parser("drift", help="drift per axis + compound")
    persub.add_parser("diff", help="what changed since anchor")
    use = persub.add_parser("use", help="switch profile")
    use.add_argument("profile")
    persub.add_parser("list", help="list profiles")
    sig = persub.add_parser("signal", help="record a persona signal")
    sig.add_argument("axis")
    sig.add_argument("value", type=float)
    sig.add_argument("--ungrounded", action="store_true", help="record even if not claim-grounded")

    tools = sub.add_parser("tools", help="tool operations")
    toolsub = tools.add_subparsers(dest="tools_op")
    toolsub.add_parser("list", help="list allowlisted tools with tiers")
    call = toolsub.add_parser("call", help="invoke a tool")
    call.add_argument("name")
    call.add_argument("--args", default="{}")

    sub.add_parser("watch", help="run all watchers (explicit invocation only)")
    sub.add_parser("audit", help="query the audit log").add_argument("--limit", type=int, default=50)

    voice = sub.add_parser("voice", help="voice I/O")
    voicesub = voice.add_subparsers(dest="voice_op")
    voicesub.add_parser("status", help="voice availability")
    voicesub.add_parser("test", help="say a test phrase")

    sub.add_parser("status", help="system status")
    sub.add_parser("gui", help="launch the Tkinter desktop interface")

    cfg = sub.add_parser("config", help="read/write config")
    cfgsub = cfg.add_subparsers(dest="config_op")
    cget = cfgsub.add_parser("get", help="read a config key").add_argument("key")
    cset = cfgsub.add_parser("set", help="write a config key")
    cset.add_argument("key")
    cset.add_argument("value")

    args = parser.parse_args(argv)

    from .brain import Brain
    from .config import Config

    brain = Brain(config=Config())

    if args.command in (None,):
        parser.print_help()
        return 0

    if args.command == "init":
        brain.remember("Samvit brain initialized.", source="system", trust=1.0)
        print(f"Initialized. Brain: {brain.memory.path}")
        print(f"HONESTY: {HONESTY}")
        return 0

    if args.command == "chat":
        return _chat(brain, args)

    if args.command == "ask":
        result = brain.ask(args.query, profile=args.profile, authorized=args.authorized,
                           fast=args.fast)
        _print_result(result, args.json)
        return 0

    if args.command == "say":
        _speak(args.text)
        return 0

    if args.command == "remember":
        out = brain.remember(args.text)
        print(f"stored claim #{out['claim_id']}")
        return 0

    if args.command == "memory":
        return _memory(brain, args)

    if args.command == "persona":
        return _persona(brain, args)

    if args.command == "tools":
        return _tools(brain, args)

    if args.command == "watch":
        from .proactive import run_all

        for out in run_all(brain.memory, brain.persona):
            if args.json:
                print(json.dumps(out))
            else:
                print(f"[watcher] {out.get('ok')} {out.get('result', out.get('error', ''))}")
        return 0

    if args.command == "audit":
        rows = brain.memory.query_audit(limit=args.limit)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['id']:>6}  {r['at']}  {r['action']:<16}  {r['subject']:<12} {r['detail']}")
        return 0

    if args.command == "voice":
        from .voice import speak, voice_status

        if args.voice_op == "status" or args.voice_op is None:
            print(json.dumps(voice_status(), indent=2) if args.json else
                  "\n".join(f"{k}: {v}" for k, v in voice_status().items()))
        elif args.voice_op == "test":
            _speak("Samvit voice test, one two three.")
        return 0

    if args.command == "status":
        out = brain.status()
        if args.json:
            print(json.dumps(out, indent=2, default=str))
        else:
            print(_banner())
            print(f"profile : {out['profile']}   claims: {out['claims']}")
            print(f"drift   : compound={out['persona_drift']['compound']} "
                  f"frozen={out['persona_drift']['frozen']}")
            print(f"providers: {', '.join(p['name'] for p in out['providers'])} "
                  f"({sum(1 for p in out['providers'] if p['available'])} configured)")
            print(f"tools   : {', '.join(t['name'] + '(T' + str(t['tier']) + ')' for t in out['tools'])}")
            print(f"watchers: {', '.join(w['name'] + '(T' + str(w['tier']) + ')' for w in out['watchers'])}")
            print(f"voice   : tts={out['voice']['tts']} asr={out['voice']['asr_engine'] or 'none'}"
                  " wake_word=off always_on=off")
            print(f"\n{HONESTY}")
        return 0

    if args.command == "gui":
        from .gui import launch

        return launch(brain)

    if args.command == "config":
        if args.config_op == "get":
            print(brain.config.get(args.key))
        elif args.config_op == "set":
            val = args.value
            if val.lower() in ("true", "false"):
                val = val.lower() == "true"
            elif val.isdigit():
                val = int(val)
            brain.config.set(args.key, val)
            print(f"{args.key} = {val}")
        return 0

    parser.print_help()
    return 0


def _chat(brain, args) -> int:
    banner = (
        _banner()
        + f"\nProfile: {brain.active_profile()} · type 'exit' or Ctrl-D to leave\n"
        + f"{HONESTY}\n"
    )
    print(banner)
    while True:
        try:
            line = input(f"{brain.active_profile().upper()}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return 0
        if not line:
            continue
        if line.lower() in ("exit", "quit", "bye"):
            print("bye.")
            return 0
        if line.lower() == "status":
            print(json.dumps(brain.status(), indent=2, default=str) if args.json else "")
            continue
        result = brain.ask(line, profile=args.profile, authorized=args.authorized,
                           fast=args.fast)
        _print_result(result, args.json)


def _memory(brain, args) -> int:
    if args.memory_op == "list":
        for c in brain.memory.recent(limit=args.limit):
            print(f"#{c['claim_id']:>5} [{c['kind']}] trust={c['trust']:.2f} "
                  f"{c['ts']}  {c['text'][:80]}")
    elif args.memory_op == "stats":
        print(json.dumps({"claims": brain.memory.count_claims()},
                         indent=2 if args.json else None))
    elif args.memory_op == "recall":
        for c in brain.recall(args.query):
            print(f"#{c['claim_id']:>5} trust={c['trust']:.2f}  {c['text'][:80]}")
    else:
        print("usage: samvit memory {list|stats|recall <query>}")
        return 2
    return 0


def _persona(brain, args) -> int:
    if args.persona_op == "show":
        show = brain.persona_show()
        if args.json:
            print(json.dumps(show, indent=2))
        else:
            print("current:", show["current"])
            print("anchor :", show["anchor"])
            print("drift  :", show["drift"])
            for s in show["signals"][:5]:
                print(f"  signal [{s['profile']}] {s['axis']}={s['value']} @ {s['ts']}")
    elif args.persona_op == "drift":
        print(json.dumps(brain.persona_drift(), indent=2) if args.json else
              brain.persona_drift())
    elif args.persona_op == "diff":
        show = brain.persona_show()
        for axis, val in show["current"].items():
            delta = round(val - show["anchor"][axis], 4)
            print(f"{axis:<10} current={val:.3f} anchor={show['anchor'][axis]:.3f}"
                  f" delta={'+' if delta >= 0 else ''}{delta:.4f}")
    elif args.persona_op == "anchor":
        print(brain.persona_anchor())
    elif args.persona_op == "use":
        out = brain.profile_use(args.profile)
        print(out if args.json else
              (f"profile switched to {out['profile']}" if out["ok"] else out["error"]))
    elif args.persona_op == "list":
        for p in brain.profile_list():
            print(f"{p['name']:<10} {p['kind']:<10} {p['help']}")
    elif args.persona_op == "signal":
        grounded = not args.ungrounded
        d = brain.persona_signal(args.axis, args.value, grounded=grounded)
        print(json.dumps(d, indent=2) if args.json else d)
    else:
        print("usage: samvit persona {show|anchor|drift|diff|use <p>|list|signal <axis> <value>}")
        return 2
    return 0


def _tools(brain, args) -> int:
    if args.tools_op == "list":
        for t in brain.tools.list():
            print(f"{t['name']:<16} tier={t['tier']}  {t['help']}")
    elif args.tools_op == "call":
        from .tools import TierGate

        def decide(tier: int, name: str, tool_args: dict) -> bool:
            if tier >= 3:
                print(f"\n[tool consent] {name} requires Tier {tier} approval.")
                print(f"args: {tool_args}")
                if tier == 4:
                    first = input("Stage 1/2 — proceed? [y/N] ").strip().lower() in ("y", "yes")
                    if not first:
                        return False
                    print("Stage 2/2 — final confirmation.")
                return input("Approve? [y/N] ").strip().lower() in ("y", "yes")
            return True

        def notify(tier: int, name: str, tool_args: dict) -> None:
            print(f"[tool] tier {tier} '{name}' auto-executed (FR-7.3/7.4)")

        brain.set_tier_gate(TierGate(decide=decide, notify=notify))
        out = brain.tool_call(args.name, args.args)
        print(json.dumps(out, indent=2, default=str) if args.json else out)
    else:
        print("usage: samvit tools {list|call <name> --args '{...}'}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())