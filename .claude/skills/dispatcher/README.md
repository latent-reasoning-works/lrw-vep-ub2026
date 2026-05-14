# dispatcher (workshop mirror)

This is a self-contained mirror of the `dispatcher` skill for the
Upper Bound 2026 workshop. The canonical upstream lives at
`latent-reasoning-works/shop` (private as of 2026-05-13); this snapshot
is the workshop-load-bearing subset.

**What's here**
- `SKILL.md` — the keystone (substrate router; emit-only contract)
- `references/workload_spec.md` — input contract for `route.py`
- `references/backend_schema.md` — manifest schema for remote SLURM backends
- `references/backends/_template.json` — starter manifest
- `scripts/route.py` — the router (workload → plan)
- `scripts/check_local.sh` — local CPU/GPU/MPS detection
- `scripts/check_slurm.sh` — SLURM backend reachability probe
- `scripts/detect_substrates.sh` — orchestrator (called by `route.py`)

**What's deliberately not here** (lives upstream in the full skill):
`ssh_template.md` (generic SSH ControlMaster docs), `known_backends.md`
(maintainer's cluster pointers), `backends/example_*.json` (extra
anonymized examples — the `_template.json` carries the shape).

**Use**

For Claude Code project-local discovery (if your client scans
`.claude/skills/` in the project root): nothing to do — the skill is
already at the right path.

For Claude Code user-global discovery (so the Skill tool sees it in
*any* session, not just sessions opened in this repo):
```bash
mkdir -p ~/.claude/skills
cp -r .claude/skills/dispatcher ~/.claude/skills/
```

For Bash-direct invocation (works in any environment):
```bash
echo '<workload>' | python3 .claude/skills/dispatcher/scripts/route.py
```

See the project root's `CLAUDE.md` Phase 2 section for how the
dispatcher fits the workshop's scaling story.
