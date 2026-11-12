# Contributing

Thanks for helping. This page covers the setup, the checks to run, and the few rules the code follows. [docs/architecture.md](docs/architecture.md) explains how the parts fit together.

## Set up

You need Python 3.11 or newer and `ffmpeg` on your PATH (the video tests render short clips).

```sh
git clone https://github.com/mertkayacs/postkitty
cd postkitty
python -m venv .venv
. .venv/bin/activate
python -m pip install ruamel.yaml pytest ruff hypothesis
python -c "from ruamel.yaml import YAML; print('\n'.join(YAML(typ='safe').load(open('plugin.yaml'))['python_dependencies']))" > .venv/requirements.txt
python -m pip install -r .venv/requirements.txt
```

The runtime packages are declared in `plugin.yaml` and again in `pyproject.toml`, and a test keeps the two lists identical. The third command reads them from `plugin.yaml`.

## Run the checks

```sh
python -m pytest -q
ruff check .
```

The tests build their own photos and clips and use a stand-in face detector, so they download nothing. Tests marked `real_detector` run the real detector and are left to CI.

To check the plugin the way Hermes does, use a scratch Hermes home so your own setup stays untouched:

```sh
HERMES_HOME="$(mktemp -d)" hermes plugins validate . --install-deps
```

## Rules the code follows

- **A bug fix starts with a failing test.** Write the test that shows the bug, then fix it, then run the whole suite. One commit per fix.
- **Each test pins something a user would notice.** A test with no such reason does not belong.
- **The engine stays a plain library.** Hermes imports belong in `__init__.py`, `tools.py` and `command.py`.
- **Limits live in `data/platforms.yaml`.** Every number carries the page it came from and the date it was checked. No limit goes into code.
- **Handlers never raise.** A tool returns JSON, and an error is one plain sentence with a hint that says what to do next.
- **Keep it small.** The least code that solves the problem, no options nobody asked for.

## Commits and pull requests

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) with a scope, an imperative subject in lower case after the colon, and no full stop:

```text
fix(video): keep the cover frame inside the trim
```

Keep a pull request to one topic, and say in it what you ran and what you saw.

## Add a platform

The steps are in [docs/architecture.md](docs/architecture.md#platform-data-and-how-to-add-a-platform). In short: add the platform to `data/platforms.yaml` with a source for every limit, run `python docs/build_platforms.py` to rebuild [docs/platforms.md](docs/platforms.md), and run the tests.

## Releases and the Hermes catalog

The Hermes plugin catalog pins one commit of this repository. `.github/catalog-entry.yaml` is that entry, with `__COMMIT__` where the pin goes, and the consistency check keeps its version and tool list in step with `plugin.yaml`.

The `catalog-gate` workflow runs Hermes' own admission checks from their repository on every change to the plugin: it fills in the entry for that commit and checks it against Hermes' main branch. A pin update is a pull request on NousResearch/hermes-agent that carries the filled-in entry. Their checks start only after a maintainer approves them, so run the workflow by hand with the pull request's number first. It then checks that pull request's merge commit the way their CI will: the catalog gate, the catalog tests and the repository guards.

After the pull request merges, Hermes publishes the new pin with its next site build. When `https://hermes-agent.nousresearch.com/docs/api/plugin-catalog.json` carries the new commit, run the `first-run` workflow by hand with `install` set to `catalog`. It runs the README command on a clean machine and checks that Hermes installed the pinned version.

## Report a security problem

Please follow [SECURITY.md](SECURITY.md) and keep the details out of public issues.
