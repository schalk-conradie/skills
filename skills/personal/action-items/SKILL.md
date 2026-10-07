---
name: action-items
description: Turns the current chat into a short, grouped list of what the user still needs to do, decide, answer, or send. Use this whenever the user types /action-items, or asks things like "what do I need to do?", "what's left?", "what are my next steps?", "give me the to-dos from this", "tl;dr what do I action", or says they're lost in a long reply and want to know what needs their attention. Use it even if they don't say "action items" explicitly but clearly want the outstanding to-dos pulled out of the conversation.
---

# Action Items

The user is busy and often ends up with long replies where the things they actually need to act on are buried in explanation. This skill pulls those out into a short list they can scan in a few seconds. The value is in the filtering: anything that isn't something the user still has to act on stays out.

## What to scan

Read the whole conversation, not just the last reply. Earlier messages often contain open questions or tasks that were never resolved. But skip anything that's already been dealt with:

- The user said they did it, answered it, decided it, or sent it.
- A later message superseded it (e.g. plan changed, option dropped).
- Claude already did it for them (a file was produced, a draft was written). The user may still need to *use* that output, which can be its own item, e.g. "Send the drafted email to Thabo".

When in doubt about whether something is still open, include it but keep it short; a stale item costs the user a second, a missed one costs more.

## What counts as an action item

Four kinds, and these become the groups:

- **Do** — tasks the user has to carry out themselves (install something, update a setting, book a meeting, test a change).
- **Decide** — choices that were left open, where Claude presented options or the user said they'd think about it.
- **Answer** — questions Claude asked the user that haven't been answered yet, or information Claude said it needs to continue.
- **Send / share** — things to pass on to someone else (an email to send, a file to share, a person to loop in).

Leave out: background explanation, general tips, "you could also consider…" suggestions the user showed no interest in, and anything Claude is responsible for doing next. If Claude itself promised to do something, that isn't the user's to-do.

## Output format

Use this structure, omitting any group that's empty:

```
**Do**
- [ ] Item
- [ ] Item

**Decide**
- [ ] Item — options: A or B

**Answer**
- [ ] Item

**Send / share**
- [ ] Item → recipient
```

Guidelines for each item:

- One line, starting with a verb. Aim for under ~15 words.
- Be specific: name the file, person, setting, or number involved, so the item makes sense without re-reading the chat.
- For decisions, list the options briefly after a dash.
- Within each group, put the most important or time-sensitive item first. If something blocks other items, put it first and say so briefly ("first — blocks the rest").
- Include a deadline only if one was actually mentioned.

Don't add an intro, a summary paragraph, or a closing offer. The whole point is brevity. At most, one short line at the end if something genuinely needs flagging (e.g. "Answering the budget question will unblock the remaining steps.").

If nothing is outstanding, say so in one sentence, e.g. "Nothing outstanding — you're all caught up."

## Example

A chat where Claude explained how to set up a Power BI gateway, asked which region the server is in, offered on-prem vs cloud gateway, and the user later said they'd already installed the gateway software.

```
**Do**
- [ ] Register the gateway in the Power BI service under the admin account
- [ ] Add the SQL Server data source with the service account credentials

**Decide**
- [ ] Pick gateway type — on-premises standard or personal mode

**Answer**
- [ ] Tell Claude which Azure region the server is in

**Send / share**
- [ ] Ask IT to open port 443 outbound on the server → IT team
```

Note that "Install the gateway software" is missing because the user already did it.
