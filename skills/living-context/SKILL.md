---
name: living-context
description: Manual controls for this repo's living-context setup (the auto-updating CONTEXT.md that the living-context plugin's commit hook maintains). Use this whenever the user asks about the context doc's status or size, wants to see what the auto-update hook has changed recently, wants to condense/summarize old entries or archive files, or wants to adjust living-context's configuration (doc path, archive threshold, auto-commit). Trigger on phrases like "check the context doc", "is CONTEXT.md getting too big", "condense the old context entries", "what has living-context logged recently", "show me the context doc diff", or "/living-context" followed by status/diff/condense/configure. Also trigger if the user seems confused about entries appearing in CONTEXT.md they didn't write themselves -- that's this plugin's hook, and `status` explains what's going on.
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
call happens -- specifically in `condense` below. Keep that split in mind:
if the user wants something *reworded* or *shortened*, that's this skill,
manually, with review before anything is committed. If they just want to
know what state things are in, that's `status` or `diff` -- no writes at
all.

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

## Configuring

There's no dedicated config script -- `.living-context/config.json` is a
plain JSON file the user (or you, on their behalf) can create or edit
directly at the repo root. It's optional; living-context works with no
config file at all, using the defaults `status` will show. The recognized
keys are `doc_path`, `sub_doc_dir`, `archive_dir`, `threshold_lines`,
`auto_commit`, and `model` -- see the plugin README for what each does. If
the user asks to change one, read the existing file if present (don't
clobber other keys), edit or create it, and mention that new values take
effect on the *next* hook run, not retroactively.
