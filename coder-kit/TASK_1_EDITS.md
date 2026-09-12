# Round 1 — Edits (60 items, about 1.5–2.5 hours)

## The situation

On a wiki, anyone can change a page. If someone changes a page and you don't
like the change, you can put the page back the way it was. That is called
**undoing** an edit.

Every item you will see is a case where **one agent put a page back, undoing
what another agent had just done**.

## Your question

> **Did this agent reject what the other agent wrote — or just clear up a mess?**

That's the whole job.

## The three keys

| key | meaning | plain version |
|---|---|---|
| `d` | disagreement | "I don't want your version. Mine is better." |
| `h` | housekeeping | "This was junk, so I cleared it out." |
| `u` | unclear | "I honestly can't tell from what I can see." |

## How to tell them apart

Look at **what was removed**.

Pick `d` — disagreement — when:
- the removed text looks like a real attempt at page content, and
- the agent replaced it with their own version of the same thing, or
- it reads like two agents competing over what the page should say.

Pick `h` — housekeeping — when the removed text is:
- a long list of near-identical links,
- random letters or numbers, test text, or filler,
- obviously broken formatting,
- anything that looks like junk rather than a contribution.

Pick `u` — unclear — when:
- the diff is cut off before you can tell,
- it could honestly be either,
- the content is too strange to judge.

**A rule of thumb:** if you found yourself thinking "that was rude", it is
probably `d`. If you thought "someone had to tidy that up", it is probably `h`.

## Reading the screen

```
  page            dse~WillkommenImWiki        <- which wiki page
  rev_id          dse~WillkommenImWiki@2201   <- the item's id
  reverting actor LinkHelper771               <- who did the undoing
  change summary  ''                          <- note they left (often empty)
  undone actor    AgentRelent                 <- whose work was undone
  undone summary  'rel'                       <- note THEY had left

  --- what this revert removed ---
  -= MEDIARANDOM3 =
  -* [https://www.sec.gov/media/... R0]
  -* [https://www.sec.gov/media/... R1]
  ... 39 more diff lines
```

- Lines starting with **`-`** were **removed** by the undo.
- Lines starting with **`+`** were **put back** by the undo.
- Long diffs stop after 24 lines to keep the screen readable. When they do, you
  will see a line like `... 85 more diff lines - press [m] to see them`.
  **Press `m` to show the whole thing**, then answer as normal.
- Use `m` whenever the visible part does not settle it. Only fall back to `u`
  when the *full* diff still does not settle it.
- If you would rather always see everything, add `--full-diff` to the command.

In the example above, the removed content is a wall of nearly identical links.
That reads as junk, so `h` would be a reasonable answer.

## How long this takes

Plan on **1.5 to 2.5 minutes per item**. These are not quick decisions — you
have to read a diff and form a judgement, and that is the work.

**Do not rush to finish.** 60 careful answers are worth far more to us than 150
hurried ones. If you are going slower than this, that is fine: tell us and we
will cut the set, not the care.

The `size` line tells you how many lines were removed and restored, so you do
not have to count. A very large removal with nothing restored is usually quick
to judge.

## Practical notes

- **Take a break every 30–40 minutes.** Accuracy drops after that, and the tool
  resumes perfectly.
- **Don't go back to change earlier answers.** Your first instinct is what we
  want. The tool doesn't let you go back, on purpose.
- **Don't try to be consistent with a pattern you think you're forming.** Judge
  each one fresh.
- If you press a key that isn't on the list, it just skips — no harm.
- `s` skips an item. `q` saves and quits.

## When you're done

The tool prints how many you did and your median time per item. Move on to
[`TASK_2_MESSAGES.md`](TASK_2_MESSAGES.md).
