# SafeMed — Daily Workflow

**Read `SETUP.md` first.** That gets the project onto your machine — you only do
it once.

**This guide is what you do every day after that**: open the project, pick up a
task, write code, and get it reviewed.

Mac instructions. Windows differences are noted at the bottom.

---

## Part 1 — Open the project in VS Code

### Install VS Code (once)

Download from <https://code.visualstudio.com/>, open the `.zip`, and drag
**Visual Studio Code** into your **Applications** folder.

### Open the project

1. Open **Visual Studio Code** from Applications
2. Menu bar: **File → Open Folder…**
3. Navigate to **your home folder → dev → safemed**
4. Click **Open**
5. If it asks "Do you trust the authors of the files in this folder?", click
   **Yes, I trust the authors** — it's your own code

**Open the `safemed` folder itself, not individual files.** VS Code then treats
it as a project: you get the file tree on the left, and the built-in terminal
starts in the right place.

✅ You should see `backend`, `docs`, `README.md`, and `docker-compose.yml` in
the sidebar.

### Make the `code` command work (optional, saves time later)

1. Press `Command (⌘) + Shift + P`
2. Type `shell command`
3. Choose **Shell Command: Install 'code' command in PATH**

Now you can open the project from Terminal with:

```
cd ~/dev/safemed
code .
```

### Install two extensions

Click the **Extensions** icon in the left bar (four squares), then search and
install:

- **Docker** (by Microsoft) — see your running containers in the sidebar
- **Python** (by Microsoft) — autocomplete and error highlighting
- **ESLint** — only if you're working on the frontend

### The built-in terminal

Press `Control + \`` (the backtick key, above Tab) to open a terminal inside VS
Code. It already starts in `~/dev/safemed`, so you never need to `cd`.

You will usually want **two** terminals:

- **Terminal 1** — runs the server (`docker compose up`). Leave it alone.
- **Terminal 2** — everything else. Open it with the **`+`** icon in the
  terminal panel.

---

## Part 2 — The daily loop

Six steps. Do all of them, in order, for every task.

### Step 1 — Get the latest code

Someone else has merged work since you last looked. Start from their work, not
from yesterday's copy.

```
git checkout main
git pull
```

> **Skipping this is the #1 cause of merge conflicts.**

### Step 2 — Pick your task from the board

Go to the project board, find a card assigned to you in **Todo**, and drag it to
**In Progress**.

Note its issue number — the `#4` in the title. You need it later.

### Step 3 — Make a branch

A **branch** is your own copy of the code where you can work without affecting
anyone else.

```
git checkout -b feature/short-description
```

Name it after the task:

| Task | Branch name |
|---|---|
| Add login endpoints | `feature/auth-endpoints` |
| Build the patient dashboard | `feature/patient-dashboard` |
| Fix a dose-time bug | `fix/dose-time-offset` |

> **Never work directly on `main`.** `main` must always run, because it is what
> we demo.

### Step 4 — Start the app and write code

In **Terminal 1**:

```
docker compose up
```

Wait for `Uvicorn running on http://0.0.0.0:8000`.

Now edit files in VS Code. **The backend reloads automatically** — save a `.py`
file and watch Terminal 1 restart the server by itself. Refresh
<http://localhost:8000/docs> to see your change.

Where your files are:

| You | Work in |
|---|---|
| **Victory** | `backend/app/models/`, `backend/app/services/` |
| **Chima** | `backend/app/api/`, `backend/app/core/security.py` |
| **Pacifique** | `frontend/` |

Stay in your own folders. If you need something from someone else's area, ask
them rather than editing it — that is how conflicts start.

> **One exception:** if you change `requirements.txt` or a `Dockerfile`, restart
> with `docker compose up --build`. Hot reload does not reinstall packages.

### Step 5 — Save your work with git

Check what you changed:

```
git status
```

Then stage and commit:

```
git add .
git commit -m "feat: add login endpoint"
```

**Commit as you go, not once at the end.** Three small commits tell a clearer
story than one giant one — and they're easier to undo if something breaks.

Commit message prefixes:

