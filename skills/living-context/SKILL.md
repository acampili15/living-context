---
name: living-context
description: Manual controls for this repo's living-context setup (the auto-updating CONTEXT.md that the living-context plugin's commit hook maintains). Use this whenever the user asks about the context doc's status or size, wants to see what the auto-update hook has changed recently, wants to condense/summarize old entries or archive files, wants a topic-organized reference doc built from the chronological log (not just a changelog), or wants to adjust living-context's configuration (doc path, archive threshold, auto-commit). Trigger on phrases like "check the context doc", "is CONTEXT.md getting too big", "condense the old context entries", "turn the context log into a proper doc", "build/update a project overview from the log", "what has living-context logged recently", "show me the context doc diff", or "/living-context" followed by status/diff/condense/synthesize/configure. Also trigger if the user seems confused about entries appearing in CONTEXT.md they didn't write themselves -- that's this plugin's hook, and `status` explains what's going on.
---

# living-context: manual controls

This skill is the human-facing half of the living-context plugin. The other
half is a commit-triggered background hook (see the plugin's `hooks/`
directory) that automatically appends dated entries to a `CONTEXT.md` doc
(or a sub-doc under `context/`) after commits, and mechanically archives
old entries once a doc grows past a line-count threshold.

The hook is deliberately restricted to two kinds of automatic writes:
appending a new entry, and moving old entries verbatim into an archive
file. It never rewrites or reworks existing text, because that kind of
judgment call needs a human in the loop. This skill is where that judgment
call happens -- in `condense` and `synthesize` below. Keep that split in
mind: if the user wants something *reworded*, *shortened*, or
*reorganized*, that's this skill, manually, with review before anything is
written. If they just want to know what state things are in, that's
`status` or `diff` -- no writes at all.

`condense` and `synthesize` are easy to conflate but do different things.
`condense` shortens the log *as a log* -- fewer, denser dated entries,
still chronological. `synthesize` doesn't shorten anything in place; it
reads the log and produces a separate, topic-organized reference doc (what
this project is, how it works, key decisions and why) -- the kind of thing
someone would want to read first, rather than scrolling a changelog. If
the user's request sounds like "make the log shorter," that's `condense`;
if it sounds like "turn this into a real doc" or "give me an overview,"
that's `synthesize`.

There's no single fixed way this skill gets invoked -- infer which action
the user wants from their request (see the trigger phrases in the
frontmatter above), or ask if it's genuinely ambiguous. If they pass an
explicit subcommand (`/living-context status`, `/living-context condense`,
etc.), use that.

## `status`

Run the bundled script and relay its output, in your own words if that
reads better than a raw dump:

```
python3 <skill_dir>/scripts/status.py
```

(`<skill_dir>` is this skill's own directory -- use the path you loaded
this SKILL.md from.)

This is read-only. It reports: the effective config (defaults or
`.living-context/config.json` overrides), the main doc's size vs.
threshold and the commit SHA its last entry references, the same for any
sub-docs, and a list of archive files with how many entries each holds.

A doc flagged "APPROACHING THRESHOLD" already carries a visible warning
banner (written by the hook itself, at the top of the doc) suggesting
`condense` -- that's the cue this action exists for. If the user asks
about it, offer to run `condense` for them rather than waiting for them to
ask a second time.

If a doc shows "OVER THRESHOLD", that means it's *waiting* on the next hook
run to be archived -- the hook only archives as a side effect of appending
a new entry, so an over-threshold doc with no recent commits will sit that
way until the next one lands. You can tell the user this rather than
treating it as broken.

## `diff`

The context doc(s) are ordinary tracked files, so "what changed" is just
git history on them -- no bundled script needed. Run, adapting the path
from `status`'s config output (default `CONTEXT.md`):

```
git log --oneline -- CONTEXT.md
git diff <ref> -- CONTEXT.md
```

