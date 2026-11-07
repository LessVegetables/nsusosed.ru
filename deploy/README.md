# Deploying nsusosed.ru

Push or merge into the `deploy` branch and [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) ships it to the VPS. Production uses the files in this folder. The repo-root `nginx/` and `docker-compose.yml` are the dev setup and aren't used.

## How it fits together

```
internet ──443──▶ host nginx ──┬── /            static files in /var/www/nsusosed.ru
                               └── /api/  ──▶ 127.0.0.1:1231 ──▶ [api container :8000]
                                                                        │  network "db" (internal)
                                                                  [db container: Postgres]
```

Docker writes its own iptables rules, and those rules go around UFW: a container port published as `1231:8000` would be open to the whole internet, whatever UFW says. So nothing in the stack is published on a public address:

- **`db`** publishes no ports and sits on an `internal` Docker network, with no route in or out. Only the `api` container can reach it.
- **`api`** publishes only on `127.0.0.1:1231`, which is reachable from the VPS itself (nginx) and nothing else.

You can check this on the server at any time: `sudo ss -ltnp | grep docker` should list only `127.0.0.1:1231`.

## What lives where on the VPS

| Path | What | Owner |
|---|---|---|
| `/var/www/nsusosed.ru/` | the static site (`frontend/`, minus dev-only files) | `gh_deploy` |
| `/opt/nsusosed/app/` | `backend/`, the build context for the api image | `gh_deploy` |
| `/opt/nsusosed/compose.yaml` | the stack ([compose.yaml](compose.yaml)) | `root` |
| `/usr/local/bin/nsusosed-redeploy` | rebuild + restart + health check ([nsusosed-redeploy](nsusosed-redeploy)) | `root` |
| `/usr/local/bin/gh-deploy-gate` | allowlist of commands `gh_deploy` may run over SSH ([gh-deploy-gate](gh-deploy-gate)) | `root` |
| `/etc/ssh/sshd_config.d/gh_deploy.conf` | `Match` block that locks down the `gh_deploy` login ([sshd/gh_deploy.conf](sshd/gh_deploy.conf)) | `root` |
| `/etc/ssh/authorized_keys/gh_deploy` | the GitHub Actions public key | `root` |
| `/etc/sudoers.d/nsusosed-deploy` | lets `gh_deploy` run the redeploy script, nothing else ([sudoers/nsusosed-deploy](sudoers/nsusosed-deploy)) | `root` |
| `/etc/nsusosed.env` | secrets and settings | `root`, mode `600` |
| `/etc/nginx/sites-available/nsusosed.ru` | host nginx config | `root` |
| Docker volume `nsusosed_pgdata` | the database | Docker |

### The `gh_deploy` user

`gh_deploy` is the account GitHub Actions logs in as. Each lock works on its own; the others don't depend on it:

- **No password, no groups.** It can't log in with a password, and it's not in `sudo`, `docker` or `adm`. Being in `docker` would be root in disguise (`docker run -v /:/host …`).
- **Its key is in a root-owned file**, `/etc/ssh/authorized_keys/gh_deploy`, so it can't add keys of its own. The key is prefixed with `restrict`.
- **sshd `Match` block:** public key only, no terminal, no forwarding of any kind, no tunnels, no `~/.ssh/rc`.
- **`ForceCommand` gate:** whatever command the client asks for, sshd runs [`gh-deploy-gate`](gh-deploy-gate) instead. The gate allows only what the workflow runs:
  - `true`;
  - `cat` of the three hand-installed files;
  - the two rsync uploads into its own folders;
  - `sudo nsusosed-redeploy`.

  Anything else is refused and logged.
- **sudo:** exactly one command, `/usr/local/bin/nsusosed-redeploy`, with no arguments.
- **Files:** it owns `/var/www/nsusosed.ru` and `/opt/nsusosed/app`, and nothing else.

So if the GitHub key leaks, the attacker can change what the site serves and restart the stack, and that's it. They can't:

- get a shell;
- read the secrets;
- download files;
- edit the compose file or any of the scripts;
- become root.

