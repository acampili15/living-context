# living-context

A Claude Code plugin that keeps a living `CONTEXT.md` for a repo up to
date automatically, without turning "context doc maintenance" into a
chore someone has to remember to do.

- A **commit-triggered background hook** reads each commit's message and
  diff and, when there's something worth recording, appends a dated entry
  to `CONTEXT.md` (or a sub-doc under `context/` for changes concentrated
  in one feature area) — grounded only in that commit's actual content,
  never invented.
- When a doc grows past a size threshold, the hook **mechanically
  archives** its oldest entries — verbatim, no rewriting — into
  `context/archive/<YYYY-MM>.md`. Before that happens, once the doc
  crosses a lower `warn_ratio` of that threshold, it gets a visible
  **warning banner** suggesting you run `condense` yourself instead.
- The first time it runs in a repo, the hook writes a short **onboarding
  paragraph** into the newly-created doc explaining what living-context
  is and how it works — so opening `CONTEXT.md` for the first time
  answers "wait, what wrote this?" on the spot.
- A companion **skill** gives you manual controls: `status` (doc sizes,
  what the hook has been doing), `diff` (what's changed in the doc
  itself, via ordinary git history), `condense` (shorten the log itself —
  fewer, denser dated entries, still chronological), and `synthesize`
  (turn the log into a separate, topic-organized reference doc, e.g.
  `PROJECT.md` — what this project is and how it works, not a changelog).
  Both `condense` and `synthesize` always draft their result for your
  review first and never auto-commit.

## Why archiving is automatic but condensing isn't

This is the central design decision in this plugin, and it's worth
understanding before you rely on it.

The hook is allowed to do exactly two things to your context doc, fully
unattended: **append** a new entry, and **move** old entries into an
archive file byte-for-byte. Neither of those requires judgment about what
still matters — appending is additive (nothing existing changes), and
archiving is a pure cut-and-paste keyed off a line-count threshold.

Summarizing old entries into something shorter is a genuinely different
kind of operation: it requires deciding which details are still load-
bearing. A context log often contains corrections — an entry that reverses
or supersedes an earlier decision — and a naive automatic summarizer can
easily flatten "we tried X, then reversed it because Y" down to just "we
did Y," silently erasing the fact that X was tried and why it didn't work.
That's exactly the kind of thing a context doc exists to preserve. So
condensing is a manual, skill-driven action: you tell it what to condense,
it drafts a rewrite, you review the actual proposed text, and only then
does it get written — and even then, the plugin doesn't commit it for you.

If you take nothing else from this README: the hook never rewords
anything you or a previous hook run already wrote. It only ever adds or
relocates text unchanged.

## The log vs. the doc: `condense` vs. `synthesize`

`CONTEXT.md` is a *log*: dated entries, in order, one per commit judged
worth recording. That's a great format for "what happened and when," and a
bad format for "what is this project and how does it work" — answering the
second question from a long changelog means scrolling and mentally
reassembling scattered facts. `condense` and `synthesize` both shorten
your reading burden, but in different ways:

- `condense` keeps the log's shape. It makes old entries denser — fewer
  words, same chronological structure — and writes the result back into
  the log itself (or an archive file).
- `synthesize` throws the chronological shape away on purpose. It reads
  the whole log and produces a separate, topic-organized reference doc
  (default `PROJECT.md`) — the kind of document a project's own
  `CLAUDE.md` or `README.md` usually is: what this is, how it's
  structured, key decisions and why, grouped by subject. It's built *from*
  the log, but it isn't the log, and it isn't touched by the hook.

Keeping `synthesize`'s output in a separate file (not a restructured
`CONTEXT.md`) is deliberate: the log's core guarantee is that nothing in
it is ever rewritten by automation, and a topic-organized doc necessarily
needs its sections *updated* over time as the project changes underneath
them — that's editing, not appending. Splitting them into two files means
the log's append-only guarantee never needs an exception, and the
synthesized doc can always be regenerated (or updated) from the log if it
ever gets out of sync — see `synthesize` in the skill for how re-runs
handle a doc you've since hand-edited.

## Why the warning is a banner in the doc, not a message from Claude

It would be nicer if, right after a commit, Claude just told you in that
same session "hey, CONTEXT.md is getting long, want me to condense it?"
instead of you having to notice a banner in a file. That was tried and
deliberately not shipped.

