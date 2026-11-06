# SafeMed — Team Guide

**Start here.** This explains who does what, how we use GitHub and VS Code, and
exactly how to take a task from "assigned to me" to "merged".

None of us has worked this way before. That is normal. Follow the steps
literally and ask in the group chat the moment something does not match.

---

## The four documents

| Document | What it is | When to read it |
|---|---|---|
| **TEAM_GUIDE.md** (this one) | How we work | Now, then whenever you are unsure |
| `SETUP.md` | Installing everything, once | Already done |
| `WORKFLOW.md` | The git command reference | Keep it open while you work |
| `API_CONTRACT.md` | The exact shapes our code exchanges | Before you write code |

---

## 1. What we are building

SafeMed watches a patient's medication list against authoritative drug-safety
data and alerts their caregiver when something needs attention — even when
nobody has the app open.

Three rules the project lives by:

1. **Safety findings come from data and fixed rules, never from AI.** AI only
   rewrites a finding into plain language.
2. **SafeMed never diagnoses, prescribes, or tells anyone to change a
   medication.** It flags things and says "contact your pharmacist".
3. **We only ever use fake patient data.**

---

## 2. Who owns what

Ownership means *you are responsible for it and you review changes to it*. It
does not mean nobody else may ever touch it — but ask first.

| Person | Area | Files you work in |
|---|---|---|
| **Victory** | Data, safety engine, shared UI | `backend/app/models/`, `backend/app/services/`, `backend/app/api/v1/medications.py`, `backend/app/api/v1/doses.py`, `frontend/src/components/`, `frontend/src/styles/` |
| **Chima** | Security and access | `backend/app/core/security.py`, `backend/app/api/deps.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/consent.py`, `backend/app/services/audit.py` |
| **Pacifique** | Frontend screens and API client | `frontend/src/api/`, `frontend/src/routes.tsx`, `frontend/src/pages/Login.tsx`, `Register.tsx`, `CaregiverDashboard.tsx` |

### Shared files — announce in chat before editing

`backend/app/main.py` · `backend/requirements.txt` · `frontend/src/App.tsx` ·
`frontend/package.json` · `docker-compose.yml` · `docs/API_CONTRACT.md`

If you change `requirements.txt` or `package.json`, say so, because everyone
else has to rebuild afterwards.

---

## 3. The five rules

1. **Never commit directly to `main`.** `main` must always run — it is what we
   demo. All work happens on a branch and arrives through a pull request.
2. **One task, one branch, one pull request.** Do not mix two features.
3. **Always `git pull` on `main` before starting something new.** Skipping this
   is the number one cause of merge conflicts.
4. **Every pull request description contains `Closes #<number>`.** That links
   your code to a ticket and to your name. Our professor grades this.
5. **Stay in your own files.** If you need something in someone else's area,
   ask them for it.

---

## 4. Your first task, start to finish

A complete worked example. Chima's auth ticket is used here; substitute your
own task and branch name.

### Step 1 — Get the latest code

Open VS Code, then open a terminal inside it with `` Control + ` ``.

```
git checkout main
git pull
```

> `checkout main` moves you to the shared branch. `pull` downloads everyone
> else's merged work. Do this **every time** you start something new.

### Step 2 — Claim your task on the board

Go to the **SafeMed** project board on GitHub. Find your card in **Todo** and
drag it to **In Progress**.

Write down its number — the `#5` in the title. You need it in step 7.

### Step 3 — Make a branch

```
git checkout -b feature/auth
```

> A branch is your own copy of the code. You can break anything on it without
> affecting anyone. `-b` means "create it and switch to it".

Confirm it worked:

```
git branch
```

You should see `* feature/auth` with the asterisk marking where you are.

### Step 4 — Start the app

In a **separate** terminal (click `+` in the terminal panel):

```
docker compose up
```

Wait for `Uvicorn running on http://0.0.0.0:8000`. Leave that terminal alone —
it is now the server.

Frontend work needs a third terminal:

```
cd frontend
npm run dev
```

### Step 5 — Write the code

Read your section of `API_CONTRACT.md` first. It gives the exact shapes, so
your work fits with everyone else's without a conversation.

Save a file and the server reloads itself. Check your work at:

- http://localhost:8000/docs — backend, click an endpoint and press
  **Try it out**
- http://localhost:5173 — frontend

> **If you changed `requirements.txt` or `package.json`**, hot reload is not
> enough. Stop the server (`Control + C`) and run `docker compose up --build`.

### Step 6 — Save your work

See what you changed:

```
git status
```

Then:

```
git add .
git commit -m "feat: add login endpoint with JWT"
```

> `add` marks files for the next save. `commit` saves them permanently with a
> message. Commit several times as you go — three small commits are better
> than one giant one.

Message prefixes: `feat:` new feature · `fix:` bug fix · `docs:` documentation
· `test:` tests · `chore:` config and cleanup.