If the user wants to see what a specific commit's hook run added, `git show
<sha> -- CONTEXT.md` is more direct than a range diff. If they didn't name
a range, showing the diff since their last few commits (or since they last
looked, if that's inferable from conversation) is usually what they mean --
ask if it's not clear.

## `condense`

This is the one place where paraphrasing/summarizing is allowed -- and it's
manual for a reason: shortening old entries requires judging which details
still matter, and a naive summarizer can flatten something important. In
particular, watch for entries that *correct* or *supersede* an earlier one
("reversed the approach from the 2026-09-04 entry because...") -- if you
condense the original away without preserving that a correction happened,
a reader loses the fact that the earlier approach was tried and abandoned,
which is often more useful than the detail you're cutting.

Steps:

1. Find out what the user wants condensed -- a specific archive file under
   the archive directory (from `status`'s output), a date range, or "make
   the whole archive shorter." If they haven't said, ask, rather than
   guessing a scope.
2. Read the relevant file(s) in full.
3. Draft a condensed version: fewer, denser entries or paragraphs, written
   in your own words, but keeping every decision, correction, and
   still-relevant rationale that a future reader would need -- err toward
   keeping something rather than cutting it if you're unsure it still
   matters.
4. Show the user your proposed replacement text (not just a description of
   what you'd change) before writing anything. Wait for their go-ahead.
5. Once approved, write it. Do not commit it yourself -- tell the user the
   file has been updated and that they should review with `git diff` and
   commit when they're happy, same as any other change to a doc they
   maintain.

Never run this automatically or as a side effect of another action -- it
only happens when the user has actually asked for something to be
condensed.

## `synthesize`

Turns the chronological log into a separate, topic-organized reference
doc -- written to `synthesized_doc_path` (from `status`'s config output,
default `PROJECT.md`). Think of the shape a good project's own `CLAUDE.md`
or `README.md` takes: what this is, how it's structured, key decisions and
why, organized by subject -- not "on this date we did this." A good model
for the *kind* of document to produce, if the repo has one, is its own
CLAUDE.md-style file: topic sections for durable facts about the project,
distinct from a chronological history.

Steps:

1. Read the main doc (`doc_path`) and every sub-doc under `sub_doc_dir` in
   full. Archived entries (`archive_dir`) are older and lower-signal by
   definition -- skim them for anything that still matters (an important
   reversal, a still-relevant constraint) rather than reading every one in
   full, unless the user specifically asks for full history.
2. **If `synthesized_doc_path` already exists, read it too, and treat it
   as the base to update, not a draft to throw away.** Someone may have
   hand-edited it since the last synthesize run -- added their own
   sections, corrected something, reworded for clarity. Your job on a
   re-run is to fold in what the log has recorded since, and fix anything
   the log shows is now stale, while leaving sections the log hasn't
   touched alone. Don't silently discard human edits just because you're
   regenerating from the log; the log is a source of new information, not
   the sole source of truth for content a person already refined.
3. Organize by topic, not by date -- group related facts and decisions
   together the way you'd explain the project to someone new, rather than
   preserving the log's chronological order. It's fine, and often right,
   to note *why* a decision was made if the log entries carry that
   rationale, but don't invent rationale the log doesn't actually contain.
4. Show the user the proposed doc (or, on a re-run, the diff against the
   existing one) before writing anything. Wait for their go-ahead.
5. Once approved, write it. Do not commit it yourself -- tell the user to
   review with `git diff` and commit when they're happy.

Like `condense`, this only runs when the user has asked for it -- never
automatically, and never as a side effect of `status` or `diff`.

## Configuring

There's no dedicated config script -- `.living-context/config.json` is a
plain JSON file the user (or you, on their behalf) can create or edit
directly at the repo root. It's optional; living-context works with no
config file at all, using the defaults `status` will show. The recognized
keys are `doc_path`, `sub_doc_dir`, `archive_dir`, `threshold_lines`,
`warn_ratio`, `synthesized_doc_path`, `auto_commit`, and `model` -- see the
plugin README for what each does. If
the user asks to change one, read the existing file if present (don't
clobber other keys), edit or create it, and mention that new values take
effect on the *next* hook run, not retroactively.