Claude Code hooks can attach a `systemMessage`/`additionalContext` to what
Claude sees next. In testing: phrased as neutral information ("CONTEXT.md
is at 39/40 lines"), it was silently absorbed and never mentioned — not a
reliable nudge. Phrased as an instruction ("tell the user to run
condense"), Claude *did* notice it, but correctly flagged it as a likely
prompt injection and declined to act on it, rather than relaying it. That
second behavior is Claude Code working as intended — a background hook
script shouldn't be able to freely put words in Claude's mouth, and trying
to phrase around that would mean working against a real security boundary,
not a bug to route around. So there's no reliable "Claude proactively
mentions this" channel available here, and this plugin doesn't try to
manufacture one. The banner living-context writes directly into the doc is
guaranteed-visible instead: you'll see it the moment you open the file,
with no dependency on how any particular session happens to react to hook
output.

## Requirements

- The `claude` CLI on `PATH` (the hook shells out to `claude -p` in the
  background — this is what actually reads the diff and drafts entries).
- `python3` on `PATH` (used for the hook's JSON/git parsing and the
  mechanical archiving logic — chosen over hand-rolled shell JSON parsing
  for reliability, not because it's a "heavy" dependency; it's already on
  effectively every machine that has `git` and `claude` installed).
- No other runtime or package-manager dependency. Nothing gets installed
  into the repos this plugin runs in.

## Installing

### Try it locally first (recommended before installing for real)

From anywhere, point Claude Code at this plugin's directory directly —
this doesn't touch your global plugin registry, so it's safe to try and
walk back:

```bash
claude --plugin-dir /path/to/living-context
```

Then, inside a scratch git repo, make a commit and watch what happens (see
"Verifying it's working" below).

### Install for real, across all your repos

Installing "for the user" (so the hook applies automatically in every repo
you work in, including ones you haven't created yet) means registering
this plugin in your user-level Claude Code config rather than a specific
project's. The exact install command depends on your Claude Code version —
use `/plugin install <path-or-name>` from within a Claude Code session, or
add an entry for this plugin under the plugins section of `~/.claude/settings.json`
if you're installing from a local path rather than a marketplace. Either
way, this plugin isn't published to a marketplace (yet) — install it from
this local directory (or from wherever you've pushed it, once you have a
git remote for it).

Once installed at the user level, no per-repo setup is required — the hook
is active in any repo you commit in, immediately, with zero config.

## Configuring a repo (optional)

Every repo works with living-context out of the box, using these
defaults:

| key | default | meaning |
|---|---|---|
| `doc_path` | `CONTEXT.md` | Main context doc, relative to repo root. |
| `sub_doc_dir` | `context` | Where sub-feature docs live/get created. |
| `archive_dir` | `context/archive` | Where mechanically-archived entries land, one file per `YYYY-MM`. |
| `threshold_lines` | `400` | Line count that triggers archiving an over-long doc after an append. |
| `warn_ratio` | `0.85` | Fraction of `threshold_lines` at which the doc gets a visible warning banner suggesting `condense`, before the hard archiving threshold hits. |
| `synthesized_doc_path` | `PROJECT.md` | Where the skill's `synthesize` action writes its topic-organized reference doc, built from the log. Never touched by the hook. |
| `auto_commit` | `false` | If true, the hook commits its own doc/archive changes as a separate commit. **Off by default** — an automation that commits on your behalf should be something you opt into per repo, not a default that could surprise you. |
| `model` | `null` | Model for the headless `claude -p` call; `null` uses the CLI's own default. |

To override any of these, create `.living-context/config.json` at the
repo's root with just the keys you want to change:

```json
{
  "threshold_lines": 250,
  "auto_commit": true
}
```

The `living-context` skill's `status` action shows the effective config
(defaults merged with your overrides) for the repo you're in.

## Verifying it's working

1. `claude --plugin-dir /path/to/living-context` in a scratch git repo
   with a couple of real files in it.
2. Make a substantive commit (not just `git init`) — something with an
   actual behavior change, so the hook has something worth logging.
3. The `git commit` command returns immediately — the hook does not block
   it. Give it a few seconds to a minute or two in the background
   (it's making a real `claude -p` call).
4. Check `CONTEXT.md` — a new dated entry should appear, referencing your
   commit's short SHA. If this was the repo's first commit through
   living-context, you should also see the onboarding paragraph above it.
5. To see the warning banner without waiting for a real 400-line doc, set
   a low `threshold_lines`/`warn_ratio` in `.living-context/config.json`
   (e.g. `{"threshold_lines": 10, "warn_ratio": 0.5}`) before committing.
6. If nothing appears, check the hook's log: `$CLAUDE_PLUGIN_DATA/context-update.log`,
   or `~/.living-context/logs/context-update.log` if `CLAUDE_PLUGIN_DATA`
   isn't set in your environment. It records why a run was skipped (commit
   judged not worth logging, `claude` not found, a timeout, etc.) —
   nothing here should be silent-and-mysterious.

## How the pieces fit together

```
living-context/
├── .claude-plugin/plugin.json     — plugin manifest
├── hooks/
│   ├── hooks.json                 — registers the PostToolUse hook
│   ├── context-update.py          — fast filter: is this a successful `git commit`?
│   │                                 backgrounds run_context_update.py and returns instantly.
│   └── run_context_update.py      — the actual worker: gathers the commit's diff,
│                                     calls `claude -p` to draft/append an entry,
│                                     then runs the mechanical archive check.
├── lib/
│   ├── config.py                  — shared defaults + .living-context/config.json loading
│   ├── doc_format.py              — shared entry-parsing + sentinel-block helpers
│   ├── archive.py                 — the mechanical, LLM-free archiving logic
│   ├── warn.py                    — the mechanical, LLM-free size-warning banner
│   └── prompts/system_prompt.md   — the rules given to the headless append step
└── skills/living-context/
    ├── SKILL.md                   — manual status/diff/condense/configure controls
    └── scripts/status.py          — read-only status report
```

The hook fires on every `Bash` tool call (`PostToolUse` can't filter by
command content at the matcher level), but exits in milliseconds for
anything that isn't a successful `git commit` — the filtering happens
inside `context-update.py`, not by making Claude Code itself do less
matching.

## Known limitations (v1)

- The headless `claude -p` call is scoped to `Read`/`Write`/`Edit`/`Glob`
  tools only (no `Bash`, no network), and its system prompt explicitly
  restricts it to the context doc(s) — but tool-type allowlisting isn't
  the same as filesystem sandboxing. This is trusted automation over your
  own commits, not a hardened sandbox around untrusted input.
- Only the main doc and existing sub-docs are checked for the archive
  threshold on each run — a sub-doc that's created and never touched
  again won't get re-checked until something else triggers a run in that
  repo.
- No marketplace listing yet; install from a local path as described
  above.