| Prefix | For |
|---|---|
| `feat:` | A new feature |
| `fix:` | A bug fix |
| `docs:` | Documentation |
| `test:` | Tests |
| `chore:` | Dependencies, config, cleanup |

### Step 6 — Push and open a pull request

```
git push -u origin feature/short-description
```

(After the first push on a branch, just `git push`.)

Then:

1. Go to <https://github.com/victory113/safemed>
2. A yellow banner appears: **"Compare & pull request"** — click it
3. In the description, write what you did, and on its own line:

   ```
   Closes #4
   ```

   Use your real issue number. **This line matters** — it links the code to the
   ticket, closes the issue when merged, and moves the card to Done by itself.
4. On the right, set **Reviewers** to a teammate
5. Click **Create pull request**
6. Drag your card to **In Review** on the board

Then tell the team chat that it's ready for review.

---

## Part 3 — After review

**If changes are requested:** make them on the same branch, then commit and push
again. The pull request updates itself — you do not open a new one.

```
git add .
git commit -m "fix: address review comments"
git push
```

**Once approved:** click **Merge pull request** on GitHub, then **Delete
branch** when offered. Your card moves to Done automatically.

**Then start the next task from Step 1** — and the `git pull` there now brings
down your own merged work plus everyone else's.

---

## Part 4 — Reviewing someone else's pull request

You will be asked to review. It is not a rubber stamp.

1. Open the pull request → **Files changed** tab
2. Read the changes. Click the **`+`** beside any line to leave a comment
3. Click **Review changes** and choose:
   - **Comment** — questions, no verdict
   - **Approve** — looks good to merge
   - **Request changes** — something needs fixing first

Useful things to check, even if you don't know the area well:

- Does the description explain what it does?
- Are there tests for new behaviour?
- Any passwords, keys, or secrets accidentally committed?
- Does anything touch a file outside the author's area without warning?

---

## Part 5 — When things go wrong

### "I started working and forgot to make a branch"

You're on `main` with uncommitted changes. Move them to a branch:

```
git checkout -b feature/my-task
```

Your changes come with you. Commit as normal.

### "git pull says I have conflicts"

Two people changed the same lines. VS Code shows the conflict with
**Accept Current Change / Accept Incoming Change / Accept Both**.

**If you don't understand both sides, stop and ask the other person.** Guessing
here silently deletes someone's work.

### "My change isn't showing up in the browser"

1. Did you save the file? (`⌘ + S`)
2. Does Terminal 1 still say `Uvicorn running`, or did it crash with an error?
3. Hard-refresh the browser: `⌘ + Shift + R`
4. If you changed dependencies: `docker compose up --build`

### "docker: command not found" or "Cannot connect to the Docker daemon"

Docker Desktop isn't running. Open it from Applications, wait for
**Engine running**, then try again.

### "I want to throw away my changes and start over"

```
git checkout -- .
```

This permanently discards uncommitted changes in the current folder. There is no
undo.

### "I committed something I shouldn't have"

Don't push. Tell Victory. Undoing a local commit is easy; undoing a pushed one
is not.

---

## Part 6 — Windows differences

Everything with `git` and `docker` is identical. Only these differ:

| Mac | Windows |
|---|---|
| `Control + \`` opens terminal | `Control + \`` (same) |
| `⌘ + Shift + P` command palette | `Ctrl + Shift + P` |
| `⌘ + S` save | `Ctrl + S` |
| `cd ~/dev/safemed` | `cd $HOME\dev\safemed` |
| `cp .env.example .env` | `Copy-Item .env.example .env` |

---

## Quick reference

```
git checkout main            # go to the main branch
git pull                     # get everyone's latest work
git checkout -b feature/x    # create and switch to a new branch
git status                   # what have I changed?
git add .                    # stage all changes
git commit -m "feat: ..."    # save a snapshot
git push                     # upload to GitHub
git branch                   # which branch am I on?

docker compose up            # start the app
docker compose up --build    # start after changing dependencies
docker compose down          # stop everything
docker compose logs -f api   # watch the server logs
```
