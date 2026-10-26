---
name: issue-create
description: Interview a developer about a bug, feature, refactor or task, check the idea against the repository's own documentation, and write a ready-to-paste GitHub issue (Title, Summary, Problem, Proposal, Open Design Questions, Acceptance Criteria) in ASD-STE100 Simplified Technical English, inside a markdown block in chat. Use this skill whenever the user wants to write, draft, open, file, prepare or "turn this into" a GitHub issue, ticket or feature request for a repo, or describes a bug or idea and asks for an issue text — even if they only say "make an issue for this" or paste a rough note. Do not use it to triage, label, close or search existing issues, or to write pull request descriptions or commit messages.
---

# GitHub Issue Writer

Turn a developer's rough idea into a clear GitHub issue. The developer knows
the problem. The repository documentation knows the rules of the project. A
good issue joins the two, so the reader does not have to ask the same
questions again in the comments.

The work has four phases:

1. Capture the idea.
2. Read the repository documentation.
3. Ask clarifying questions until each issue section has real content.
4. Write the issue in a markdown block, in STE.

Do not skip phase 2 or 3 to reach the output faster. An issue that ignores
the project docs or guesses at the scope creates more work for the team.

---

## Phase 1 — Capture the idea

Read what the developer wrote and sort it into the six issue sections in
your head:

- What is the issue? (Title, Summary)
- What is wrong or missing today, and who feels it? (Problem)
- What change do they want? (Proposal)
- What is not decided yet? (Open Design Questions)
- How will the team know it is done? (Acceptance Criteria)

Note which sections are empty or vague. These gaps drive phase 3. Also note
the issue type, because it changes what the Problem section needs:

- **Bug** — needs current behavior, expected behavior, steps to reproduce,
  version or environment.
- **Feature or enhancement** — needs the user need, the use case, and the
  limits of the current behavior.
- **Refactor, tech debt or chore** — needs the cost of the current state
  (slow builds, duplicate code, risk) and what must not change.
- **Documentation** — needs the page, the missing or wrong content, and the
  audience.

## Phase 2 — Read the repository documentation

Find the repository first. Use what is available, in this order:

1. A repository in the working directory or a connected folder.
2. Files the developer attached.
3. A GitHub repository the developer named. Clone it or read it with the
   tools in the session.
4. Documentation text the developer pasted.

If you find no repository, ask for one in your first round of questions. If
the developer cannot give access, continue. Mark in the issue which facts
come only from the developer.

Read the files that tell you how the project thinks. Start with the ones
that exist:

- `README.md`
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
- `docs/`, `doc/`, `documentation/`, wiki exports
- Architecture and design records: `ARCHITECTURE.md`, `docs/adr/`,
  `docs/decisions/`, `rfcs/`, `design/`
- `.github/ISSUE_TEMPLATE/` and `.github/` guidance
- `CHANGELOG.md` and `ROADMAP.md`
- The docs and the code for the module the issue touches. Use search to find
  the names the developer used.

Do not read the whole repository. Read until you can answer these questions:

- Does the docs already describe this behavior, or a rule that limits it?
- Does an existing design decision support or block the proposal?
- What names does the project use for the parts involved? Use those names in
  the issue, not the developer's informal names.
- Does the repository have an issue template or a label convention? If yes,
  keep the six required sections and add the template's extra fields after
  them.

Keep a short list of what you found, with file paths. You will cite these
paths in the issue so the reader can check them.

When the developer's idea conflicts with the docs, do not choose a side in
silence. Show the conflict to the developer as a question in phase 3.

## Phase 3 — Ask clarifying questions

Ask questions in rounds. Each round has three to five questions, ordered by
importance. A long list in one message makes the developer skip questions.

Make each question specific and grounded:

- Refer to what you found. Write "`docs/auth.md` says tokens expire after 24
  hours. Must the new refresh flow keep that limit?" Do not write "Are there
  any constraints?"
- Give options when you can see them, so the developer can answer fast:
  "(a) per user, (b) per API key, (c) both".
- Do not ask what the docs or code already answer. State the answer and ask
  the developer to confirm only if it matters.

