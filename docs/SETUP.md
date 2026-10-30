# SafeMed — Setup Guide

Follow this from top to bottom. Do not skip steps.

**Time needed:** about 30 minutes, mostly waiting for downloads.

**This guide is for Mac.** Windows instructions are at the bottom in Appendix A.

**Good news:** you do NOT need to install Python, PostgreSQL, or Redis.
Docker installs and runs all of them for you.

---

## How to use this guide

Every step looks like this:

> **Type this:** the exact command to paste
>
> **You should see:** what tells you it worked

If what you see does not match, **stop** and post a screenshot in the team chat.
Do not continue — a broken step makes every later step fail in confusing ways.

### Opening Terminal

You will type commands into an app called **Terminal**.

1. Press `Command (⌘) + Space`
2. Type `terminal`
3. Press `Enter`

A window with text appears. That is Terminal. You type a command, press Enter,
and it runs.

To paste: `Command (⌘) + V`.

---

# Part 1 — Install Docker Desktop

Docker runs our database and server for you, so you don't install them yourself.

### Step 1.1 — Find out which chip your Mac has

This matters because there are two different downloads.

1. Click the  **Apple menu** (top-left of your screen)
2. Click **About This Mac**
3. Look at the **Chip** or **Processor** line

| If it says | You have |
|---|---|
| Apple M1, M2, M3, or M4 | **Apple Silicon** |
| Intel Core i5, i7, i9 | **Intel** |

Remember which one. You need it in the next step.

### Step 1.2 — Download Docker Desktop

Go to <https://www.docker.com/products/docker-desktop/>

Click the download button that matches your chip:

- **Apple Silicon** → "Download for Mac - Apple Silicon"
- **Intel** → "Download for Mac - Intel Chip"

Downloading the wrong one will not work, so double-check.

### Step 1.3 — Install it

1. Open the downloaded `Docker.dmg` file
2. Drag the **Docker** icon onto the **Applications** folder
3. Open **Applications** and double-click **Docker**
4. If macOS warns that it was downloaded from the internet, click **Open**
5. It will ask for your Mac password — this is normal, Docker needs it to install
   a helper tool
6. Accept the terms when asked

### Step 1.4 — Skip the sign-in

Docker will push you to create an account. **You do not need one.**

Look for **"Continue without signing in"** or a small **Skip** link. It is easy
to miss — often small text at the bottom of the window.

### Step 1.5 — Wait for Docker to start

Look at the **bottom-left** of the Docker Desktop window. Wait until it says:

**🟢 Engine running**

This takes a minute or two the first time.

> **Important:** Docker only works while Docker Desktop is open. If you quit it,
> the project stops working. Leave it running whenever you work on SafeMed.

### Step 1.6 — Check Docker works

Open **Terminal** and paste this:

> **Type this:**
> ```
> docker run --rm hello-world
> ```
>
> **You should see:** a message that begins **"Hello from Docker!"**

If you see `command not found`, Docker Desktop is not running, or you need to
close Terminal and open it again.

✅ **Checkpoint 1 complete.**

---

# Part 2 — Check Git

Git is the tool that tracks our code. Most Macs already have it.

> **Type this:**
> ```
> git --version
> ```
>
> **You should see:** something like `git version 2.39.5`

**If a popup appears** saying "The git command requires the command line
developer tools", click **Install** and wait. It takes a few minutes. Then run
the command again.

✅ **Checkpoint 2 complete.**

---

# Part 3 — Tell Git who you are

Git puts your name and email on every change you make. This is how our professor
sees who did what, so it has to be right.

**Use the same email address as your GitHub account.**

> **Type this** (replace with your real name and GitHub email):
> ```
> git config --global user.name "Chima Onochie"
> ```
> ```
> git config --global user.email "your.github.email@example.com"
> ```
>
> **Then check it:**
> ```
> git config --global --list | grep user
> ```
>
> **You should see:** your name and email printed back

### Important: verify your email on GitHub

