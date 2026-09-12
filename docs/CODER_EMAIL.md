# Email to send the coder

Copy from the line below. Attach `coder-bundle.zip` (3.9 MB).
Replace the bracketed bits.

---

**Subject:** Small paid/volunteer coding task — ~2–3 hours, needs to be done [Saturday morning]

Hi [Name],

Thank you for agreeing to help. Here is everything, and a realistic picture of
what it involves.

**What it is.** I'm doing a research project on how AI agents behave when
several of them work on the same thing. A group of AI agents were set loose
editing pages on a wiki, and I have a complete record of what they did. I need a
person — not a program — to look at a sample of it and sort each item into a
category. Your labels are the reference standard the rest of the analysis is
checked against, which is why it has to be a human and why it has to be someone
who isn't me.

**What you'd do.** Two rounds, one key press per item.

1. **Edits — 60 items, about 1.5–2.5 hours.** You see a case where one agent
   undid another agent's work, with a diff of what was removed. You decide:
   was this a *disagreement* or just *clearing up a mess*? Or can't you tell?
2. **Messages — 200 items, about 35–70 minutes.** You see a short note an agent
   wrote, usually a few words like `coordination update`. You pick which of
   eight kinds of note it is. These go quickly.

**Total: 2–3.5 hours** with breaks. You can stop and restart any time — it saves
after every single answer and picks up exactly where you left off.

**To start:** unzip the attachment, then

```
uv sync --extra dev
bash coder-kit/check_setup.sh
```

That checks your machine and offers 5 practice items that don't count. **Please
do the practice first and tell me your median time per item** — it prints it. If
Round 1 is running slower than about 2.5 minutes an item, say so and I'll cut it
to 40 items. I would much rather have 40 careful answers than 60 rushed ones.
Then read `coder-kit/README.md`; it's short and it explains everything.

**Four things that genuinely matter, more than speed:**

- **"I can't tell" is a real answer.** Both rounds have an *unclear* option.
  Please use it whenever you're unsure. An honest "don't know" is far more useful
  to me than a guess, and there's no target number of anything.
- **Please don't discuss individual items with anyone while you work** —
  including me. I'm coding 50 of the same items separately, and comparing our
  two sets of answers is part of the measurement. Talking first would spoil it.
- **Please don't go looking for the project's results or write-up.** They say
  what I expect to find, and I'd rather your answers weren't shaped by that. The
  attachment deliberately doesn't contain them, so you'd have to go out of your
  way.
- **About the data:** it has no licence, so please don't share it, don't paste
  any of it into ChatGPT or any other online tool, and delete the folder when
  you're finished. There's a note about this in the zip. Your labels contain no
  page text at all, so those are fine to send back.

**When you're done,** send me:

1. the files in `results/annotations/` (two small JSON files), and
2. `coder-kit/FEEDBACK.md` filled in — it takes 5 minutes and it matters. I
   especially want to know how confident you felt, anything that was ambiguous,
   and any category you wanted that didn't exist. Changing how you judged
   partway through is completely normal; I just need to know if it happened.

If anything breaks, run the same command again — you won't lose finished work.
If you see an error, send me the message and don't edit the saved file by hand.

I'd need this back by [time] on [day] to make my deadline. If that's not
realistic, tell me now and I'll cut the number of items rather than have you
rush — that's a genuine offer, not politeness.

Thank you, really. This is the part of the project I can't do myself.

[Your name]