Cover these areas, but only where a gap exists:

- **Scope**: what is in, what is out, what must not change.
- **Impact**: who is affected, how often, how bad. Ask for logs, error
  messages, links or numbers.
- **Reproduction** (bugs): steps, expected result, actual result, version.
- **Constraints**: compatibility, performance, security, migration, API
  stability.
- **Done**: what a reviewer can observe or test to accept the work.
- **Conflicts**: each place the idea disagrees with the docs.

Stop when each section has real content. Two or three rounds are usually
enough. Some questions will stay open. Questions that the team must decide,
not the developer, go into the Open Design Questions section. They do not
block the draft.

If the developer says "just write it" or does not want more questions,
write the issue now. Put every assumption you made into Open Design
Questions, so the team can see and correct it.

Before you write, give a short summary of what you understood, in two to
four lines, in the same message as the issue. Do not wait for a separate
confirmation unless a large conflict is open.

## Phase 4 — Write the issue

Put the full issue in one fenced markdown block in the chat, so the
developer can copy it in one action. Use a four-backtick fence
(` ````markdown `), because the issue can hold code blocks with three
backticks.

Do not create the issue on GitHub. The output is text in the chat. Create
an issue with `gh issue create` or a connector only if the developer
explicitly asks for it, and confirm the repository and the text with them
first.

Use this exact structure and these exact headings, in this order:

````markdown
# <Title>

## Summary

## Problem

## Proposal

## Open Design Questions

## Acceptance Criteria
````

### Section rules

**Title** — Replace `<Title>` with the issue title. Keep it under about 70
characters. Make it specific and searchable. Start with a verb for a change
("Add retry limit to webhook delivery"). Use a short statement of the fault
for a bug ("Webhook delivery retries without a limit"). Do not use a prefix
such as "Feature:" unless the repository uses one.

**Summary** — Write two or three sentences. Say what the issue is about and
why it matters. A reader who reads only this section must understand the
issue.

**Problem** — Describe the current state and its effect. Say who is
affected and how. Give evidence: error text in a code block, numbers, links,
or file paths. For a bug, use this sub-structure:

- **Steps to reproduce** — a numbered list.
- **Expected result**
- **Actual result**
- **Environment** — version, platform, configuration.

Do not describe the solution in this section.

**Proposal** — Describe the change. Name the modules, files, APIs or
configuration the change touches, with the project's own names. Refer to
the docs that support the change, with relative paths such as
`docs/architecture/queues.md`. If the developer considered other options,
add a short **Alternatives considered** list with one line about why each
option was not chosen. Describe the intent, not every line of code.

**Open Design Questions** — Use a numbered list. Write each item as a real
question that the team can answer. Add the options and the trade-off when
you know them. Include assumptions you made, conflicts with the docs that
are not resolved, and decisions that need an owner. If no question is open,
write "None."

**Acceptance Criteria** — Use a GitHub task list (`- [ ]`). Write each item
as an observable, testable statement of the result:

- Good: "- [ ] A delivery that fails five times moves to the dead-letter
  queue."
- Bad: "- [ ] Retries work correctly."

Include tests and documentation updates when the change needs them.

### Links and references

- Refer to repository files with relative paths in backticks.
- Refer to related issues or pull requests with `#123` only if the developer
  or the docs gave the number. Do not invent numbers or links.
- Do not add facts that you did not get from the developer, the docs or the
  code. If a section needs a fact you do not have, ask for it or put it in
  Open Design Questions.

---

## Writing standard — ASD-STE100 (Simplified Technical English)

Write all the issue text in STE. STE removes ambiguity, so readers who do
not speak English as a first language, and tired reviewers, can read the
issue in one pass. Apply the rules to the prose in each section. Do not
apply them to code, error messages, file paths, identifiers, or quotations
from logs. Keep those exactly as they are.

Technical terms that the project uses are allowed (API, endpoint, commit,
queue, the names of modules). Keep them, and use each one in the same way
each time.

Apply these rules:

1. **Short sentences.** Use 20 words or fewer in an instruction. Use 25
   words or fewer in a description.
