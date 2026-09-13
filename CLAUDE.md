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

## Adding a scalar field: `optional` is a decision, not a formality

A proto3 scalar without `optional` has **implicit presence** — it reads back as its zero value whether the caller set it or not, and `HasField` raises on it. So the moment a new field means "if you say nothing, the server keeps doing what it was doing", the field needs `optional`. Without it there is no wire-level way to tell "the caller expressed no preference" from "the caller sent the default", and the server has to guess.

`AsteriskConfigs.asterisk_version` is the worked example. Unset means "use the deployment's `ONDEWO_VTSI_ASTERISK_IMAGE_TAG`"; an empty string cannot form a usable docker image reference and is rejected. Both would read back as `""` on a plain scalar.

Two consequences worth knowing before adding one:

- **`optional` compiles to a synthetic one-member oneof** named `_<field>`. It shows up in the generated `WhichOneof` overloads and in `DESCRIPTOR.oneofs`, next to any real oneof in the same message. It does not join the real one — `WhichOneof("asterisk_configs_oneof")` is unaffected in both directions — but a descriptor walk that assumes one oneof per message will now see two.
- **The clients are not equivalent.** python and the jspb clients (js / nodejs / typescript) expose real presence (`HasField` / `hasX()`); **ngx-grpc flattens it** into a plain string that is written to the wire only when truthy, so an Angular caller cannot send the empty value at all. If a field genuinely needs the third state from Angular, that has to be designed for rather than discovered after release.

## Jenkins — never trigger a multibranch scan or branch indexing

**NEVER trigger a Jenkins multibranch scan or branch indexing.** Do not call a multibranch/folder job's
`build`, `scan`, or reindex endpoints, click "Scan Repository Now" / "Build Now" on a folder, run
`p4 scan`, or use any API/CLI that reindexes branches or scans the repository. A scan/reindex runs across
**every** branch, consumes CI resources, and can kick off unintended builds and deploys.

If a branch is not building — it was not discovered, or its job is marked `buildable: false` / orphaned —
**report it and stop**. Let the user or a Jenkins admin adjust branch-discovery/config or rename the branch
to the convention. Never force a build by scanning or reindexing.

## Releasing: preflight and the traps that have actually bitten

Written after a release program across every ONDEWO client in one session. Each item below
cost real time or a broken artefact; every statement is derived from THIS repo's Makefile.

### Before you touch the version, check the released tag is in `master`

Releases here are cut from a `release/<version>` branch and are **not always merged back**, so
`master` can be missing work that is already published — and because a later version number
sorts above the unmerged one, a consumer upgrading silently loses it. The ondewo-nlu-client-python
7.1.0 release was exactly this: it shipped from a `master` that had never seen 7.0.5's
offline-token hand-off, so PyPI's newest release was a regression against its predecessor.

```bash
latest=$(git tag --sort=-v:refname | head -1)
git merge-base --is-ancestor "$latest" master && echo "in master" || echo "NOT in master -- merge first"
```

A fast-forward (`git merge --ff-only <tag>`) is the common case. A true merge needs care: resolve
metadata toward `master` and keep BOTH release-note sections, newest first — a reader upgrading
from the older line still needs the older entry.

### `git add` on a dirty submodule stages the WRONG commit

This repo has submodules (`ondewo-nlu-api`, `ondewo-s2t-api`, `ondewo-sip-api`, `ondewo-t2s-api`). If a submodule's working
tree is dirty, `git add <submodule>` stages **its current HEAD**, not the pointer you resolved
during a merge — silently regressing it to an older commit. `git checkout master -- <submodule>`
fixes the index but the next `git add` re-breaks it. Move the working tree instead:

```bash
want=$(git ls-tree master <submodule> | awk '{print $3}')
git -C <submodule> checkout -q "$want" && git add <submodule>
```

### The release notes are sliced by an EXACTLY-CASED heading

`CURRENT_RELEASE_NOTES` slices `RELEASE.md` with a perl range. In THIS repo the opening
pattern is, verbatim:

```text
Release ONDEWO VTSI API ${ONDEWO_VTSI_API_VERSION}
```

So the heading of a new entry must read exactly `## Release ONDEWO VTSI API <version>`. **This wording is
not consistent across the ONDEWO repos** — some say `... <Name> Client`, some `... Client
<Name>` with the words reversed, the API repos say `... API` with no `Client` at all, and the
casing varies (`Js`, `Nodejs`, `Typescript`, `Survey`). Do not carry a heading over from a
sibling repo. Copy the PREVIOUS entry in this file and change only the version, or read the
pattern above out of the Makefile.

