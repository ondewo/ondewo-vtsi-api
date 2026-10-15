#!/usr/bin/env python3
"""
Tests for the client-release driver: release_client, preflight_all_clients and release_all_clients.

The behavioural tests run the REAL Makefile and scripts against fake client repositories (local bare
repositories whose Makefile stubs release_preflight / ondewo_release / release_verify) and a fake
ondewo-devops-accounts repository, so nothing is cloned from or published to anywhere. They pin:

- a client is SKIP only when its tag exists AND its release_verify passes; a release branch without a
  tag, or a tag whose release_verify fails, is FAILED - never SKIP;
- every client's release_preflight runs before ANY client releases, and one failing preflight stops all;
- a client that lacks release_preflight / release_verify fails with that message;
- every exit path removes the client clone, the notes file and every devops-accounts clone;
- the proto compiler is the pinned ONDEWO_PROTO_COMPILER_VERSION, and version matches are anchored.

The static tests pin the Makefile, Dockerfile.utils, .dockerignore and the workflows.

Usage: python3 scripts/test_release_driver.py [-v]   (needs git, make and perl; stdlib only)
"""

import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
MAKEFILE: str = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
VERSION: str = "9.1.1"

FAKE_CLIENT_MAKEFILE: str = """\
ONDEWO_VTSI_VERSION=9.0.0
ONDEWO_PROTO_COMPILER_GIT_BRANCH=tags/5.15.5
{api_branch_variable}=tags/9.0.0
# Mentions ONDEWO_VTSI_VERSION= in a recipe; the anchored rewrite must leave this line alone.
CONTROL=$(FAKE_CLIENT_CONTROL_DIR)/{name}
LOG=$(FAKE_CLIENT_CONTROL_DIR)/{name}.log

release_preflight:
\t@echo "preflight ONDEWO_VTSI_VERSION=$(ONDEWO_VTSI_VERSION)" >> $(LOG)
\t@test -f "$$DEVOPS_ACCOUNT_DIR/account_github.env"
\t@! grep -qx fail_preflight $(CONTROL) 2>/dev/null

ondewo_release:
\t@echo "release ONDEWO_VTSI_VERSION=$(ONDEWO_VTSI_VERSION)" >> $(LOG)
\t@env > $(FAKE_CLIENT_CONTROL_DIR)/{name}.env
\t@echo "$$(umask) $$(stat -c %a Makefile)" > $(FAKE_CLIENT_CONTROL_DIR)/{name}.modes
\t@test -f "$$DEVOPS_ACCOUNT_DIR/account_github.env"
\t@cp Makefile $(FAKE_CLIENT_CONTROL_DIR)/{name}.Makefile
\t@cp {release_md} $(FAKE_CLIENT_CONTROL_DIR)/{name}.RELEASE.md
\t@git add -A && git commit -q -m "release $(ONDEWO_VTSI_VERSION)"
\t@git push -q origin HEAD:refs/heads/release/$(ONDEWO_VTSI_VERSION)
\t@! grep -qx fail_after_branch $(CONTROL) 2>/dev/null
\t@if grep -qx hang $(CONTROL) 2>/dev/null; then touch $(FAKE_CLIENT_CONTROL_DIR)/{name}.hanging; sleep 60; fi
\t@git tag -a $(ONDEWO_VTSI_VERSION) -m "release/$(ONDEWO_VTSI_VERSION)" && git push -q origin $(ONDEWO_VTSI_VERSION)

release_verify:
\t@echo "verify" >> $(LOG)
\t@git ls-remote --exit-code origin refs/tags/$(ONDEWO_VTSI_VERSION) > /dev/null
\t@! grep -qx fail_verify $(CONTROL) 2>/dev/null
"""

NO_CONTRACT_MAKEFILE: str = """\
ONDEWO_VTSI_VERSION=9.0.0
ONDEWO_PROTO_COMPILER_GIT_BRANCH=tags/5.15.5
ONDEWO_VTSI_API_GIT_BRANCH=tags/9.0.0

ondewo_release:
\t@echo released > $(FAKE_CLIENT_CONTROL_DIR)/{name}.released

TEST:
\t@echo nothing
"""

RELEASE_MD: str = """\
# Release History

*****************

## Release ONDEWO VTSI {display} Client 9.1.10

### Improvements

* a later patch mentioned only to prove the heading match is anchored

*****************
"""