### Step 7 — Push and open a pull request

```
git push -u origin feature/auth
```

> `push` uploads your branch to GitHub. `-u origin feature/auth` tells git to
> remember the pairing — after the first time, plain `git push` is enough.

Then on GitHub:

1. Open <https://github.com/victory113/safemed>
2. A yellow banner appears with **Compare & pull request** — click it
3. Title: what you did, e.g. `Add password hashing and JWT authentication`
4. Description: what you built, anything the reviewer should know, and on its
   own line:

   ```
   Closes #5
   ```

5. Set **Reviewers** to a teammate
6. Click **Create pull request**
7. Drag your card to **In Review** on the board
8. Say in the group chat that it is ready

### Step 8 — Handle review comments

Your reviewer may ask for changes. Make them **on the same branch**:

```
git add .
git commit -m "fix: address review comments"
git push
```

The pull request updates itself. Do not open a second one.

### Step 9 — Merge

Once approved, click **Merge pull request** → **Confirm merge** →
**Delete branch**.

Your issue closes automatically and the card moves to **Done**.

### Step 10 — Go again

```
git checkout main
git pull
git checkout -b feature/next-thing
```

---

## 5. How to review someone's pull request

You will be asked. It is not a rubber stamp, and you do not need to be an
expert in their area.

1. Open the pull request → **Files changed**
2. Read it. Click the `+` next to any line to ask a question
3. Click **Review changes** and pick:
   - **Comment** — questions, no verdict
   - **Approve** — fine to merge
   - **Request changes** — needs a fix first

Worth checking every time:

- Does the description say what it does and why?
- Are there tests for new behaviour?
- Any passwords, tokens, or keys committed by accident?
- Does it touch files outside their area without a heads-up?
- Does it match `API_CONTRACT.md`?

**Asking "why did you do it this way?" is a good review comment.** It is not
criticism, and the answer often improves the code.

---

## 6. Definition of done

A task is done only when **all** of these are true:

- [ ] The code works — you ran it and saw it work
- [ ] It matches `API_CONTRACT.md`
- [ ] There are tests for the new behaviour
- [ ] Nothing in `main` broke
- [ ] A teammate reviewed and approved it
- [ ] The pull request is merged
- [ ] The board card is in **Done**
- [ ] **You can explain it out loud.** You will be asked in the presentation

That last one is not optional. If you cannot explain your own code, it is not
finished.

---

## 7. When you depend on someone else

This will happen. Do not sit on it.

**Example:** Victory's medication endpoints need `get_current_user`, which
Chima is writing.

How we handle it:

1. The **shape** is agreed first, in `API_CONTRACT.md`. Both people code
   against the agreed shape.
2. Whoever is downstream builds everything that does not need the missing
   piece — the schemas, the database queries, the tests.
3. When the upstream work merges, the downstream person pulls `main` and wires
   it in. Usually a couple of lines.
4. **Say in chat the moment you are blocked**, with what you need. A blocker
   nobody mentioned is the most expensive kind.

---

## 8. Daily rhythm

**Each working day:**
1. `git checkout main && git pull`
2. Check the board for your card
3. Work on your branch
4. Commit as you go
5. Post one line in the chat: what you did, what is next, anything blocking you

**Before you stop for the day:** commit and push, even if it is unfinished.
Work that only exists on your laptop does not exist.

**Twice a week:** review each other's open pull requests. A PR sitting unread
for three days blocks a person.

---

## 9. Common problems

### "docker: command not found"
Docker Desktop is not running. Open it, wait for **Engine running**, retry.

### "database: unavailable" on /health
PostgreSQL is still starting. Wait ten seconds and refresh. If it persists:
`docker compose down` then `docker compose up --build`.

### My change is not showing in the browser
Did you save? Is the server terminal still running or did it crash with an
error? Hard refresh (`Command/Control + Shift + R`). If you changed
dependencies, `docker compose up --build`.

### I forgot to make a branch and worked on main
```
git checkout -b feature/my-task
```
Your uncommitted changes move with you. Commit as normal.

### git says I have conflicts
Two people changed the same lines. VS Code shows both versions with buttons to
accept one or both. **If you do not understand both sides, stop and ask the
other person.** Guessing deletes someone's work.

### The page went blank after switching branches
The dev server was watching files that git moved. Hard refresh. Stop the dev
server before switching branches to avoid it.

### I committed something I should not have
Do not push. Tell Victory immediately. A local mistake is easy to undo; a
pushed one is not.

---

## 10. Where to get answers

| Question | Where |
|---|---|
| How do I install X? | `SETUP.md` |
| What is the git command for…? | `WORKFLOW.md` |
| What shape does that endpoint return? | `API_CONTRACT.md` |
| Why did we build it this way? | `HANDBOOK.md` |
| What am I supposed to be doing? | The project board |
| Anything else | Group chat — ask early, not after two days |