A heading that does not match yields an **empty slice**, and the GitHub release is then
created with empty notes or fails outright. Verify before releasing:

```bash
grep -c '^## Release ONDEWO VTSI API ' RELEASE.md     # must be >= 1 for your new version
```

### Where the release notes live

This repo does NOT regenerate the root `RELEASE.md` from `src/`, so the root file is the one
the release reads. Keep `src/RELEASE.md` in step by hand if it exists.

### Publish order decides how a partial failure is recovered

`make release` in this repo runs:


The **npm publish happens LAST**. So a failure before it means nothing shipped, but the
branch, tag and GitHub release may already exist — and `spc` will then refuse a re-run. Recover
by running only the remaining step, not the whole target.

### Verify against the registry, with the REAL package name

This package publishes as **`<see package.json name>`**, which is not always the repository name — the JS client
publishes as `@ondewo/ondewo-nlu-client-js` (doubled `ondewo`), so a lookup by repo name returns
a 404 that reads like a failed release. Check the name in the manifest first, then:

```bash
npm view <see package.json name> versions --json
```

**An npm publish can be STAGED but not yet served.** Immediately after a publish the registry may
answer 404 for the new version while refusing a re-publish with
`409 Cannot publish over previously staged version`. That is not a failure and the version is
not burned — wait and re-check before bumping to a new number.

### The release prints credentials — read the log BEFORE you scrub it

`make ondewo_release` clones `ondewo-devops-accounts` and passes the registry and GitHub tokens on
the make command line, so they are echoed into the console and into any transcript capturing it.
This is a known and accepted property of the shared release path: do **not** re-plumb the recipe.
Redirect the run to a file, read it through a filter, and shred the file afterwards — and read it
**before** shredding, or a genuine failure is lost with the secrets:

```bash
umask 077; make ondewo_release > /tmp/rel.log 2>&1; echo "RC=$?"
grep -avE 'TOKEN|PASSWORD|USERNAME|_authToken' /tmp/rel.log | tail -20   # read FIRST
shred -u /tmp/rel.log; rm -rf ondewo-devops-accounts                     # then scrub
```

### Run the release from `master`, and check with `git branch --show-current`

A release ends by checking out `release/<version>`, and **nothing checks you out back**. Start the
next release from that leftover checkout and `git commit` + `git push` land on the OLD release
branch: the new `release/<version>` is cut from it, the tag points into it, and `master` never sees
the release at all. Measured on ondewo-csi-client-typescript 5.5.1 -- npm had it, the tag had it,
and `origin/master` was still at 5.5.0. Recovery was a fast-forward (`git merge --ff-only
release/5.5.1`), which worked only because nothing else had moved; a diverged `master` needs a real
merge.

```bash
git branch --show-current            # must print master BEFORE `make ondewo_release`
```

### The release `git add` list is an ALLOW-LIST, so anything outside it ships but is never committed

`make build` writes files the release target then stages from a fixed list of paths. Anything the
build touches that is not on that list reaches the registry and is **absent from the tag of that
same version** -- two different things under one name, with nothing anywhere reporting it.

Both directions have bitten: a hand-written directory the build copies into the package, and a
tracked file the build regenerates. Whatever `make build` writes, either stage it or prove the
release does not need it.

The general check costs nothing:

```bash
git status --porcelain    # MUST be empty after a release; anything left is published-but-uncommitted
```

### Write the RELEASE.md section BEFORE releasing, or the release body is silently empty

`CURRENT_RELEASE_NOTES` slices RELEASE.md between the heading naming this exact version and the next
`*****` separator. No heading means an EMPTY slice, `gh release create -n ""` succeeds, and you get a
release with no notes and no error anywhere. ondewo-nlu-client-js and -typescript 7.1.1 shipped that
way and had to be repaired after the fact.

```bash
cat RELEASE.md | perl -ne 'print if /<the exact heading> <version>/../^\*{5}/' | wc -l   # must be > 0
```

### Verify the three artefacts separately -- they fail independently

GitHub's release API returned 500 twice in one session, leaving the registry and the tag correct and
**no release object at all** (nlu-client-js and -angular 7.1.1); `gh release create` after the fact
repairs it without touching the artefact.


```bash
git tag --list <version> ; gh release view <version> --json body --jq '.body|length'
```
