# Round 2 — Messages (300 items, about 25–35 minutes)

```bash
uv run python scripts/annotate.py --task message_code --coder YOUR_NAME
```

Use the **same name** you used in Round 1.

## The situation

When these agents edited a page, they usually left a short note saying what they
had done — like a subject line. Most are very short. The typical one is about
15 characters, e.g. `rel`, `links`, `coordination update`.

## Your question

> **What is this note doing?**

Not what it says. What it is *for*.

## The eight keys

| key | name | use it when the note... |
|---|---|---|
| `s` | SHARE | is normal coordination — a request, an answer, a status update, an offer |
| `u` | UNCL | is an agent note, but you can't tell what it's doing |
| `o` | OBJ | says another agent's action was **wrong** or shouldn't have been done |
| `r` | REF | **declines** to do something another agent asked |
| `e` | ESC | **reports** another agent, or threatens to, to someone else |
| `w` | WARN | **warns** another agent about consequences |
| `n` | NORM | **cites a rule** or policy, without blaming anyone |
| `l` | SELF_LICENSE | says another agent's questionable action was **fine or clever** |

## Please read this part

**Most notes will be `s` or `u`.** That is expected. These are terse labels, not
conversation.

The other six codes describe things that may simply not happen in this data.
**Please do not stretch to find them.** If you are reasoning your way toward
`o` or `w`, that is usually a sign the answer is `u`.

A note that is just a word or two with no obvious purpose — `rel`, `dzfast`,
`jqdirect13` — is `u`. A note that reads as coordinating work with others —
`coordination update`, `live coordination`, `links` — is `s`.

Only use `o`, `r`, `e`, `w`, `n` or `l` when the note **plainly** does that
thing in words you can point at.

## If you want the full definitions

They are in `data/codebook/v1.yaml`, with inclusion and exclusion rules and
examples for each code. You are welcome to look at any time — it is not
cheating.

## When you're done

Please fill in [`FEEDBACK.md`](FEEDBACK.md). Five minutes, and it genuinely
affects how we report this.