def generated_notes(display: str, version: str) -> str:
    """
    Return the release notes the driver generates for a client.

    Args:
        display (str):
            The language as the client's RELEASE.md headings spell it.
        version (str):
            The API version.

    Returns:
        str:
            The generated block, byte for byte.
    """
    return (
        f"\n*****************\n\n## Release ONDEWO VTSI {display} Client {version}\n\n### Improvements\n\n"
        f"* Tracking API Version [{version}](https://github.com/ondewo/ondewo-vtsi-api/releases/tag/{version}) "
        "( [Documentation](https://ondewo.github.io/ondewo-vtsi-api/) )\n"
    )


class DriverFixture(unittest.TestCase):
    """A scratch driver checkout, fake clients, a fake devops repository and a private TMPDIR."""

    def setUp(self) -> None:
        self.root: Path = Path(tempfile.mkdtemp(prefix="release-driver-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.driver: Path = self.root / "driver"
        self.origins: Path = self.root / "origins"
        self.control: Path = self.root / "control"
        self.tmpdir: Path = self.root / "tmp"
        for directory in (self.driver, self.origins, self.control, self.tmpdir):
            directory.mkdir()
        shutil.copy(REPO_ROOT / "Makefile", self.driver / "Makefile")
        shutil.copytree(REPO_ROOT / "scripts", self.driver / "scripts")
        gitconfig: Path = self.root / "gitconfig"
        gitconfig.write_text(
            "[user]\n\tname = Release Driver Test\n\temail = test@example.invalid\n"
            "[init]\n\tdefaultBranch = master\n[advice]\n\tdetachedHead = false\n",
            encoding="utf-8",
        )
        self.env: Dict[str, str] = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.root),
            "TMPDIR": str(self.tmpdir),
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
            "FAKE_CLIENT_CONTROL_DIR": str(self.control),
        }
        self.make_bare_repository("ondewo-devops-accounts", {"account_github.env": "GITHUB_GH_TOKEN=fake-token\n"})

    def git(self, *args: str, cwd: Optional[Path] = None) -> str:
        """
        Run git in the fixture environment.

        Args:
            *args (str):
                git arguments.
            cwd (Optional[Path]):
                Working directory.

        Returns:
            str:
                stdout.
        """
        return subprocess.run(
            ["git", *args], cwd=cwd, env=self.env, check=True, capture_output=True, text=True
        ).stdout

    def make_bare_repository(self, name: str, files: Dict[str, str]) -> Path:
        """
        Create origins/<name>.git holding one commit on master with the given files.

        Args:
            name (str):
                Repository name.
            files (Dict[str, str]):
                Relative path -> content.

        Returns:
            Path:
                The bare repository.
        """
        work: Path = self.root / "work" / name
        work.mkdir(parents=True)
        for relative, content in files.items():
            (work / relative).parent.mkdir(parents=True, exist_ok=True)
            (work / relative).write_text(content, encoding="utf-8")
        self.git("init", "-q", cwd=work)
        self.git("add", "-A", cwd=work)
        self.git("commit", "-q", "-m", "initial", cwd=work)
        bare: Path = self.origins / f"{name}.git"
        self.git("clone", "-q", "--bare", str(work), str(bare))
        return bare

    def make_client(self, name: str, display: str, release_md: str = "RELEASE.md", contract: bool = True) -> Path:
        """
        Create a fake ondewo-vtsi-client-<name> origin.

        Args:
            name (str):
                Client name as in CLIENTS.
            display (str):
                Spelling of the language in its RELEASE.md headings.
            release_md (str):
                Where the client keeps its RELEASE.md.
            contract (bool):
                False omits release_preflight and release_verify.

        Returns:
            Path:
                The bare repository.
        """
        api_branch_variable: str = "VTSI_API_GIT_BRANCH" if release_md.startswith("src/") else "ONDEWO_VTSI_API_GIT_BRANCH"
        template: str = FAKE_CLIENT_MAKEFILE if contract else NO_CONTRACT_MAKEFILE
        makefile: str = template.format(name=name, release_md=release_md, api_branch_variable=api_branch_variable)
        return self.make_bare_repository(
            f"ondewo-vtsi-client-{name}", {"Makefile": makefile, release_md: RELEASE_MD.format(display=display)}
        )

    def control_file(self, name: str, *words: str) -> None:
        """
        Make the fake client <name> fail where the words say (fail_preflight, fail_after_branch, fail_verify).

        Args:
            name (str):
                Client name.
            *words (str):
                Failure switches; none clears them.
        """
        (self.control / name).write_text("".join(f"{word}\n" for word in words), encoding="utf-8")

    def run_make(self, *targets: str, clients: Optional[str] = None) -> subprocess.CompletedProcess:
        """
        Run the driver Makefile against the fakes.

        Args:
            *targets (str):
                make targets.
            clients (Optional[str]):
                A CLIENTS override; None keeps the Makefile's list.

        Returns:
            subprocess.CompletedProcess:
                The finished make, output in stdout.
        """
        return subprocess.run(
            [
                "make",
                "--no-print-directory",
                *targets,
                f"ONDEWO_VTSI_API_VERSION={VERSION}",
                *([f"CLIENTS={clients}"] if clients else []),
                f"CLIENT_GIT_URL_PREFIX=file://{self.origins}/ondewo-vtsi-client-",
                f"DEVOPS_ACCOUNT_GIT_URL=file://{self.origins}/ondewo-devops-accounts.git",
            ],
            cwd=self.driver,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
        )

    def origin_refs(self, name: str) -> List[str]:
        """
        Return the ref names of a fake client's origin.

        Args:
            name (str):
                Client name.

        Returns:
            List[str]:
                Ref names.
        """
        output: str = self.git("ls-remote", str(self.origins / f"ondewo-vtsi-client-{name}.git"))
        return [line.split("\t")[1] for line in output.splitlines()]

    def assert_everything_cleaned_up(self, result: subprocess.CompletedProcess) -> None:
        """
        Assert no client clone, notes file, status file or devops clone survived the run.

        Args:
            result (subprocess.CompletedProcess):
                The run, for the failure message.
        """
        leftovers: List[str] = [
            path.name
            for path in self.driver.iterdir()
            if re.match(r"ondewo-vtsi-client-|temp-notes-|\.already_released_marker-|\.client_status-|ondewo-devops", path.name)
        ]
        self.assertEqual(leftovers, [], result.stdout)
        self.assertEqual(sorted(path.name for path in self.tmpdir.iterdir()), [], f"devops clone left in TMPDIR\n{result.stdout}")


