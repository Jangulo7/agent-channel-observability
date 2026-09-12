# Start here

Hello, and thank you for helping.

## What this is, in plain words

Some AI agents were given jobs that involved editing pages on a wiki — a website
anyone can edit, like Wikipedia. They edited pages, and they left short notes
about what they changed.

We saved everything they did. Now we need a person to look at some of it and
sort it into categories. That person is you.

**You do not need to know anything about AI, wikis, or the research.** You just
need to read what is on the screen and pick the option that fits best.

## What you will do

Two rounds of sorting.

**Round 1 — Edits.** You will see 60 cases where one agent undid another
agent's work. For each one you decide: *was this a disagreement, or was it just
cleaning up a mess?* You press one key. **About 1.5–2.5 hours** — these need
real reading, so they are not quick.

**Round 2 — Messages.** You will see 200 short notes the agents wrote, usually
just a few words like `coordination update` or `links`. For each one you pick
which kind of note it is. **About 35–70 minutes** — these genuinely are quick.

**Total: 2–3.5 hours**, with breaks. You can stop and restart whenever you like.
Nothing is ever lost.

**Before you commit to the full run**, do the 5-item practice in the setup check.
It prints how long you took per item. If Round 1 is running slower than about
2 minutes an item, tell us.

## How to start

1. Open a terminal in the project folder.
2. Run this once to check everything works:

   ```bash
   bash coder-kit/check_setup.sh
   ```

   It will tell you if anything is missing, and let you try 5 practice items
   that do not count.

3. Read [`TASK_1_EDITS.md`](TASK_1_EDITS.md). It is short.
4. Start Round 1:

   ```bash
   uv run python scripts/annotate.py --task revert_validity --coder YOUR_NAME --n 60
   ```

   Put your own short name in place of `YOUR_NAME` — `anna`, or `coder_a`, or
   your initials. No spaces. **Use the same name in both rounds.**

5. When Round 1 is done, read [`TASK_2_MESSAGES.md`](TASK_2_MESSAGES.md) and
   start Round 2:

   ```bash
   uv run python scripts/annotate.py --task message_code --coder YOUR_NAME --n 200
   ```

6. Fill in [`FEEDBACK.md`](FEEDBACK.md). It takes 5 minutes and it matters.

Keep [`DECISION_CARD.md`](DECISION_CARD.md) open beside you while you work. It
is a one-page reminder of the choices.

## Four things that matter

1. **"I can't tell" is a real answer.** Every round has an *unclear* option.
   Please use it whenever you are not sure. We would much rather have an honest
   "don't know" than a guess. There is no prize for using it less.

2. **There is no right proportion.** Do not worry if you are picking the same
   option many times in a row. That happens, and it is fine.

3. **Please don't discuss items with anyone while you work.** Someone else may
   be sorting the same items separately. Comparing your two sets of answers is
   part of the measurement, so talking first would spoil it.

4. **Please don't read the project's README or results first.** They say what we
   expect to find, and we would rather your answers were not shaped by that. If
   you have already read them, no problem — just say so in the feedback form.

## Your answers are private

The saved file contains only: which item, which key you pressed, how many
seconds you took, and the date. **None of the page text or message text is
saved**, and nothing identifies you beyond the short name you choose.

## If something goes wrong

Run the same command again. You will not lose finished work.
If you see an error, copy it and send it on. Please do not edit the saved file
by hand.
