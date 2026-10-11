# Connect GitHub (free, about 2 minutes)

Skill Scout reads public GitHub data to check skills that are not in its index yet. Without a GitHub login, GitHub allows 60 requests an hour, which can run out when several new skills need checking. Pick one option:

**1. Sign in with the GitHub CLI (easiest)**
Install the GitHub CLI from https://cli.github.com, run `gh auth login`, and choose GitHub.com with browser login. Skill Scout uses this login automatically.

**2. Use Git's saved GitHub login**
If you already push to GitHub from this computer, Skill Scout can use that saved login. It asks you once before it does.

**3. Add a free token**
1. On GitHub: Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
2. Repository access: **Public repositories (read-only)**. Add no other permissions.
3. Run `python scripts/github_auth.py init`. It prints the path of your settings file.
4. Open that file in a text editor and put the token between the quotes after `"github_token"`.

Do not paste your token into the chat. Skill Scout sends it only to GitHub and never stores it anywhere else.
