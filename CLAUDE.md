# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Principles

Behavioral guidelines to reduce common mistakes. They bias toward caution over speed; for trivial tasks, use judgment.

### Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### Surgical changes

Touch only what you must. Clean up only your own mess.

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that _your_ changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### Goal-driven execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```text
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and
clarifying questions come before implementation rather than after mistakes.

## Logging

```python
from loguru import logger as log
```

- **Levels:** `log.trace()`, `log.debug()`, `log.info()`, `log.warning()`, `log.error()`, `log.exception()`. Choose by
  hotness/verbosity — `trace` for per-token / hot-path detail, `debug` for routine method entry/exit, `info` for notable
  lifecycle events, `warning` / `error` / `exception` for problems.
- **Interpolate with f-strings, not loguru's `{}` positional args.** Consistent with the Code Style rule, use
  `f"…{value}"`; only add the `f` prefix when the string actually interpolates (`"START: …"` with no params stays a
  plain string).
- **`START:` / `DONE:` bracketing.** Wrap a method (or other notable operation) with a `START:` line at entry and a
  `DONE:` line at exit, both naming `ClassName: method_name` (append `: param={value}` context where useful):

  ```python
  log.debug("START: IntentBertClassifier: predict")
  ...
  log.debug(f"DONE: IntentBertClassifier: predict. Elapsed time: {perf_counter() - start_time:.5f}")
  ```

- **Timing uses `perf_counter()`, rendered `:.5f`.** Measure elapsed time with `time.perf_counter()` captured as a start
  value and subtracted at the `DONE:` line; always format the elapsed value with the `:.5f` spec:

  ```python
  from time import perf_counter

  start_time: float = perf_counter()
  ...
  log.info(f"DONE: SESSION SERVICER: DetectIntent. Elapsed time: {perf_counter() - start_time:.5f}")
  ```

  Never measure a duration with `time.time()` — reserve `time.time()` for wall-clock timestamps (epoch seconds persisted
  to a DB / proto, unique-id or filename stamps). `perf_counter()` has an undefined epoch and must not be stored or
  compared across processes.

## Docstrings

Google-style, triple double-quotes:

```python
"""
Short imperative summary line.

Args:
    param_name (type):
        Description of the parameter.

Returns:
    type:
        Description of the return value.

Raises:
    ExceptionType:
        When this exception is raised.
"""
```

## Git Commits

- **Never include Claude as author or co-author** in commit messages, PR descriptions, or any other text. Do not add
  `Co-Authored-By: Claude…` trailers, "Generated with Claude Code" footers, or any similar attribution.
- The user's own git author identity (already configured in git) is the only identity that should appear on commits.
- This rule overrides the default Claude Code commit-template guidance.
- **Never prepend the JIRA ticket ID** (e.g. `[OND211-2386]`) to the commit subject yourself. The `giticket` pre-commit
  hook reads the ticket from the branch name (`(feature|bugfix|support|hotfix)/<TICKET>-…`) and prepends `[<ticket>]`
  (with a trailing space) automatically. Writing the prefix manually produces a duplicate like
  `[OND211-2386] [OND211-2386] feat: …`. Write the subject as plain Conventional Commits (`feat: …`, `fix(scope): …`,
  `docs(types): …`) and let the hook add the prefix on commit.

## General Principles

- Follow existing patterns before introducing new abstractions.
- Keep changes minimal and consistent with surrounding code.
- Validate inputs early with descriptive, context-rich error messages.
- Use context managers for files, sockets, and thread pools.
- Prefer region comments for grouping methods in files that already use them.
- End edited Markdown and YAML files with a trailing newline.

## Client-release orchestration (`release_all_clients`)

- It **fails loudly** on a genuine client-release error: the piped sub-make runs under `bash -c 'set -o pipefail; make -C … | tee …'` (a plain sh pipe returns tee's 0 and masks failures), and a **marker file** distinguishes an "already released" SKIP from a real FAILURE (make flattens recipe exit codes to 2, so the code alone can't tell them apart). Do not regress either.
- Every token-bearing recipe line is `@`-prefixed so make never echoes a secret — `docker run -e <TOKEN>`, `echo $(TOKEN) | gh auth`, `twine … -p${PYPI_PASSWORD}`, and the credential sub-make `make release $(info)` (which expands the token at runtime and is easy to miss).

## Pre-commit upgraded (language-agnostic hook set)

Pre-commit here uses only the language-agnostic hooks — **markdownlint-cli2, pre-commit-hooks hygiene, giticket, conventional-pre-commit** — no ruff/mypy/uv (there is no Python). Generated docs (`docs/`) and any generated code are excluded via the top-level `exclude:`.

- **markdownlint MD053 is disabled** (its auto-fix deletes `[comment]: <>` reference-definition markers).
- **markdownlint RELEASE.md reformatting is content-safe**: it only strips trailing whitespace and adds blank lines around headings — the `## Release … <VERSION>` headings and `*****` separators that `ondewo_release` greps for remain intact. (Confirmed: the 6.5.0 release notes sliced correctly after the reformat.)

## GitHub Actions — `Generate API Documentation` is a required gate