2. **One idea per sentence.** Give one instruction or one fact in each
   sentence.
3. **Active voice.** Name who or what does the action: "The worker retries
   the job", not "The job is retried". Use passive only when the actor is
   unknown.
4. **Simple verb forms.** Use the simple present, past and future. Do not
   use an -ing form where a simple form works.
5. **Verb first in instructions.** Write commands as commands: "Add a
   timeout." Do not write "A timeout should be added."
6. **One word, one meaning.** Use the same word for the same thing in the
   full issue. Do not change "job" to "task" to "work item" for style.
7. **No long noun clusters.** Break a group of more than three nouns:
   "the timeout of the retry queue for webhooks", not "webhook retry queue
   timeout value".
8. **Keep articles.** Write "the", "a" and "an". Do not use telegraphic
   style.
9. **Conditions first.** Put the condition before the instruction or
   result: "If the token expired, the client sends a refresh request."
10. **Lists for more than three items.** Use a vertical list.
11. **Short paragraphs.** Use one topic for each paragraph, and six
    sentences or fewer.
12. **Simple words.** Use the simple word, not the complex one. See
    `references/ste-word-list.md` for common replacements.
13. **No filler.** Remove hedges and filler words such as "basically",
    "essentially", "just", "simply", "actually", "quite", "it is worth
    noting".
14. **No semicolons.** Write two sentences.

### Self-check before you send

Read the draft once as an editor:

- Count the words in the longest sentences. Split any sentence over the
  limit.
- Find passive voice, -ing forms, noun clusters and filler words. Fix them.
- Make sure each name for a part stays the same through the issue.
- Make sure each acceptance criterion is testable.
- Make sure each fact has a source: the developer, a doc path, or the code.

Do not show this check to the developer.

## Example

Developer input: "webhooks keep retrying forever when the customer endpoint
is down, it floods our queue. want a cap + DLQ."

After phase 2, the skill found `docs/webhooks.md` (it says failed deliveries
retry "with backoff") and `docs/adr/0007-queues.md` (it says all queues use
SQS). After two rounds of questions, the output was:

````markdown
# Add a retry limit and a dead-letter queue to webhook delivery

## Summary

Webhook delivery retries a failed request without a limit. When a customer
endpoint is down, the retries fill the delivery queue and delay webhooks for
all other customers. This issue adds a retry limit and a dead-letter queue.

## Problem

The delivery worker retries each failed webhook with exponential backoff.
The worker has no maximum number of retries.

On 2026-10-12, one customer endpoint was down for six hours. The queue grew
to 480,000 messages. The median delivery time for other customers went from
2 seconds to 41 minutes.

`docs/webhooks.md` describes the backoff. It does not describe a limit.

## Proposal

- Add a maximum number of attempts to the delivery worker. Read the value
  from the `WEBHOOK_MAX_ATTEMPTS` setting. The default value is 5.
- After the last failed attempt, move the message to a new SQS dead-letter
  queue, `webhooks-dlq`. This follows `docs/adr/0007-queues.md`.
- Record the endpoint, the last status code and the attempt count with each
  message in the dead-letter queue.
- Update `docs/webhooks.md` with the limit and the dead-letter behavior.

**Alternatives considered**

- Drop the message after the limit. The team cannot replay dropped
  messages, so this option loses data.

## Open Design Questions

1. Who can replay messages from the dead-letter queue: (a) support staff
   from the admin panel, or (b) engineers with a script only?
2. Must the system tell the customer when a webhook moves to the
   dead-letter queue? If yes, which channel: email or the dashboard?
3. How long does the dead-letter queue keep a message? The SQS maximum is
   14 days.

## Acceptance Criteria

- [ ] A delivery that fails 5 times moves to `webhooks-dlq`.
- [ ] An operator can change the limit with `WEBHOOK_MAX_ATTEMPTS`
      without a code change.
- [ ] Each message in `webhooks-dlq` contains the endpoint, the last
      status code and the attempt count.
- [ ] A failed endpoint does not increase the median delivery time for
      other customers by more than 10 seconds in the load test.
- [ ] `docs/webhooks.md` describes the limit and the dead-letter queue.
````