Why these folders? The Linux convention (FHS) is that `/opt/<name>` holds a self-contained app that didn't come from the package manager, `/var/www` holds what a web server serves, and `/etc` holds config. `/srv/<name>` is also common. Any of them works; the point is one predictable place per kind of thing, outside anyone's home directory.

## One-time server setup

Run these on the VPS as your normal sudo user, from a folder holding a copy of this repo's `deploy/` directory (`scp -r deploy HOST:` from your laptop, or paste the files into `nano`). `HOST` means your server's IP or hostname.

### 0. DNS

`nsusosed.ru` and `www.nsusosed.ru` need A records pointing at the VPS (plus AAAA records if it has IPv6). Check from your laptop: `dig +short nsusosed.ru`.

If you don't want `www`, delete the `www.nsusosed.ru` server block from the nginx config, drop it from `server_name` in the port-80 block, and leave out `-d www.nsusosed.ru` in step 7.

### 1. Docker and packages

You need Docker Engine with the compose plugin, from Docker's own apt repo (<https://docs.docker.com/engine/install/>), not the distro's `docker.io` package.

```bash
docker version --format '{{.Server.Version}}'   # want 28.0 or newer, see below
docker compose version                           # want v2.20 or newer
sudo apt install -y rsync curl certbot python3-certbot-nginx
```

Why Docker 28+: before 28.0, a port published on `127.0.0.1` could still be reached by other machines on the same local network segment as the VPS (Docker turned on `route_localnet`). 28.0 blocks that.

### 2. User and folders

```bash
sudo useradd --create-home --user-group --shell /bin/sh gh_deploy
sudo usermod -p '*' gh_deploy          # no password; key login still works
sudo chmod 700 /home/gh_deploy

sudo install -d -o gh_deploy -g gh_deploy -m 755 /var/www/nsusosed.ru
sudo install -d -o root      -g root      -m 755 /opt/nsusosed
sudo install -d -o gh_deploy -g gh_deploy -m 755 /opt/nsusosed/app
```

A few details:

- **The shell has to be a real one (`/bin/sh`).** sshd runs `ForceCommand` through the user's shell, so with `nologin` every command would fail, the gate included.
- **Use `*`, not `!`.** `*` means "no password can ever match". `!` means "account locked", and depending on the sshd/PAM setup that can block key logins too.
- **`AllowUsers` / `AllowGroups`:** if `/etc/ssh/sshd_config` has either line, add `gh_deploy` to it.

### 3. SSH key, sshd lockdown, command gate

**The key pair.** It can be made on the VPS itself, as root, so the private key is never readable by anyone else and never leaves the box except into GitHub:

```bash
sudo ssh-keygen -t ed25519 -N "" -C "github-actions@nsusosed.ru" -f /root/gh_deploy_key
```

That makes two files:

- `/root/gh_deploy_key.pub` is the **public** key. It goes into the authorized-keys file below.
- `/root/gh_deploy_key` is the **private** key. It goes into a GitHub secret (step 4), and is deleted from the VPS after that.

**The authorized key**, in a root-owned file, with `restrict` in front:

```bash
sudo install -d -o root -g root -m 755 /etc/ssh/authorized_keys
printf 'restrict %s\n' "$(sudo cat /root/gh_deploy_key.pub)" \
  | sudo tee /etc/ssh/authorized_keys/gh_deploy
sudo chmod 644 /etc/ssh/authorized_keys/gh_deploy
```

**The gate and the sshd `Match` block:**

```bash
sudo install -m 755 -o root -g root gh-deploy-gate /usr/local/bin/gh-deploy-gate
sudo install -m 644 -o root -g root sshd/gh_deploy.conf /etc/ssh/sshd_config.d/gh_deploy.conf
sudo sshd -t && sudo systemctl reload ssh
```

Check that the `Match` block applies to `gh_deploy` and *only* to `gh_deploy`:

```bash
sudo sshd -T -C user=gh_deploy,host=x,addr=192.0.2.1 | grep -Ei 'forcecommand|authorizedkeysfile|permittty'
sudo sshd -T -C user=root,host=x,addr=192.0.2.1      | grep -i forcecommand     # must say "none"
```

