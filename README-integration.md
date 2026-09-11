# Adding Docker + CI/CD to MarketPulse

## Files to drop in

Copy these into the repo root (the same level as your existing
`requirements.txt` and `app/` folder):

- `Dockerfile`
- `.dockerignore`
- `docker-compose.yml`

And this one into `.github/workflows/` (create the folder if it doesn't exist):

- `ci.yml`

## Before you commit — two things to check

1. **`docker-compose.yml`'s volume line** assumes your SQLite file is named
   `marketpulse.db`. Open `db.py` (or wherever the DB filename is set) and
   fix the left-hand side of the volume mapping if it's named differently —
   otherwise your data won't persist across `docker compose down`/`up`.
2. **`ci.yml`'s test command** assumes `python -m unittest discover -s tests -v`
   is how your test suite actually runs. If you use pytest instead, or your
   tests live somewhere other than `tests/`, update that line.

## Testing locally

```
docker compose up --build
```

Then hit `http://localhost:8000/docs` to confirm the FastAPI app came up
inside the container the same way it does when you run uvicorn directly.

## Being upfront about validation

I built this Dockerfile using a standard, well-tested multi-stage pattern
(build stage installs deps, runtime stage copies them in, runs as a
non-root user), but I could not actually run `docker build` end-to-end in
my own sandbox to prove it works — outbound access to Docker Hub is
blocked in this environment, so the base image pull fails before the build
even starts. The Dockerfile and workflow follow patterns I'm confident in,
but you should run `docker compose up --build` yourself before relying on
this for anything real, and fix anything that doesn't match your actual
`app/main.py` entrypoint or dependency list.

## Enabling real CD (optional, not done here)

Right now `ci.yml`'s build job builds the image but doesn't push it
anywhere (`push: false`) — it's just proof the Dockerfile works. To
actually publish images on every merge to `main`, see the commented block
at the bottom of `ci.yml` for the two secrets and two-line change needed.

## Committing

I don't have push access to your repos, so you'll need to add and commit
these yourself:

```
git add Dockerfile .dockerignore docker-compose.yml .github/workflows/ci.yml
git commit -m "Add Docker support and CI/CD pipeline"
git push
```