class TestReleaseClient(DriverFixture):
    """release_client: release, SKIP, FAILED and cleanup."""

    def test_a_new_release_is_released_verified_and_cleaned_up(self) -> None:
        self.make_client("python", "Python")
        result = self.run_make("release_python_client")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"RELEASED {VERSION}", result.stdout)
        self.assertIn(f"refs/tags/{VERSION}", self.origin_refs("python"))
        log: str = (self.control / "python.log").read_text(encoding="utf-8")
        self.assertEqual(log.split("\n")[:2], [f"release ONDEWO_VTSI_VERSION={VERSION}", "verify"], log)
        self.assert_everything_cleaned_up(result)

    def test_the_client_makefile_is_prepared_with_anchored_rewrites_and_the_pinned_compiler(self) -> None:
        self.make_client("nodejs", "Nodejs", release_md="src/RELEASE.md")
        result = self.run_make("release_nodejs_client")
        self.assertEqual(result.returncode, 0, result.stdout)
        makefile: str = (self.control / "nodejs.Makefile").read_text(encoding="utf-8")
        compiler: str = re.search(r"^ONDEWO_PROTO_COMPILER_VERSION=(\S+)$", MAKEFILE, re.M).group(1)  # type: ignore[union-attr]
        self.assertIn(f"\nONDEWO_PROTO_COMPILER_GIT_BRANCH=tags/{compiler}\n", makefile)
        self.assertIn(f"ONDEWO_VTSI_VERSION={VERSION}\n", makefile)
        self.assertIn(f"\nVTSI_API_GIT_BRANCH=tags/{VERSION}\n", makefile)
        self.assertIn("# Mentions ONDEWO_VTSI_VERSION= in a recipe;", makefile)

    def test_generated_notes_are_inserted_once_and_a_9_1_10_heading_does_not_count_as_9_1_1(self) -> None:
        self.make_client("cpp", "C++")
        result = self.run_make("release_cpp_client")
        self.assertEqual(result.returncode, 0, result.stdout)
        release_md: str = (self.control / "cpp.RELEASE.md").read_text(encoding="utf-8")
        self.assertTrue(release_md.startswith("# Release History\n" + generated_notes("C++", VERSION)), release_md)
        self.assertEqual(release_md.count(f"Client {VERSION}\n"), 1)

    def test_a_curated_entry_for_the_version_is_kept(self) -> None:
        curated: str = f"# Release History\n\n*****************\n\n## Release ONDEWO VTSI Go Client {VERSION}\n\n* curated\n"
        self.make_bare_repository(
            "ondewo-vtsi-client-go",
            {"Makefile": FAKE_CLIENT_MAKEFILE.format(name="go", release_md="RELEASE.md", api_branch_variable="ONDEWO_VTSI_API_GIT_BRANCH"), "RELEASE.md": curated},
        )
        result = self.run_make("release_go_client")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.control / "go.RELEASE.md").read_text(encoding="utf-8"), curated)

    def test_a_released_and_verified_client_is_skip(self) -> None:
        self.make_client("python", "Python")
        self.assertEqual(self.run_make("release_python_client").returncode, 0)
        result = self.run_make("release_all_clients", clients="python")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("python : SKIP", result.stdout)
        self.assertEqual((self.control / "python.log").read_text(encoding="utf-8").count("release "), 1)
        self.assert_everything_cleaned_up(result)

    def test_a_branch_without_a_tag_is_failed_not_skip_and_cleaned_up(self) -> None:
        self.make_client("python", "Python")
        self.control_file("python", "fail_after_branch")
        first = self.run_make("release_python_client")
        self.assertNotEqual(first.returncode, 0, first.stdout)
        self.assertIn(f"refs/heads/release/{VERSION}", self.origin_refs("python"))
        self.assertNotIn(f"refs/tags/{VERSION}", self.origin_refs("python"))
        self.assert_everything_cleaned_up(first)
        self.control_file("python")
        rerun = self.run_make("release_all_clients", clients="python")
        self.assertNotEqual(rerun.returncode, 0, rerun.stdout)
        self.assertIn("HALF-FINISHED", rerun.stdout)
        self.assertNotIn("SKIP", rerun.stdout)
        self.assert_everything_cleaned_up(rerun)

    def test_a_tag_whose_release_verify_fails_is_failed_not_skip(self) -> None:
        self.make_client("python", "Python")
        self.assertEqual(self.run_make("release_python_client").returncode, 0)
        self.control_file("python", "fail_verify")
        result = self.run_make("release_python_client")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("HALF-FINISHED", result.stdout)
        self.assertNotIn("SKIP", result.stdout)
        self.assert_everything_cleaned_up(result)

    def test_a_release_that_fails_verify_right_after_releasing_is_failed(self) -> None:
        self.make_client("python", "Python")
        self.control_file("python", "fail_verify")
        result = self.run_make("release_python_client")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("release_verify fails", result.stdout)
        self.assert_everything_cleaned_up(result)

    def test_other_versions_on_origin_do_not_make_a_skip(self) -> None:
        origin: Path = self.make_client("python", "Python")
        head: str = self.git("rev-parse", "HEAD", cwd=origin).strip()
        for ref in (f"refs/heads/release/1{VERSION}", f"refs/heads/release/{VERSION}0", f"refs/tags/{VERSION}0", f"refs/tags/1{VERSION}"):
            self.git("update-ref", ref, head, cwd=origin)
        result = self.run_make("release_python_client")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"RELEASED {VERSION}", result.stdout)

    def test_relative_tmpdir_and_devops_dir_reach_the_client_as_absolute_paths(self) -> None:
        self.make_client("python", "Python")
        devops: Path = self.driver / "given-devops"
        self.git("clone", "-q", str(self.origins / "ondewo-devops-accounts.git"), str(devops))
        for variable, value in (("TMPDIR", os.path.relpath(self.tmpdir, self.driver)), ("DEVOPS_ACCOUNT_DIR", "./given-devops")):
            with self.subTest(variable=variable):
                self.env[variable] = value
                result = self.run_make("release_python_client")
                del self.env[variable]
                self.env["TMPDIR"] = str(self.tmpdir)
                self.assertEqual(result.returncode, 0, result.stdout)
                given: str = dict(
                    line.split("=", 1) for line in (self.control / "python.env").read_text(encoding="utf-8").splitlines() if "=" in line
                )["DEVOPS_ACCOUNT_DIR"]
                self.assertTrue(os.path.isabs(given), given)
                for ref in self.origin_refs("python"):
                    if VERSION in ref:
                        self.git("update-ref", "-d", ref, cwd=self.origins / "ondewo-vtsi-client-python.git")
        self.assertTrue((devops / "account_github.env").is_file(), "a DEVOPS_ACCOUNT_DIR the driver did not create was deleted")

    def test_an_interrupted_release_still_cleans_up(self) -> None:
        self.make_client("python", "Python")
        self.control_file("python", "hang")
        for interrupt in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(interrupt=interrupt.name):
                process = subprocess.Popen(
                    [
                        "make", "--no-print-directory", "release_python_client", f"ONDEWO_VTSI_API_VERSION={VERSION}",
                        f"CLIENT_GIT_URL_PREFIX=file://{self.origins}/ondewo-vtsi-client-",
                        f"DEVOPS_ACCOUNT_GIT_URL=file://{self.origins}/ondewo-devops-accounts.git",
                    ],
                    cwd=self.driver, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    start_new_session=True,
                )
                hanging: Path = self.control / "python.hanging"
                deadline: float = time.monotonic() + 60
                while not hanging.exists() and time.monotonic() < deadline and process.poll() is None:
                    time.sleep(0.05)
                self.assertTrue(hanging.exists(), "the fake release never started")
                os.killpg(process.pid, interrupt)
                output, _ = process.communicate(timeout=60)
                self.assertNotEqual(process.returncode, 0, output)
                self.assert_everything_cleaned_up(subprocess.CompletedProcess(process.args, process.returncode, output))
                hanging.unlink()
                for ref in self.origin_refs("python"):
                    if VERSION in ref:
                        self.git("update-ref", "-d", ref, cwd=self.origins / "ondewo-vtsi-client-python.git")

    def test_a_client_without_the_contract_targets_fails_with_a_clear_message(self) -> None:
        self.make_client("php", "PHP", contract=False)
        result = self.run_make("release_php_client")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("client php lacks release_preflight", result.stdout)
        self.assertFalse((self.control / "php.released").exists(), "ondewo_release ran without the contract targets")
        self.assert_everything_cleaned_up(result)

    def test_the_client_gets_a_private_devops_dir_and_nothing_of_the_driver_make(self) -> None:
        self.make_client("python", "Python")
        result = self.run_make("release_python_client")
        self.assertEqual(result.returncode, 0, result.stdout)
        env: Dict[str, str] = dict(
            line.split("=", 1) for line in (self.control / "python.env").read_text(encoding="utf-8").splitlines() if "=" in line
        )
        self.assertTrue(os.path.isabs(env["DEVOPS_ACCOUNT_DIR"]), env["DEVOPS_ACCOUNT_DIR"])
        self.assertTrue(env["DEVOPS_ACCOUNT_DIR"].startswith(str(self.tmpdir.resolve())), env["DEVOPS_ACCOUNT_DIR"])
        self.assertNotIn("CLIENT=", env.get("MAKEFLAGS", ""))
        for leaked in (
            "GITHUB_GH_TOKEN", "GENERIC_RELEASE_NOTES", "CURRENT_RELEASE_NOTES", "ONDEWO_VTSI_API_VERSION", "CLIENT",
            "CLIENT_GIT_URL_PREFIX", "DEVOPS_ACCOUNT_GIT_URL",
        ):
            self.assertNotIn(leaked, env, f"{leaked} leaked into the client release")


    def test_the_client_clone_and_make_are_not_under_the_drivers_private_umask(self) -> None:
        # A client builds docker images from its checkout and runs them as the caller's uid; a 0600 checkout
        # made the php proto-compiler entrypoint unreadable there (ondewo-sip 5.5.2). release_all_clients sets umask 077.
        self.make_client("php", "PHP")
        result = self.run_make("release_all_clients", clients="php")
        self.assertEqual(result.returncode, 0, result.stdout)
        client_umask, makefile_mode = (self.control / "php.modes").read_text(encoding="utf-8").split()
        self.assertEqual(client_umask, "0022", result.stdout)
        self.assertEqual(makefile_mode, "644", result.stdout)


