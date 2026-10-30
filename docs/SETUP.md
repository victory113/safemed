# SafeMed — Developer Setup

Everything you need to get SafeMed running on your machine. It should take
about 20 minutes, most of which is downloads.

You do **not** need to install Python, PostgreSQL, or Redis. Docker provides
all three.

---

## 1. Install the prerequisites

### Git
Download from <https://git-scm.com/download/win> and install with the default
options. Check it worked by opening **PowerShell** and running:

```powershell
git --version
```

### Docker Desktop

Docker on Windows needs WSL2 (Windows Subsystem for Linux) first.

**Step A — install WSL2.** Open PowerShell **as Administrator**
(right-click → Run as administrator):

```powershell
wsl --install
```

Then **restart your computer**. On restart you may be asked to create a Linux
username and password — any value is fine, just remember it.

**Step B — install Docker Desktop.** Download from
<https://www.docker.com/products/docker-desktop/> (Windows, AMD64). During
setup keep **"Use WSL 2 instead of Hyper-V"** checked.

Launch Docker Desktop. You can **skip the sign-in** — look for
"Continue without signing in". No account is needed for this project.

Wait until the bottom-left of the Docker Desktop window says
**"Engine running"**. Docker only works while Docker Desktop is open.

Verify:

```powershell
docker --version; docker compose version; docker run --rm hello-world
```

The last command should print "Hello from Docker!".

### Visual Studio Code
Download from <https://code.visualstudio.com/>. After installing, add the
**Docker** extension (Extensions icon → search "Docker" → the Microsoft one).

---

## 2. Set your git identity

Git labels every commit with a name and email. **Use the email that is on your
GitHub account**, otherwise GitHub will not link your commits to your profile —
and our professor grades individual contribution from that history.

```powershell
git config --global user.name "Your Full Name"; git config --global user.email "your.github.email@example.com"
```

Confirm the email is listed and **verified** at
<https://github.com/settings/emails>.

---

## 3. Clone the project

```powershell
cd $HOME; mkdir dev -Force; cd dev; git clone https://github.com/victory113/safemed.git; cd safemed
```

This creates `C:\Users\<you>\dev\safemed`.

> Keep the project **out of OneDrive**. OneDrive syncs thousands of small files
> and can corrupt a git repository or lock files mid-write.

---

## 4. Create your local settings file

```powershell
Copy-Item .env.example .env
```

`.env` holds local configuration such as the database password. It is
deliberately **not** in git — that is why you create it yourself. `.env.example`
is the committed template listing every variable you need.

Never commit `.env`.

---

## 5. Start everything

Make sure Docker Desktop is running, then:

```powershell
docker compose up --build
```

The first run takes a few minutes: it downloads PostgreSQL, Redis, and Python,
then installs our packages. Later runs take seconds.

Wait for this line:

```
safemed-api  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Leave this terminal running — it is the server.** Open a second terminal for
other commands (the `+` icon in VS Code's terminal panel).

---

## 6. Check it works

Open these in your browser:

| URL | What you should see |
|---|---|
| <http://localhost:8000/health> | `"status":"ok"` and **`"database":"connected"`** |
| <http://localhost:8000/docs> | Interactive API documentation |

If `database` says anything other than `connected`, stop and post the terminal
output in the team chat.

---

## 7. Useful commands

Run these from `dev\safemed` in a second terminal.

| Command | What it does |
|---|---|
| `docker compose up` | Start everything (no rebuild) |
| `docker compose up --build` | Rebuild images, then start — use after dependency changes |
| `docker compose down` | Stop and remove containers (your data survives) |
| `docker compose ps` | List services and their health |
| `docker compose logs -f api` | Follow the API logs |
| `docker compose exec db psql -U safemed -d safemed` | Open a SQL prompt (`\dt` lists tables, `\q` quits) |
| `docker compose down -v` | **Deletes the database volume.** Only when you want a clean slate |

---

## 8. How we work — read this before your first change

**Never commit directly to `main`.** `main` must always run.

For every piece of work:

```powershell
# 1. Start from an up-to-date main
git checkout main; git pull

# 2. Create a branch named after your task
git checkout -b feature/short-description

# 3. ... make your changes, and test them ...

# 4. Commit in small, meaningful units
git add .; git commit -m "feat: add X"

# 5. Push your branch
git push -u origin feature/short-description
```

Then open a **Pull Request** on GitHub, ask a teammate to review it, and merge
once approved. Move your board ticket to Done.

### Commit message style

Start with a type, then a short description in the present tense:

```
feat: add medication entry endpoint
fix: correct dose schedule off-by-one
docs: expand handbook chapter 4
test: add safety engine interaction cases
chore: update dependencies
```

### Who owns what

| Person | Area |
|---|---|
| Victory | Database schema, safety rules engine, RxNorm + openFDA integration, background worker, AI explanation layer |
| Chima | Authentication, roles and permissions, consent grants, audit log, notification delivery |
| Pacifique | React frontend: patient and caregiver dashboards, medication entry, accessibility |

Stay in your own area where you can. When you need something from someone
else's, ask for the interface rather than editing their files.

---

## 9. If something goes wrong

**`docker: command not found`** — Docker Desktop isn't running, or you need to
reopen your terminal after installing it.

**`port is already allocated`** — something else is using port 8000. Stop it, or
tell Victory so we can change the mapping.

**`database: unavailable` on /health** — PostgreSQL is still starting. Wait ten
seconds and refresh. If it persists, run `docker compose down` then
`docker compose up --build`.

**The API won't pick up my code change** — the API container hot-reloads
`backend/`. If you changed `requirements.txt` or a Dockerfile, you must run
`docker compose up --build`.

**Something is deeply broken and I want to start over:**

```powershell
docker compose down -v; docker compose up --build
```

This deletes the database and rebuilds from scratch. Safe right now — we only
use synthetic data.

---

## 10. Next

Read `docs/HANDBOOK.md`. It explains what SafeMed is, why each tool was chosen,
and how the pieces fit together. Chapters 1 to 3 cover everything built so far.
