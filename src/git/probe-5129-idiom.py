"""Which GitPython idiom actually puts `-c core.quotepath=false` on the git argv,
and does quotepath=false stop git from C-quoting names with spaces/quotes/tabs?

Run: cd src/git && uv run python ../probe_idiom.py
"""

import pathlib
import subprocess
import tempfile

import git
import mcp_server_git.server as s


def new_repo():
    d = pathlib.Path(tempfile.mkdtemp(prefix="gitprobe-"))
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    r = git.Repo(d)
    with r.config_writer() as cw:
        cw.set_value("user", "name", "Probe")
        cw.set_value("user", "email", "probe@example.invalid")
    return r


def head(t):
    print(f"\n===== {t}")


r = new_repo()
names = [
    "名前.txt",          # high bytes only
    "my file.txt",       # ASCII space
    'name"quote.txt',    # double quote
    "back\\slash.txt",   # backslash
    "tab\there.txt",     # literal tab
    "café.txt",          # Latin-1 range
    "🎉.txt",            # 4-byte UTF-8
]
for n in names:
    (pathlib.Path(r.working_dir) / n).write_text("x\n")

head("A. git_status lines, as shipped (no flag)")
print([l for l in s.git_status(r).splitlines() if ".txt" in l])

head("A2. git_status lines, core.quotepath=false")
print([l for l in r.git(c="core.quotepath=false").status().splitlines() if ".txt" in l])

head("A3. does the -c option persist on the shared repo.git instance?")
print("  next plain call still carries _git_options:", r.git._git_options)
print("  lines from a later plain r.git.status():",
      [l for l in r.git.status().splitlines() if ".txt" in l])

head("B. per-subcommand kwarg form: repo.git.status(c='core.quotepath=false')")
try:
    out = r.git.status(c="core.quotepath=false")
    print("  argv-ish result lines:", [l for l in out.splitlines() if ".txt" in l])
except Exception as e:  # noqa: BLE001
    print(f"  {type(e).__name__}: {e}")
print("  transform_kwarg('c','x',split_single_char_options=False) ->",
      git.Git.transform_kwarg(git.Git(os.getcwd() if False else "/tmp"), "c", "core.quotepath=false", False))

head("C. execute() form")
print([l for l in r.git.execute(["git", "-c", "core.quotepath=false", "status"]).splitlines() if ".txt" in l])

head("D. diff headers with the flag, all seven names staged")
for n in names:
    r.git.add("--", n)
print("  quotepath=false :", [l for l in r.git(c="core.quotepath=false").diff("--cached").splitlines() if l.startswith("diff --git")])
print("  default         :", [l for l in r.git.diff("--cached").splitlines() if l.startswith("diff --git")])

head("E. quoting-proof alternative: status --porcelain -z")
raw = r.git.status("--porcelain", "-z")
print("  entries:", [e.replace("\x00", "<NUL>") for e in raw.split("\x00") if e.strip()])

head("F. can GitPython decode the quoted/escaped name back?")
q = '\\346\\227\\245\\346\\234\\254.txt'
print("  unquote_c_style import test:")
try:
    from git.util import dequote_paths  # noqa: F401
    print("   helper exists:", dequote_paths)
except Exception as e:  # noqa: BLE001
    print("   no public helper:", e)
try:
    print("   git.util.unquote_path?", hasattr(git.util, "unquote_paths"))
except Exception as e:  # noqa: BLE001
    print("  ", e)

head("G. does the octal name survive git_add's own path checks?")
try:
    s.git_add(r, [q])
except Exception as e:  # noqa: BLE001
    print("  git_add(octal name):", type(e).__name__, str(e)[:200])