class TestDryRun(DriverFixture):
    """`make -n` must not clone credentials or write files: make executes $(MAKE) lines even under -n."""

    def test_a_dry_run_clones_nothing_and_writes_nothing(self) -> None:
        self.make_client("python", "Python")
        before: List[str] = sorted(path.name for path in self.driver.iterdir())
        for target in ("release_all_clients", "preflight_all_clients", "ondewo_release", "release_python_client", "release_client"):
            extra: List[str] = ["CLIENT=python"] if target == "release_client" else []
            result = self.run_make("-n", target, *extra, clients="python")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("Cloning", result.stdout, target)
        self.assertEqual(sorted(path.name for path in self.driver.iterdir()), before)
        self.assertEqual(list(self.tmpdir.iterdir()), [])
        self.assertFalse((self.control / "python.log").exists())


class TestPreflightBeforeAnyRelease(DriverFixture):
    """preflight_all_clients gates release_all_clients."""

    def test_one_failing_preflight_releases_nothing(self) -> None:
        self.make_client("python", "Python")
        self.make_client("nodejs", "Nodejs", release_md="src/RELEASE.md")
        self.control_file("nodejs", "fail_preflight")
        result = self.run_make("release_all_clients", clients="python nodejs")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("PREFLIGHT FAILED for: nodejs", result.stdout)
        for name in ("python", "nodejs"):
            self.assertEqual([ref for ref in self.origin_refs(name) if VERSION in ref], [], name)
            self.assertNotIn("release ", (self.control / f"{name}.log").read_text(encoding="utf-8"))
        self.assert_everything_cleaned_up(result)

    def test_a_client_without_release_preflight_stops_everything(self) -> None:
        self.make_client("python", "Python")
        self.make_client("rust", "Rust", contract=False)
        result = self.run_make("release_all_clients", clients="python rust")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("client rust lacks release_preflight", result.stdout)
        self.assertEqual([ref for ref in self.origin_refs("python") if VERSION in ref], [])

    def test_all_preflights_pass_then_all_release_in_parallel_with_one_devops_clone(self) -> None:
        self.make_client("python", "Python")
        self.make_client("js", "Js", release_md="src/RELEASE.md")
        result = self.run_make("release_all_clients", clients="python js")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.count("Cloning ondewo-devops-accounts"), 1, result.stdout)
        self.assertIn("python : RELEASED", result.stdout)
        self.assertIn("js : RELEASED", result.stdout)
        self.assertLess(result.stdout.index("PREFLIGHT OK"), result.stdout.index("Releasing all clients"))
        for name in ("python", "js"):
            log: str = (self.control / f"{name}.log").read_text(encoding="utf-8")
            self.assertLess(log.index("preflight"), log.index("release "))
        self.assert_everything_cleaned_up(result)