1. Go to <https://github.com/settings/emails>
2. Make sure the email you just used is listed and says **Verified**
3. If it is not there, click **Add email address**, then click the link GitHub
   emails you

**If you skip this, GitHub will not count your work as yours.** Your commits
will show a grey avatar instead of your profile, and it will look like you did
nothing.

✅ **Checkpoint 3 complete.**

---

# Part 4 — Download the project

### Step 4.1 — Make a folder and clone the code

> **Type this** (you can paste all three lines at once):
> ```
> mkdir -p ~/dev
> cd ~/dev
> git clone https://github.com/victory113/safemed.git
> ```
>
> **You should see:** `Cloning into 'safemed'...` and then `done.`

This creates a folder at `/Users/yourname/dev/safemed`.

**If it asks for a username and password:** you are not a collaborator on the
repository yet. Ask Victory to add you (GitHub → Settings → Collaborators).

### Step 4.2 — Go into the project folder

> **Type this:**
> ```
> cd ~/dev/safemed
> ```
>
> **You should see:** nothing. That is correct — `cd` is silent when it works.

> **Check you are in the right place:**
> ```
> ls
> ```
>
> **You should see:** `README.md  backend  docker-compose.yml  docs`

**Everything from here must be run from this folder.** If you close Terminal
and come back later, run `cd ~/dev/safemed` first.

✅ **Checkpoint 4 complete.**

---

# Part 5 — Create your settings file

The project needs a file called `.env` holding local settings like the database
password. It is deliberately not included in the download, so you create it from
the template.

> **Type this:**
> ```
> cp .env.example .env
> ```
>
> **You should see:** nothing. That means it worked.

> **Check it exists:**
> ```
> ls -a | grep .env
> ```
>
> **You should see:** both `.env` and `.env.example`

> **Never share or commit the `.env` file.** Real projects keep passwords and
> API keys in it.

✅ **Checkpoint 5 complete.**

---

# Part 6 — Start SafeMed

Make sure **Docker Desktop is open** and says "Engine running".

> **Type this:**
> ```
> docker compose up --build
> ```

**The first time, this takes 3–10 minutes.** It is downloading PostgreSQL,
Redis, and Python, then installing our packages. Lots of text will scroll by.
That is normal.

> **You should see, eventually:**
> ```
> safemed-api  | INFO:     Uvicorn running on http://0.0.0.0:8000
> ```

### Leave this Terminal window open

**This window is now the server.** If you close it or press `Control + C`,
SafeMed stops.

To run other commands, open a **second** Terminal tab with `Command (⌘) + T`.

✅ **Checkpoint 6 complete.**

---

# Part 7 — Check it works

Open your web browser and visit these two addresses.

### 7.1 — Health check

<http://localhost:8000/health>

> **You should see:**
> ```json
> {"status":"ok","service":"SafeMed","environment":"development","database":"connected"}
> ```

**The important part is `"database":"connected"`.** That proves the server is
talking to the database.

If it says anything else, wait 10 seconds and refresh — the database may still
be starting.

### 7.2 — API documentation

<http://localhost:8000/docs>

> **You should see:** a page titled **SafeMed API** with expandable sections.

This page is generated automatically from our code. You can click an endpoint
and press "Try it out" to call the real server.

🎉 **If both pages work, you are fully set up.** Tell the team chat.

---

# Part 8 — Everyday commands

Run these from `~/dev/safemed` in a second Terminal tab.

| What you want | Command |
|---|---|
| Start SafeMed | `docker compose up` |
| Start after changing dependencies | `docker compose up --build` |
| Stop SafeMed | `Control + C` in the server window |
| Stop and clean up | `docker compose down` |
| See what is running | `docker compose ps` |
| Watch the server logs | `docker compose logs -f api` |
| Get the newest code from the team | `git pull` |
| Start completely fresh (deletes the database) | `docker compose down -v` then `docker compose up --build` |

---

# Part 9 — How we work as a team

**Never make changes directly on `main`.** `main` must always work, because it
is what we demo.