The second line guards a known trap. A `Match` block runs until the next `Match` or the end of the config. Ubuntu's `sshd_config` pulls in `sshd_config.d/*.conf` at its very top, so if your OpenSSH let the block run on past its own file, it would swallow the rest of the main config. If the root line shows the gate, stop and ask before going on.

**Test the login** on the VPS, before deleting the private key:

```bash
sudo ssh -i /root/gh_deploy_key -o StrictHostKeyChecking=accept-new gh_deploy@localhost true && echo ok
sudo ssh -i /root/gh_deploy_key gh_deploy@localhost id          # → gh-deploy-gate: refused
sudo journalctl -t gh-deploy-gate -n 5                          # shows the refused "id"
```

(If sshd doesn't listen on localhost, use the server's address instead.)

**The host key** for `SSH_KNOWN_HOSTS`, built from the server's own key file:

```bash
echo "HOST $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"          # SSH on port 22
echo "[HOST]:2222 $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"   # SSH on another port
```

`HOST` has to be written exactly as in the `SSH_HOST` secret: the same IP, or the same hostname.

### 4. GitHub secrets

Go to **github.com/LessVegetables/nsusosed.ru → Settings → Secrets and variables → Actions → New repository secret** (direct link: <https://github.com/LessVegetables/nsusosed.ru/settings/secrets/actions>). Add:

| Name | Value |
|---|---|
| `SSH_PRIVATE_KEY` | the whole output of `sudo cat /root/gh_deploy_key`, including the `-----BEGIN…` and `-----END…` lines |
| `SSH_KNOWN_HOSTS` | the line from step 3: `<SSH_HOST value> ssh-ed25519 AAAA…` (or `[host]:port …`) |
| `SSH_HOST` | the VPS IP or hostname |
| `SSH_USER` | `gh_deploy` |
| `SSH_PORT` | only if SSH isn't on 22 |

Watch out: **Settings → Deploy keys** is a different thing, for the opposite direction (a server pulling code *from* GitHub). This setup doesn't use it. Here GitHub pushes files *to* the server, so the private key goes in a secret and the public key in the server's authorized-keys file.

Once `SSH_PRIVATE_KEY` is saved, delete the private key from the VPS. GitHub never shows a secret again, so if you ever need the key back, make a new pair.

```bash
sudo shred -u /root/gh_deploy_key
```

If the key ever leaks: empty `/etc/ssh/authorized_keys/gh_deploy`, make a new pair as above, and replace the secret.

### 5. Secrets file

```bash
openssl rand -hex 24                       # use this as POSTGRES_PASSWORD
sudo install -m 600 -o root -g root /dev/null /etc/nsusosed.env
sudo nano /etc/nsusosed.env                # fill in from nsusosed.env.example
```

You don't create the database by hand. The Postgres container creates the user and the database from `POSTGRES_*` the first time it starts with an empty volume, and the api container creates the tables (`alembic upgrade head`) every time it starts.

### 6. Compose file, redeploy script, sudo rule

```bash
sudo install -m 644 -o root -g root compose.yaml /opt/nsusosed/compose.yaml
sudo install -m 755 -o root -g root nsusosed-redeploy /usr/local/bin/nsusosed-redeploy

# compose.yaml fills in ${POSTGRES_*} from the env file. The redeploy script
# passes --env-file explicitly; this link makes plain "sudo docker compose …"
# in /opt/nsusosed find it too (compose reads .env next to compose.yaml).
sudo ln -s /etc/nsusosed.env /opt/nsusosed/.env

sudo visudo -f /etc/sudoers.d/nsusosed-deploy    # paste sudoers/nsusosed-deploy; visudo checks it
sudo -l -U gh_deploy                              # should list the one command
```

The workflow prints a yellow warning when the server's copy of one of these files is out of date. When that happens, repeat its `install` line:

- `compose.yaml`
- `nsusosed-redeploy`
- `gh-deploy-gate`

Port 1231 has to be free: `sudo ss -ltnp | grep 1231` should print nothing. If you ever change the port, change it in `compose.yaml`, `nsusosed-redeploy` and the nginx `upstream`.

### 7. Certificate and nginx

Get the certificate first, because the nginx config refers to it:

```bash
sudo certbot certonly --nginx -d nsusosed.ru -d www.nsusosed.ru
```

Then install the config:

```bash
sudo cp nginx/nsusosed.ru.conf /etc/nginx/sites-available/nsusosed.ru
sudo ln -s ../sites-available/nsusosed.ru /etc/nginx/sites-enabled/nsusosed.ru
nginx -v                  # older than 1.25.1? see the comment at "http2 on;"
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` fails if:

- **`/etc/letsencrypt/options-ssl-nginx.conf` is missing.** It's normally created the first time certbot's nginx plugin runs. If it isn't there, replace the `include` lines with `ssl_protocols TLSv1.2 TLSv1.3;`.
- **The server has no IPv6.** Delete the `listen [::]:…` lines.

Renewal is automatic (`systemctl list-timers | grep certbot`).

### 8. First deploy

Push the `deploy` branch (`git push -u origin deploy`). Watch it on the repo's **Actions** tab. Then check on the VPS:

```bash
cd /opt/nsusosed && sudo docker compose ps
sudo docker compose -f /opt/nsusosed/compose.yaml logs --tail 50 api
curl -s http://127.0.0.1:1231/health
sudo ss -ltnp | grep docker      # only 127.0.0.1:1231
```

If a workflow step fails with `gh-deploy-gate: refused`, run `sudo journalctl -t gh-deploy-gate -n 20`. It shows the exact command the gate turned down.

## Day to day

- **Deploy:** merge into `deploy` and push, or open a PR into `deploy` and merge it. To re-run without a new commit, use Actions → Deploy → **Run workflow**.
- **Roll back:** `git revert` the bad commit on `deploy` and push. Nothing on the server keeps old releases.
- **Change a setting or secret:** `sudo nano /etc/nsusosed.env && sudo nsusosed-redeploy`. The workflow never touches this file.
- **Logs:**
  - API: `cd /opt/nsusosed && sudo docker compose logs -f api`.
  - nginx: `/var/log/nginx/nsusosed.ru.{access,error}.log`.
  - Refused deploy commands: `sudo journalctl -t gh-deploy-gate`.
- **Database shell:** `cd /opt/nsusosed && sudo docker compose exec db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'`.
- **Backup:** `cd /opt/nsusosed && sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > ~/nsusosed-$(date +%F).sql.gz`. Nothing does this automatically yet.

If a `docker compose` command complains that `POSTGRES_USER` "is not set", it couldn't find the env file: check the `/opt/nsusosed/.env` link from step 6. Plain `docker` commands (`sudo docker logs nsusosed-api-1`, `sudo docker ps`) don't need it.

Careful with `docker compose down -v`: the `-v` deletes the database volume. A plain `down` (or `stop`) is safe.

## What the workflow does

Every remote command below has a matching case in `gh-deploy-gate`. A new remote command in the workflow needs one too, or it gets refused.

1. Checks that `frontend/` and `backend/` exist and that the i18n keys match, then test-builds the API image on GitHub's runner.
2. Connects (`ssh vps true`).
3. Warns if the server's copies of `compose.yaml`, `nsusosed-redeploy` or `gh-deploy-gate` differ from the repo (`cat <file>`).
4. rsyncs `frontend/` into `/var/www/nsusosed.ru/`. It leaves out `tools/`, `dev_server.py`, `README.md` and `js/mock/`, and deletes files that are gone from the repo.
5. rsyncs `backend/` into `/opt/nsusosed/app/`, leaving out tests and any `.env`.
6. Runs `sudo /usr/local/bin/nsusosed-redeploy`, which:
   - rebuilds the image;
   - runs `docker compose up --wait` (migrations run on container start);
   - waits for both healthchecks;
   - prints the API logs if something fails.
7. Checks `https://nsusosed.ru/` and `/api/health` from outside.