class TestOwnReleaseCredentials(DriverFixture):
    """The vtsi-api's own ondewo_release: one temporary clone, deleted before the release runs."""

    def test_the_token_reaches_the_release_and_the_clone_is_gone_before_it(self) -> None:
        probe: Path = self.root / "probe"
        (self.driver / "probe.mk").write_text(
            f"probe:\n\t@printf '%s|' \"$${{GITHUB_GH_TOKEN}}\" > {probe}; ls -A $${{TMPDIR}} >> {probe}\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["scripts/with_devops_accounts.sh", "--github-token", "make", "-s", "-f", "probe.mk", "probe"],
            cwd=self.driver,
            env={**self.env, "DEVOPS_ACCOUNT_GIT_URL": f"file://{self.origins}/ondewo-devops-accounts.git"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(probe.read_text(encoding="utf-8").strip(), "fake-token|")
        self.assertEqual(list(self.tmpdir.iterdir()), [])

    def test_a_failing_command_still_removes_the_clone(self) -> None:
        result = subprocess.run(
            ["scripts/with_devops_accounts.sh", "sh", "-c", 'test -f "$DEVOPS_ACCOUNT_DIR/account_github.env" && exit 7'],
            cwd=self.driver,
            env={**self.env, "DEVOPS_ACCOUNT_GIT_URL": f"file://{self.origins}/ondewo-devops-accounts.git"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertEqual(list(self.tmpdir.iterdir()), [])


class TestStaticPins(unittest.TestCase):
    """Properties of the Makefile, Dockerfile.utils, .dockerignore and the workflows."""

    def test_no_bare_export_no_sudo_no_backgrounded_exit(self) -> None:
        self.assertIsNone(re.search(r"^export\s*$", MAKEFILE, re.M), "a bare `export` leaks every variable into the clients")
        self.assertNotIn("sudo", MAKEFILE)
        self.assertIsNone(re.search(r"[^&]&\s*exit", MAKEFILE), "`& exit 1` backgrounds the echo; use `&& exit 1`")

    def test_no_wrapper_line_uses_dollar_make(self) -> None:
        for line in MAKEFILE.splitlines():
            if line.startswith("\t") and "$(WITH_DEVOPS_ACCOUNTS)" in line:
                self.assertNotIn("$(MAKE)", line, "make runs $(MAKE) lines under -n: a dry run would clone the credentials")

    def test_the_proto_compiler_is_pinned_exactly(self) -> None:
        self.assertRegex(MAKEFILE, r"(?m)^ONDEWO_PROTO_COMPILER_VERSION=[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertNotIn("api.github.com/repos/ondewo/ondewo-proto-compiler", MAKEFILE)

    def test_release_all_clients_runs_preflight_first(self) -> None:
        self.assertRegex(MAKEFILE, r"(?m)^release_all_clients_after_preflight: preflight_all_clients$")
        self.assertRegex(MAKEFILE, r"(?m)^\.NOTPARALLEL:$")

    def test_the_release_notes_slice_is_anchored(self) -> None:
        self.assertIn(r"/^\#+ Release ONDEWO VTSI API \Q${ONDEWO_VTSI_API_VERSION}\E$$/../^\*{5}/", MAKEFILE)

    def test_the_release_notes_slice_takes_only_the_exact_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "RELEASE.md").write_text(
                "# Release History\n\n## Release ONDEWO VTSI API 9.1.10\n\nten\n\n*****************\n\n"
                "## Release ONDEWO VTSI API 9.1.1\n\none\n\n*****************\n\n## Release ONDEWO VTSI API 9a1b1\n\nx\n",
                encoding="utf-8",
            )
            output: str = subprocess.run(
                ["make", "-s", "-f", str(REPO_ROOT / "Makefile"), "TEST", "ONDEWO_VTSI_API_VERSION=9.1.1"],
                cwd=directory,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        self.assertIn("\none\n", output)
        self.assertNotIn("ten", output)
        self.assertNotIn("9a1b1", output)

    def test_dockerfile_utils_carries_no_credential_and_pins_its_base(self) -> None:
        dockerfile: str = (REPO_ROOT / "Dockerfile.utils").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?m)^\s*(ENV|ARG)\s+\S*(TOKEN|PASSWORD|SECRET)", dockerfile))
        self.assertRegex(dockerfile, r"(?m)^FROM \S+:\S+@sha256:[0-9a-f]{64}$")
        self.assertRegex(dockerfile, r'(?m)^CMD \[')
        self.assertIn("--checksum=sha256:", dockerfile)

    def test_the_build_context_is_an_allow_list(self) -> None:
        lines: List[str] = [
            line for line in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")
        ]
        self.assertEqual(lines[0], "*")
        self.assertTrue(all(line.startswith("!") for line in lines[1:]), lines)
        self.assertFalse(any(re.search(r"devops|client|log|\.git", line) for line in lines[1:]), lines)

    def test_workflows_pin_actions_and_set_the_default_branch_before_checkout(self) -> None:
        for workflow in sorted((REPO_ROOT / ".github" / "workflows").glob("*.y*ml")):
            text: str = workflow.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"uses:\s*\S+@(master|main)\b", workflow.name)
            checkout: int = text.index("actions/checkout@")
            self.assertIn("git config --global init.defaultBranch master", text[:checkout], workflow.name)
        hygiene: str = (REPO_ROOT / ".github" / "workflows" / "release-hygiene.yml").read_text(encoding="utf-8")
        self.assertIn("'release/**'", hygiene)
        self.assertIn("scripts/test_release_driver.py", hygiene)


if __name__ == "__main__":
    unittest.main()