For every task you are given:

```
# 1. Get the latest code
git checkout main
git pull

# 2. Make a branch for your task
git checkout -b feature/login-page

# 3. ...do your work, and test that it still runs...

# 4. Save your work
git add .
git commit -m "feat: add login page"

# 5. Upload your branch
git push -u origin feature/login-page
```

Then go to GitHub, click **Compare & pull request**, and ask a teammate to
review it. Once approved, merge it and move your ticket to Done.

### Naming your commits

Start with a word describing the type:

| Prefix | Use it for |
|---|---|
| `feat:` | A new feature |
| `fix:` | Fixing a bug |
| `docs:` | Documentation only |
| `test:` | Adding tests |
| `chore:` | Dependencies, config, cleanup |

Example: `feat: add caregiver dashboard`

### Who owns what

| Person | Area |
|---|---|
| **Victory** | Database design, safety rules engine, RxNorm and FDA data, background worker, AI explanation |
| **Chima** | Login, user roles and permissions, consent, audit log, sending notifications |
| **Pacifique** | React frontend: patient dashboard, caregiver dashboard, medication forms, accessibility |

Work inside your own area. If you need something from someone else's area, ask
them for it rather than editing their files — that is how merge conflicts start.

---

# Part 10 — When something goes wrong

### `docker: command not found`
Docker Desktop is not running. Open it from Applications and wait for
"Engine running". Then close Terminal, open it again, and retry.

### `Cannot connect to the Docker daemon`
Same cause. Docker Desktop must be open.

### `"database":"unavailable"` on the health page
PostgreSQL is still starting. Wait 10 seconds and refresh. If it persists:
```
docker compose down
docker compose up --build
```

### `port is already allocated`
Something else on your Mac is using that port. Tell Victory — we can change it.

### `permission denied` while installing Docker
Normal. macOS is asking for your Mac login password. Type it and press Enter.
Nothing appears as you type — that is how Terminal handles passwords.

### The page won't load at all
Check that the server window still shows `Uvicorn running`. If it scrolled past
an error, copy the last 20 lines into the team chat.

### I want to start over completely
```
cd ~/dev/safemed
docker compose down -v
docker compose up --build
```
This deletes the local database and rebuilds everything. Safe to do — we only
use fake test data.

---

# Part 11 — What to read next

Open `docs/HANDBOOK.md` in the project folder. It explains what SafeMed is, why
we chose each tool, and how the pieces fit together.

In VS Code you can read it nicely formatted with `Command (⌘) + Shift + V`.

---

# Appendix A — Windows setup

Same steps, different commands.

**1. Install WSL2 first.** Open PowerShell **as Administrator**
(right-click → Run as administrator):
```powershell
wsl --install
```
Then **restart your computer**.

**2. Install Docker Desktop** from
<https://www.docker.com/products/docker-desktop/> (Windows, AMD64). Keep
"Use WSL 2" checked. Skip the sign-in.

**3. Install Git** from <https://git-scm.com/download/win> with default options.

**4. The commands differ slightly:**

| Mac | Windows (PowerShell) |
|---|---|
| `mkdir -p ~/dev` | `mkdir $HOME\dev -Force` |
| `cd ~/dev/safemed` | `cd $HOME\dev\safemed` |
| `cp .env.example .env` | `Copy-Item .env.example .env` |
| `ls -a \| grep .env` | `Get-ChildItem -Force \| Select-String env` |
| `git config --global --list \| grep user` | `git config --global --list \| Select-String user` |

Everything with `docker` and `git` is identical on both.

---

# Appendix B — Useful VS Code setup

Not required, but it makes life easier.

1. Install VS Code from <https://code.visualstudio.com/>
2. Open the project: **File → Open Folder** → `dev/safemed`
3. Install the **Docker** extension (Extensions icon → search "Docker")
4. Open a terminal inside VS Code with `Control + ~` — it starts in the project
   folder automatically, so you never need to `cd`