`.github/workflows/generate-doc-and-deploy.yaml` is the only workflow in this repo, and it is a **required gate,
not advisory**: it runs on every push and pull request against `master` (plus `workflow_dispatch`), and its last
step publishes `docs/` to GitHub Pages. A red run means the published API documentation silently stops updating.

The `generate-doc-and-deploy` job (`ubuntu-latest`) has three author-written steps; the runner wraps them in
`Set up job`, `Build ondewo/ondewo-protoc-gen-doc-action@master`, `Post Checkout 🛎️` and `Complete job`:

1. **Checkout 🛎️** — `actions/checkout@v5` with `submodules: true`.
2. **Generate documentation from ONDEWO proto files 🔧** — `ondewo/ondewo-protoc-gen-doc-action@master`.
3. **Deploy 🚀** — `JamesIves/github-pages-deploy-action@v4`, guarded by `if: ${{ !env.ACT }}`, deploying folder
   `docs` to target folder `docs` on branch `master`.

### Reproducing it locally

```bash
make build_docs           # the whole gate; `make clean_docs_builder` drops the checkout + image
```

Use that target rather than hand-rolling a `protoc` line. It clones the action into `.tmp-protoc-gen-doc-action/`
(gitignored), builds the action's own `Dockerfile`, and runs the resulting image with the same `html,md index`
arguments `action.yaml` passes — so it exercises the CI tool itself, not an approximation of it. It requires
**Docker and network access**; there is no offline path. Step 3 cannot be run locally and must not be: it pushes
to `master`.

To read the real verdict for the current commit instead of guessing:

```bash
SHA=$(git rev-parse HEAD)
curl -s "https://api.github.com/repos/ondewo/ondewo-vtsi-api/actions/runs?head_sha=$SHA" \
  | grep -E '"(status|conclusion)"'
```

There is deliberately **no `uv` / `ruff` / `mypy` / `pytest` step to mirror**: this repo contains zero Python
files (`git ls-files '*.py'` is empty), which is why `.pre-commit-config.yaml` carries only language-agnostic
hooks. The `mypy` and `install_python_requirements` targets still sitting in the `Makefile` are vestigial —
`mypy` even calls `pre-commit run mypy`, a hook id this repo does not define — and are wired into no gate.

### What is sharp about it

- **The action is pinned to `@master`, so the toolchain floats.** There is no lockfile here and nothing to
  `--frozen`, so the protection a frozen install buys elsewhere does not exist: both
  `ondewo/ondewo-protoc-gen-doc-action` and its `FROM pseudomuto/protoc-gen-doc` base can move underneath you.
  A green run yesterday is not evidence about today — re-run `make build_docs` rather than trusting the last
  run's colour.
- **Nothing ever compares the committed `docs/` with what the action generates.** The workflow regenerates and
  deploys; it never diffs. Stale committed docs therefore cannot turn a run red — the drift is invisible to CI
  by construction, and a clean `make build_docs` followed by `git diff docs/` is the only thing that detects it.
  Live example at `5a32ca1`: the committed `docs/index.html` differs from a fresh build by 21 lines, because
  that commit added 30 trailing-whitespace lines to `ondewo/s2t/speech-to-text.proto` without regenerating.
- **Only `index.html` drifts that way.** `html.tmpl` copies proto comment text verbatim, trailing whitespace and
  line breaks included, while `md.tmpl` folds each comment into one table cell so per-line trailing spaces
  vanish. Expect an HTML-only diff from a whitespace-only proto edit, and do not read it as corruption.
- **`submodules: true` does not feed the documentation.** The action's `entrypoint.sh` globs
  `find ondewo -name '*.proto'` — only the self-contained top-level `ondewo/` tree (25 protos). Building from a
  tree with all four `ondewo-*-api` submodule directories completely empty yields byte-identical `index.html`,
  `index.md` and `style.css`. A drifted or uninitialised submodule can therefore never explain a docs diff; look
  at `ondewo/**/*.proto` instead.
- **Two warning classes are expected and are not failures.** `googleapis: warning: directory does not exist.`
  (the entrypoint passes `-Igoogleapis`, which this repo does not have — the vendored `google/` tree resolves
  through `-I.`) and the `Import ... is unused` lines for `ondewo/vtsi/calls.proto` and `ondewo/vtsi/projects.proto`.
  `protoc` still exits 0; do not chase them.
- **`make build_docs` writes into the working tree.** It overwrites `docs/` in place, so run it from a clean
  tree and then either commit the refresh deliberately or `git checkout -- docs/`. Note that `docs/**` is
  excluded from both markdownlint and pre-commit, so nothing will normalise what it emits.

## Jenkins — never trigger a multibranch scan or branch indexing

**NEVER trigger a Jenkins multibranch scan or branch indexing.** Do not call a multibranch/folder job's
`build`, `scan`, or reindex endpoints, click "Scan Repository Now" / "Build Now" on a folder, run
`p4 scan`, or use any API/CLI that reindexes branches or scans the repository. A scan/reindex runs across
**every** branch, consumes CI resources, and can kick off unintended builds and deploys.

If a branch is not building — it was not discovered, or its job is marked `buildable: false` / orphaned —
**report it and stop**. Let the user or a Jenkins admin adjust branch-discovery/config or rename the branch
to the convention. Never force a build by scanning or reindexing.
