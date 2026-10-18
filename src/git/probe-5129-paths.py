"""Evidence for modelcontextprotocol/servers issue #5129.

Exercises the four path-printing git tools in-process, exactly as the issue's
repro does, plus the names git C-quotes for reasons other than core.quotepath.

Run:  cd src/git && uv run python ~/projects/mcp-servers-evidence2/verify_paths.py
"""

import pathlib
import subprocess
import tempfile

import git
import mcp_server_git.server as s

HIGH_BYTE = "日本.txt"          # the name in the issue
TRICKY = [
    "日本.txt",                   # high bytes only (the issue's case)
    "café.txt",                   # 2-byte UTF-8
    "🎉.txt",                     # 4-byte UTF-8
    "my file.txt",                # ASCII space
    'name"quote.txt',            # double quote
    "back\\slash.txt",            # backslash
    "tab\there.txt",              # control character
]


def new_repo():
    d = pathlib.Path(tempfile.mkdtemp(prefix="git5129-"))
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    r = git.Repo(d)
    with r.config_writer() as cw:
        cw.set_value("user", "name", "Probe")
        cw.set_value("user", "email", "probe@example.invalid")
    return r


def head(t):
    print(f"\n=== {t}")


def client_name_from_status(status_text):
    """What the issue's repro does: take the path line, strip the quotes."""
    cand = [l.strip() for l in status_text.splitlines() if ".txt" in l and not l.startswith("Untracked")]
    if not cand:
        cand = [l.strip() for l in status_text.splitlines() if ".txt" in l]
    return cand[0].strip('"') if cand else None


def add(repo, name):
    try:
        s.git_add(repo, [name])
        return "round-trip OK"
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "stderr: " in msg:
            msg = msg.split("stderr: ")[-1]
        return "FAILS: " + msg.strip().strip("'").splitlines()[0]


def issue_repro():
    head("1. the issue's repro, in-process (server at HEAD)")
    r = new_repo()
    (pathlib.Path(r.working_dir) / HIGH_BYTE).write_text("a\n")
    st = s.git_status(r)
    print("   git_status untracked line :", repr([l for l in st.splitlines() if ".txt" in l]))
    name = client_name_from_status(st)
    print("   name a client would reuse :", repr(name))
    print("   git_add(that name)        :", add(r, name))
    print("   git_add(the real name)     :", add(r, HIGH_BYTE))

    head("2. the four tools the issue names, one non-ASCII file with a staged change")
    r2 = new_repo()
    p = pathlib.Path(r2.working_dir) / HIGH_BYTE
    p.write_text("a\n")
    r2.git.add(HIGH_BYTE)
    r2.index.commit("base")
    p.write_text("a\nb\n")
    print("   git_diff_unstaged hdr:", [l for l in s.git_diff_unstaged(r2).splitlines() if l.startswith(("diff --git", "--- ", "+++ "))])
    r2.git.add(HIGH_BYTE)
    print("   git_diff_staged   hdr:", [l for l in s.git_diff_staged(r2).splitlines() if l.startswith(("diff --git", "--- ", "+++ "))])
    print("   git_diff(HEAD)    hdr:", [l for l in s.git_diff(r2, "HEAD").splitlines() if l.startswith(("diff --git", "--- ", "+++ "))])
    print("   git_status        line:", [l for l in s.git_status(r2).splitlines() if ".txt" in l])


def round_trip_matrix():
    head("3. round-trip matrix: does the name each tool prints go back into git_add?")
    r = new_repo()
    for n in TRICKY:
        (pathlib.Path(r.working_dir) / n).write_text("x\n")
    st = s.git_status(r)
    for n in TRICKY:
        line = [l for l in st.splitlines() if n.split(".")[0][:3] in l or n in l]
        printed = client_name_from_status(st)
        print(f"   real {n!r}")
    print("   --- per file, independently")
    for n in TRICKY:
        r2 = new_repo()
        (pathlib.Path(r2.working_dir) / n).write_text("x\n")
        st2 = s.git_status(r2)
        shown = [l.strip() for l in st2.splitlines() if ".txt" in l and not l.startswith("Untracked")]
        printed = shown[0].strip('"') if shown else None
        print(f"   {n!r:24} status shows {shown[0] if shown else None!r}")
        print(f"   {'':24} client reuses {printed!r} -> {add(r2, printed)}")


def gitpython_idioms():
    head("4. GitPython: which spelling actually puts -c on the git argv?")
    r = new_repo()
    (pathlib.Path(r.working_dir) / HIGH_BYTE).write_text("x\n")

    print("   a) repo.git.status(c='core.quotepath=false')")
    try:
        out = r.git.status(c="core.quotepath=false")
        print("      -> ok:", [l for l in out.splitlines() if ".txt" in l])
    except Exception as e:  # noqa: BLE001
        print("      ->", type(e).__name__, str(e).splitlines()[1].strip() if len(str(e).splitlines()) > 1 else str(e))
        print("      ->", [l for l in str(e).splitlines() if "cmdline" in l or "unknown switch" in l])

    print("   b) repo.git(c='core.quotepath=false').status()")
    g = r.git(c="core.quotepath=false")
    print("      same object as repo.git:", g is r.git)
    print("      _git_options while pending:", r.git._git_options)
    print("      ->", [l for l in g.status().splitlines() if ".txt" in l])
    print("      _git_options afterwards:", r.git._git_options)
    print("      a later plain r.git.status():", [l for l in r.git.status().splitlines() if ".txt" in l])

    print("   c) repo.git.execute(['git','-c','core.quotepath=false','status'])")
    print("      ->", [l for l in r.git.execute(["git", "-c", "core.quotepath=false", "status"]).splitlines() if ".txt" in l])


def alternatives():
    head("5. quoting-proof alternatives, measured")
    r = new_repo()
    for n in TRICKY:
        (pathlib.Path(r.working_dir) / n).write_text("x\n")
    raw = r.git.status("--porcelain", "-z")
    print("   status --porcelain -z entries:", [e.replace("\x00", "<NUL>") for e in raw.split("\x00") if e.strip()])
    print("   status --porcelain (no -z)  :", [l for l in r.git.status("--porcelain").splitlines() if ".txt" in l])


def main():
    print("git      :", subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip())
    print("GitPython:", git.__version__)
    print("python   :", subprocess.run(["python", "-V"], capture_output=True, text=True).stdout.strip() or "")
    print("module   :", s.__file__)
    print("source of the four call sites:")
    for i, line in enumerate(open(s.__file__).read().splitlines(), 1):
        if "repo.git.status()" in line or "repo.git.diff(" in line or "_git" in line and "def " in line:
            print(f"   L{i}: {line.strip()}")
    issue_repro()
    round_trip_matrix()
    gitpython_idioms()
    alternatives()


if __name__ == "__main__":
    main()
