#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pomocnik GitHub dla Kubuntu/Ubuntu, KDE i Kate (także inne Linuksy).

Lokalny program graficzny. Wymaga tylko Pythona 3, tkinter i Git.
Nie używa GitHub API ani nie przechowuje haseł lub tokenów.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

APP_TITLE = "Pomocnik GitHub"
APP_VERSION = "1.1"
DEFAULT_FOLDER = Path.home() / "Projekty_Codex"
APP_DIR = Path(__file__).resolve().parent
ASKPASS = APP_DIR / "git_askpass.py"

BG = "#0b1220"
PANEL = "#101c30"
PANEL_LIGHT = "#16253b"
BORDER = "#29405c"
FG = "#eef5ff"
MUTED = "#a7bed8"
ACCENT = "#42b7e9"
SUCCESS = "#38c9a4"
WARNING = "#f7c66c"
FONT = "DejaVu Sans"

GITHUB_HTTPS = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)/?$",
    re.IGNORECASE,
)
GITHUB_SSH = re.compile(
    r"^git@github\.com:([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$",
    re.IGNORECASE,
)


class GitError(RuntimeError):
    pass


def normalized_repo_url(raw: str) -> tuple[str, str, str]:
    """Return (Git URL, owner, repository name) for a GitHub repository."""
    url = raw.strip()
    match = GITHUB_HTTPS.fullmatch(url) or GITHUB_SSH.fullmatch(url)
    if not match:
        raise ValueError(
            "Wpisz adres repozytorium GitHub, na przykład:\n"
            "https://github.com/twoj-login/moj-projekt.git"
        )
    owner, repo = match.groups()
    if repo.endswith(".git"):
        repo = repo[:-4]
    if owner in (".", "..") or repo in (".", "..") or not repo:
        raise ValueError("Niepoprawna nazwa repozytorium.")
    # Zwracamy standardowy URL HTTPS lub oryginalny wariant SSH.
    target = f"git@github.com:{owner}/{repo}.git" if url.startswith("git@") else f"https://github.com/{owner}/{repo}.git"
    return target, owner, repo


def same_github_repo(a: str, b: str) -> bool:
    try:
        _, aa, ar = normalized_repo_url(a)
        _, ba, br = normalized_repo_url(b)
        return (aa.lower(), ar.lower()) == (ba.lower(), br.lower())
    except ValueError:
        return a.rstrip("/") == b.rstrip("/")


def looks_sensitive(relative: str) -> bool:
    path = Path(relative)
    parts = [p.lower() for p in path.parts]
    filename = path.name.lower()
    if filename in {
        ".env", "id_rsa", "id_ed25519", "credentials", "credentials.json",
        "secrets.json", "token.json", "config.json.secret", ".netrc",
    }:
        return True
    if filename.startswith(".env."):
        return True
    if filename.endswith((".pem", ".p12", ".pfx", ".key", ".kdbx")):
        return True
    if any(part in {".ssh", ".aws", "secrets", "private_keys"} for part in parts[:-1]):
        return True
    return False


def looks_backup(relative: str) -> bool:
    filename = Path(relative).name.lower()
    return filename.endswith((
        ".fcbak", ".fcstd1", ".fcstd2", ".bak", ".tmp", ".swp", "~"
    )) or filename in {"thumbs.db", ".ds_store"}


def human_size(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GiB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.1f} MiB"
    if n >= 1024:
        return f"{n / 1024:.0f} KiB"
    return f"{n} B"


@dataclass
class CmdResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def text(self) -> str:
        return "\n".join(s.strip() for s in (self.stdout, self.stderr) if s.strip())


class GitService:
    def __init__(self) -> None:
        if shutil.which("git") is None:
            raise GitError("Nie znaleziono programu Git. Zainstaluj pakiet git.")

    def run(self, *args: str, cwd: Path | None = None, check: bool = True,
            timeout: int = 900) -> CmdResult:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_MERGE_AUTOEDIT"] = "no"
        if ASKPASS.is_file():
            env["GIT_ASKPASS"] = str(ASKPASS)
        try:
            completed = subprocess.run(
                ["git", *args], cwd=str(cwd) if cwd else None,
                env=env, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError("Przekroczono czas oczekiwania na Git. Sprawdź połączenie z internetem.") from exc
        except OSError as exc:
            raise GitError(f"Nie udało się uruchomić Git: {exc}") from exc
        result = CmdResult(completed.stdout, completed.stderr, completed.returncode)
        if check and completed.returncode != 0:
            raise GitError(result.text or f"Git zakończył pracę kodem {completed.returncode}.")
        return result

    def repo_root(self, directory: Path) -> Path | None:
        result = self.run("rev-parse", "--show-toplevel", cwd=directory, check=False)
        if result.returncode:
            return None
        return Path(result.stdout.strip()).resolve()

    def branch(self, directory: Path) -> str:
        branch = self.run("branch", "--show-current", cwd=directory).stdout.strip()
        if not branch:
            raise GitError("Nie można ustalić bieżącej gałęzi Git.")
        return branch

    def has_commits(self, directory: Path) -> bool:
        return self.run("rev-parse", "--verify", "HEAD", cwd=directory, check=False).returncode == 0

    def origin(self, directory: Path) -> str | None:
        result = self.run("remote", "get-url", "origin", cwd=directory, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def changed_files(self, directory: Path) -> tuple[list[str], list[str]]:
        """Files changed, new, deleted, or already staged. Respects .gitignore."""
        unstaged = self.run("ls-files", "-m", "-d", "-o", "--exclude-standard", "-z", cwd=directory)
        staged = self.run("diff", "--cached", "--name-only", "-z", cwd=directory)
        # -z lists need byte-stable separators; text=True retains NUL byte.
        untracked_paths = [s for s in unstaged.stdout.split("\0") if s]
        staged_paths = [s for s in staged.stdout.split("\0") if s]
        return sorted(set(untracked_paths + staged_paths)), sorted(set(staged_paths))

    def status(self, directory: Path) -> str:
        return self.run("status", "-sb", cwd=directory).stdout.strip()

    def stage_paths(self, directory: Path, paths: list[str]) -> None:
        # Avoid OS argv length limits for large projects.
        for start in range(0, len(paths), 75):
            group = paths[start:start + 75]
            self.run("add", "-A", "--", *group, cwd=directory)

    def staged_change_exists(self, directory: Path) -> bool:
        result = self.run("diff", "--cached", "--quiet", cwd=directory, check=False)
        if result.returncode > 1:
            raise GitError(result.text or "Nie udało się sprawdzić zmian do Commit.")
        return result.returncode == 1

    def push(self, directory: Path) -> CmdResult:
        return self.run("push", "-u", "origin", self.branch(directory), cwd=directory)

    def pull(self, directory: Path) -> CmdResult:
        # Untracked files (e.g. FreeCAD backups) may stay on disk.
        # Git itself rejects a pull if an untracked file would be overwritten.
        dirty_worktree = self.run("diff", "--quiet", cwd=directory, check=False)
        dirty_index = self.run("diff", "--cached", "--quiet", cwd=directory, check=False)
        if dirty_worktree.returncode > 1 or dirty_index.returncode > 1:
            raise GitError("Nie można sprawdzić lokalnych zmian Git.")
        if dirty_worktree.returncode == 1 or dirty_index.returncode == 1:
            raise GitError("W projekcie są niezapisane w Git zmiany. Najpierw je zatwierdź albo obsłuż w Kate.")
        # --ff-only prevents automatic merges or rebases of divergent history.
        upstream = self.run("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}",
                            cwd=directory, check=False)
        if upstream.returncode == 0:
            return self.run("pull", "--ff-only", cwd=directory)
        return self.run("pull", "--ff-only", "origin", self.branch(directory), cwd=directory)


def safety_warnings(directory: Path, paths: list[str]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    blocked: list[str] = []
    for path in paths:
        absolute = directory / path
        if not absolute.exists() or absolute.is_symlink() or not absolute.is_file():
            continue
        try:
            size = absolute.stat().st_size
        except OSError:
            continue
        if size >= 100 * 1024 * 1024:
            blocked.append(f"{path} ({human_size(size)})")
        elif size >= 50 * 1024 * 1024:
            warnings.append(f"Duży plik: {path} ({human_size(size)})")
        if looks_sensitive(path):
            warnings.append(f"Możliwy plik poufny: {path}")
        elif looks_backup(path):
            warnings.append(f"Kopia zapasowa: {path}")
    return warnings, blocked


class FilesDialog(tk.Toplevel):
    """Explicit choice of files to stage; backups and secrets deselected by default."""
    def __init__(self, master: tk.Tk, directory: Path, paths: list[str],
                 already_staged: list[str]):
        super().__init__(master)
        self.title("Wybierz pliki do zatwierdzenia")
        self.geometry("830x560")
        self.minsize(600, 380)
        self.configure(bg=BG)
        self.result: list[str] | None = None
        self.paths = paths
        self.directory = directory
        self.staged = set(already_staged)
        self.transient(master)

        tk.Label(self, text="Które pliki wysłać na GitHuba?", bg=BG, fg=FG,
                 font=(FONT, 15, "bold")).pack(anchor="w", padx=22, pady=(18, 5))
        tk.Label(self, text="Zaznaczone = zostaną dodane do Commit. Kopie FreeCAD i potencjalne sekrety\n"
                 "domyślnie są odznaczone. Niczego tutaj nie usuwamy.",
                 bg=BG, fg=MUTED, justify="left", font=(FONT, 10)).pack(anchor="w", padx=22, pady=(0, 8))

        body = tk.Frame(self, bg=PANEL)
        body.pack(fill="both", expand=True, padx=22, pady=6)
        bar = tk.Scrollbar(body, orient="vertical")
        self.listbox = tk.Listbox(body, selectmode="extended", exportselection=False,
                                 bg=PANEL, fg=FG, selectbackground="#245d83",
                                 selectforeground="white", relief="flat", borderwidth=0,
                                 font=("DejaVu Sans Mono", 10), yscrollcommand=bar.set,
                                 activestyle="none")
        bar.config(command=self.listbox.yview)
        bar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        for index, path in enumerate(paths):
            flag = "[DOBRANY] " if path in self.staged else ""
            self.listbox.insert("end", flag + path)
            if not looks_backup(path) and not looks_sensitive(path):
                self.listbox.selection_set(index)

        if self.staged:
            tk.Label(self, text="Uwaga: pliki już dobrane wcześniej w Kate także wejdą do Commit.",
                     bg=BG, fg=WARNING, font=(FONT, 10)).pack(anchor="w", padx=22)

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=22, pady=15)
        ttk.Button(actions, text="Zaznacz bez kopii i sekretów", command=self.safe_select).pack(side="left")
        ttk.Button(actions, text="Anuluj", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="Dalej — sprawdź wybór", command=self.accept,
                   style="Accent.TButton").pack(side="right")
        self.grab_set()
        self.focus_set()

    def safe_select(self) -> None:
        self.listbox.selection_clear(0, "end")
        for i, path in enumerate(self.paths):
            if not looks_backup(path) and not looks_sensitive(path):
                self.listbox.selection_set(i)

    def accept(self) -> None:
        selected = [self.paths[int(i)] for i in self.listbox.curselection()]
        if not selected and not self.staged:
            messagebox.showinfo("Brak wyboru", "Wybierz co najmniej jeden plik.", parent=self)
            return
        self.result = selected
        self.destroy()


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE} {APP_VERSION} • Kubuntu / Kate")
        self.geometry("990x790")
        self.minsize(750, 650)
        self.configure(bg=BG)
        self.busy = False
        self.git: GitService | None = None
        self.clone_url = tk.StringVar()
        self.clone_base = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.clone_name = tk.StringVar()
        self.upload_path = tk.StringVar()
        self.upload_url = tk.StringVar()
        self.upload_message = tk.StringVar(value="Pierwsza wersja projektu")
        self.sync_path = tk.StringVar()
        self.sync_message = tk.StringVar(value="Aktualizacja projektu")
        self.status_var = tk.StringVar(value="Gotowy do pracy")
        self.build_style()
        self.build_ui()
        try:
            self.git = GitService()
            if not shutil.which("kate"):
                self.log("Uwaga: nie znaleziono Kate w PATH. Pozostałe funkcje działają.")
            self.log("Pomocnik uruchomiony. Hasła i tokeny nie są zapisywane przez program.")
        except GitError as exc:
            self.log(str(exc))
            messagebox.showerror("Brakuje Git", str(exc))

    def build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=(FONT, 11, "bold"), padding=(17, 13),
                        background=PANEL, foreground=MUTED, borderwidth=1)
        style.map("TNotebook.Tab", background=[("selected", PANEL_LIGHT)],
                  foreground=[("selected", FG)])
        style.configure("TEntry", font=(FONT, 11), padding=8,
                        fieldbackground="#f1f6fc", foreground="#111827")
        style.configure("TButton", font=(FONT, 10), padding=(11, 10),
                        background=PANEL_LIGHT, foreground=FG, borderwidth=0)
        style.map("TButton", background=[("active", "#28445e")])
        style.configure("Accent.TButton", font=(FONT, 11, "bold"), padding=(12, 11),
                        background="#1975a6", foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#2389bc")])
        style.configure("Success.TButton", font=(FONT, 11, "bold"), padding=(12, 11),
                        background="#177d69", foreground="white", borderwidth=0)
        style.map("Success.TButton", background=[("active", "#239f86")])

    def build_ui(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=28, pady=(24, 14))
        tk.Label(header, text="Pomocnik GitHub", bg=BG, fg=FG,
                 font=(FONT, 23, "bold")).pack(anchor="w")
        tk.Label(header, text="Projekty FreeCAD, pliki i GitHub — prosto, po polsku, bez komend.",
                 bg=BG, fg=MUTED, font=(FONT, 11)).pack(anchor="w", pady=(3, 0))
        tk.Label(header, text="Pobierz ↓  •  Wyślij ↑  •  Synchronizuj ↻",
                 bg=BG, fg=ACCENT, font=(FONT, 11, "bold")).pack(anchor="w", pady=(12, 0))

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=False, padx=24, pady=(0, 13))
        clone_tab = self.make_tab()
        upload_tab = self.make_tab()
        sync_tab = self.make_tab()
        self.tabs.add(clone_tab, text="↓  Pobierz nowy")
        self.tabs.add(upload_tab, text="↑  Wyślij nowy")
        self.tabs.add(sync_tab, text="↻  Synchronizuj")
        self.build_clone_tab(clone_tab)
        self.build_upload_tab(upload_tab)
        self.build_sync_tab(sync_tab)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        tk.Label(bottom, text="Dziennik działań", bg=BG, fg=FG,
                 font=(FONT, 11, "bold")).pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(
            bottom, bg="#08101c", fg="#c9e2ee", insertbackground=FG,
            font=("DejaVu Sans Mono", 9), relief="flat", wrap="word",
            height=8, state="disabled", padx=12, pady=10,
        )
        self.log_box.pack(fill="both", expand=True, pady=(7, 8))
        tk.Label(bottom, textvariable=self.status_var, bg=BG, fg=SUCCESS,
                 font=(FONT, 10)).pack(anchor="w")

    def make_tab(self) -> tk.Frame:
        tab = tk.Frame(self.tabs, bg=PANEL, padx=22, pady=18)
        return tab

    def heading(self, tab: tk.Frame, title: str, subtitle: str) -> None:
        tk.Label(tab, text=title, bg=PANEL, fg=FG,
                 font=(FONT, 14, "bold")).pack(anchor="w", pady=(0, 3))
        tk.Label(tab, text=subtitle, bg=PANEL, fg=MUTED,
                 font=(FONT, 10), justify="left", wraplength=850).pack(anchor="w", pady=(0, 14))

    def field(self, tab: tk.Frame, label: str, variable: tk.StringVar,
              browse: bool = False, default_button: str = "Wybierz") -> None:
        tk.Label(tab, text=label, bg=PANEL, fg=FG,
                 font=(FONT, 10, "bold")).pack(anchor="w", pady=(7, 3))
        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", pady=(0, 2))
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True)
        if browse:
            ttk.Button(row, text=default_button,
                       command=lambda: self.pick_directory(variable)).pack(side="left", padx=(8, 0))

    def build_clone_tab(self, tab: tk.Frame) -> None:
        self.heading(tab, "Pobierz projekt z GitHuba",
                     "Dla projektu, którego jeszcze nie masz na tym komputerze.")
        self.field(tab, "Adres repozytorium GitHub (HTTPS lub SSH)", self.clone_url)
        self.field(tab, "Katalog na projekty", self.clone_base, browse=True)
        self.field(tab, "Nazwa nowego katalogu (opcjonalnie)", self.clone_name)
        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", pady=(15, 0))
        ttk.Button(row, text="↓  Pobierz projekt", style="Accent.TButton",
                   command=self.clone_clicked).pack(side="left")
        tk.Label(row, text="Nie nadpisze istniejącego folderu.",
                 bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=15)

    def build_upload_tab(self, tab: tk.Frame) -> None:
        self.heading(tab, "Wyślij nowy projekt z komputera",
                     "Najpierw utwórz PUSTE repozytorium na GitHubie (bez README).\n"
                     "Następnie wskaż katalog projektu i wklej adres repozytorium.")
        self.field(tab, "Katalog istniejącego projektu na komputerze", self.upload_path, browse=True)
        self.field(tab, "Adres pustego repozytorium na GitHubie", self.upload_url)
        self.field(tab, "Opis pierwszego zatwierdzenia (Commit)", self.upload_message)
        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", pady=(14, 0))
        ttk.Button(row, text="Utwórz repozytorium na GitHubie",
                   command=self.open_new_repo).pack(side="left", padx=(0, 9))
        ttk.Button(row, text="↑  Sprawdź i wyślij", style="Success.TButton",
                   command=self.upload_clicked).pack(side="left")

    def build_sync_tab(self, tab: tk.Frame) -> None:
        self.heading(tab, "Synchronizuj istniejący projekt",
                     "Pobieranie i wysyłanie są osobnymi operacjami. Nic nie będzie scalane na siłę.")
        self.field(tab, "Katalog projektu Git na komputerze", self.sync_path, browse=True)
        self.field(tab, "Opis zmian przy wysyłaniu (Commit)", self.sync_message)
        row = tk.Frame(tab, bg=PANEL)
        row.pack(fill="x", pady=(15, 0))
        ttk.Button(row, text="Sprawdź stan", command=self.status_clicked).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="↓  Pobierz zmiany", style="Accent.TButton",
                   command=self.pull_clicked).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="↑  Zatwierdź i wyślij", style="Success.TButton",
                   command=self.sync_push_clicked).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Otwórz w Kate", command=self.open_kate_clicked).pack(side="left")

    def pick_directory(self, variable: tk.StringVar) -> None:
        current = Path(variable.get()).expanduser()
        initial = current if current.is_dir() else current.parent
        folder = filedialog.askdirectory(initialdir=str(initial if initial.is_dir() else Path.home()),
                                         title="Wybierz katalog", mustexist=True)
        if folder:
            variable.set(folder)

    def log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] {text.strip()}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def fail(self, text: str) -> None:
        self.log("BŁĄD: " + text)
        self.status_var.set("Nie wykonano operacji — sprawdź dziennik")
        messagebox.showerror("Nie udało się", text, parent=self)

    def worker(self, description: str, action, done_message: str,
               on_success=None) -> None:
        if self.busy:
            messagebox.showinfo("Operacja trwa", "Zakończ najpierw bieżącą operację.", parent=self)
            return
        if self.git is None:
            self.fail("Git nie jest dostępny.")
            return
        self.busy = True
        self.status_var.set("Trwa: " + description + "…")
        self.log(description + "…")

        def run_action() -> None:
            try:
                output = action()
            except Exception as exc:
                self.after(0, lambda err=str(exc): finish_error(err))
            else:
                self.after(0, lambda out=output: finish_success(out))

        def finish_error(err: str) -> None:
            self.busy = False
            extra = ""
            if "Authentication failed" in err or "could not read Username" in err:
                extra = ("\n\nSprawdź logowanie do GitHuba. Program używa tej samej "
                         "konfiguracji Git co terminal i Kate.")
            if "non-fast-forward" in err or "fetch first" in err or "divergent" in err:
                extra = ("\n\nHistoria lokalna i GitHub różnią się. Program nie wymusi "
                         "nadpisania — rozwiąż różnice w Kate.")
            self.fail(err + extra)

        def finish_success(output) -> None:
            self.busy = False
            if output:
                self.log(str(output))
            self.log(done_message)
            self.status_var.set(done_message)
            if on_success:
                on_success()
            messagebox.showinfo("Sukces", done_message, parent=self)

        threading.Thread(target=run_action, daemon=True).start()

    def clone_clicked(self) -> None:
        try:
            url, _, repo = normalized_repo_url(self.clone_url.get())
            base = Path(self.clone_base.get()).expanduser().resolve()
            folder_name = self.clone_name.get().strip() or repo
            if folder_name in {".", ".."} or "\x00" in folder_name or "/" in folder_name or "\\" in folder_name:
                raise ValueError("Nazwa katalogu musi być prostą nazwą, bez ukośników.")
            target = base / folder_name
            if target.exists() or target.is_symlink():
                raise ValueError(f"Katalog już istnieje:\n{target}\n\nNic nie nadpisano.")
            if not base.is_dir() and not messagebox.askyesno(
                    "Utworzyć katalog?", f"Utworzyć katalog na projekty?\n{base}", parent=self):
                return
            if not messagebox.askyesno(
                    "Potwierdź pobieranie",
                    f"Z GitHuba:\n{url}\n\nDo nowego katalogu:\n{target}\n\nPobrać projekt?",
                    parent=self):
                return
        except (ValueError, OSError) as exc:
            self.fail(str(exc))
            return

        def task() -> str:
            base.mkdir(parents=True, exist_ok=True)
            # Recheck after confirmation, in case another app just created the folder.
            if target.exists() or target.is_symlink():
                raise GitError("Katalog docelowy już istnieje. Klonowanie anulowano.")
            result = self.git.run("clone", url, str(target), timeout=1800)
            return result.text or "Pobrano projekt."

        self.worker("Pobieranie " + url, task, "Projekt pobrany do: " + str(target),
                    on_success=lambda: self.sync_path.set(str(target)))

    def open_new_repo(self) -> None:
        webbrowser.open("https://github.com/new")
        messagebox.showinfo(
            "Puste repozytorium", "Na GitHubie podaj nazwę, ustaw Private i wyłącz README.\n"
            "Nie dodawaj .gitignore ani licencji. Po utworzeniu skopiuj adres repozytorium\n"
            "do pola w Pomocniku.", parent=self,
        )

    def require_repo(self, path_raw: str) -> Path:
        if not path_raw.strip():
            raise ValueError("Wybierz katalog projektu.")
        path = Path(path_raw).expanduser().resolve()
        if not path.is_dir():
            raise ValueError("Katalog nie istnieje: " + str(path))
        root = self.git.repo_root(path)
        if root is None:
            raise ValueError("Ten katalog nie jest jeszcze repozytorium Git.")
        if root != path:
            raise ValueError(f"Wskazany katalog należy do repozytorium w:\n{root}\n\nWybierz katalog główny repozytorium.")
        return path

    def pick_files(self, path: Path) -> tuple[list[str], list[str]] | None:
        candidates, staged = self.git.changed_files(path)
        if len(candidates) > 4000:
            raise GitError("W projekcie jest ponad 4000 zmienionych plików. "
                           "Najpierw dodaj .gitignore lub użyj Kate do wyboru plików.")
        if not candidates:
            return [], []
        dialog = FilesDialog(self, path, candidates, staged)
        self.wait_window(dialog)
        if dialog.result is None:
            return None
        return dialog.result, staged

    def final_selection_confirmation(self, path: Path, selected: list[str], staged: list[str],
                                     remote: str, message: str) -> bool:
        all_in_commit = sorted(set(selected).union(staged))
        warnings, blocked = safety_warnings(path, all_in_commit)
        if blocked:
            self.fail("GitHub nie przyjmuje zwykłych plików o rozmiarze 100 MiB lub więcej.\n"
                      "Usuń je z wyboru / historii albo skonfiguruj Git LFS:\n\n" +
                      "\n".join(blocked[:12]))
            return False
        # Warn especially about selected backups/secrets; never send without explicit consent.
        lines = "\n".join("• " + p for p in all_in_commit[:12])
        if len(all_in_commit) > 12:
            lines += f"\n…i jeszcze {len(all_in_commit) - 12} plików (wykaz był w oknie wyboru)"
        warning_text = ""
        if warnings:
            warning_text = "\n\nUWAGA:\n" + "\n".join("! " + s for s in warnings[:6])
            if len(warnings) > 6:
                warning_text += f"\n…oraz {len(warnings) - 6} kolejnych ostrzeżeń"
        return messagebox.askyesno(
            "Ostatnie potwierdzenie",
            f"Repozytorium:\n{remote}\n\nOpis Commit: {message}\n\n"
            f"Pliki do zatwierdzenia ({len(all_in_commit)}):\n{lines}"
            f"{warning_text}\n\nZatwierdzić lokalnie i wysłać na GitHuba?",
            parent=self,
        )

    def commit_and_push(self, path: Path, selected: list[str], message: str, first: bool) -> str:
        self.git.stage_paths(path, selected)
        lines: list[str] = []
        if self.git.staged_change_exists(path):
            result = self.git.run("commit", "-m", message, cwd=path)
            lines.append(result.text)
        elif not self.git.has_commits(path):
            raise GitError("Brak plików do pierwszego Commit. Niczego nie wysłano.")
        else:
            lines.append("Nie ma nowych zmian do Commit. Sprawdzam wysyłanie istniejących zatwierdzeń.")
        try:
            result = self.git.push(path)
            lines.append(result.text or "Git push zakończony sukcesem.")
        except GitError as exc:
            raise GitError("Zatwierdzenie lokalne zostało zapisane (jeżeli były zmiany), "
                           "ale wysyłanie na GitHuba nie powiodło się:\n\n" + str(exc)) from exc
        return "\n".join(lines)

    def upload_clicked(self) -> None:
        try:
            raw_path = self.upload_path.get().strip()
            if not raw_path:
                raise ValueError("Wskaż katalog projektu na komputerze.")
            path = Path(raw_path).expanduser().resolve()
            if not path.is_dir():
                raise ValueError("Katalog projektu nie istnieje: " + str(path))
            remote, _, _ = normalized_repo_url(self.upload_url.get())
            message = self.upload_message.get().strip()
            if not message:
                raise ValueError("Wpisz opis zmian (Commit).")
            existing_root = self.git.repo_root(path)
            if existing_root is not None and existing_root != path:
                raise ValueError("Projekt jest wewnątrz innego repozytorium Git:\n" + str(existing_root))
            current_remote = self.git.origin(path) if existing_root else None
            if current_remote and not same_github_repo(current_remote, remote):
                raise ValueError(
                    "Ten projekt jest już połączony z innym repozytorium:\n" +
                    current_remote + "\n\nNie zmieniam tego połączenia."
                )
            if not existing_root:
                if not messagebox.askyesno(
                        "Przygotowanie Git", "W tym katalogu nie ma jeszcze repozytorium Git.\n\n"
                        "Czy mogę utworzyć w nim katalog .git (bez usuwania plików)?",
                        parent=self):
                    return
                self.git.run("init", "-b", "main", cwd=path)
                self.log("Utworzono lokalne repozytorium Git w: " + str(path))
            if not current_remote:
                self.git.run("remote", "add", "origin", remote, cwd=path)
                self.log("Dodano adres origin: " + remote)
            files = self.pick_files(path)
            if files is None:
                self.log("Anulowano wybór plików. Istniejące pliki nie zostały zmienione.")
                return
            selected, staged = files
            if not selected and not staged and not self.git.has_commits(path):
                raise ValueError("Nie ma plików do pierwszej wersji projektu.")
            if not self.final_selection_confirmation(path, selected, staged, remote, message):
                return
        except (GitError, ValueError, OSError) as exc:
            self.fail(str(exc))
            return

        def task() -> str:
            return self.commit_and_push(path, selected, message, first=True)

        self.worker("Zatwierdzanie i wysyłanie " + path.name, task,
                    "Projekt wysłany na GitHuba: " + remote,
                    on_success=lambda: self.sync_path.set(str(path)))

    def status_clicked(self) -> None:
        try:
            path = self.require_repo(self.sync_path.get())
            state = self.git.status(path)
            remote = self.git.origin(path) or "(brak adresu origin)"
            self.log(f"Projekt: {path}\nGitHub: {remote}\nStan:\n{state}")
            self.status_var.set("Sprawdzono: " + path.name)
            messagebox.showinfo("Stan projektu", f"{path.name}\n\n{state}\n\nOrigin:\n{remote}", parent=self)
        except (ValueError, GitError) as exc:
            self.fail(str(exc))

    def pull_clicked(self) -> None:
        try:
            path = self.require_repo(self.sync_path.get())
            if not self.git.origin(path):
                raise GitError("Brak połączenia z GitHubem (origin).")
            if not self.git.has_commits(path):
                raise GitError("To repozytorium nie ma jeszcze pierwszego Commit.")
            if (self.git.run("diff", "--quiet", cwd=path, check=False).returncode != 0 or
                self.git.run("diff", "--cached", "--quiet", cwd=path, check=False).returncode != 0):
                raise GitError("Najpierw zatwierdź zmiany śledzonych plików. Pull mógłby je nadpisać.")
            if not messagebox.askyesno(
                    "Pobieranie zmian", f"Pobrać aktualizacje do projektu:\n{path}\n\n"
                    "Git wykona wyłącznie bezpieczne fast-forward.\n"
                    "Nie będzie wymuszonego scalania ani nadpisywania historii.",
                    parent=self):
                return
        except (GitError, ValueError) as exc:
            self.fail(str(exc))
            return

        self.worker("Pobieranie zmian do " + path.name,
                    lambda: self.git.pull(path).text,
                    "Zakończono pobieranie zmian: " + path.name)

    def sync_push_clicked(self) -> None:
        try:
            path = self.require_repo(self.sync_path.get())
            remote = self.git.origin(path)
            if not remote:
                raise GitError("Ten projekt nie ma adresu GitHub (origin).")
            message = self.sync_message.get().strip()
            if not message:
                raise ValueError("Wpisz opis zmian (Commit).")
            files = self.pick_files(path)
            if files is None:
                self.log("Anulowano wybór plików.")
                return
            selected, staged = files
            if not selected and not staged:
                if not self.git.has_commits(path):
                    raise GitError("Brak zmian i brak pierwszego Commit.")
                if not messagebox.askyesno(
                        "Brak zmian", "Nie ma nowych plików do Commit.\n"
                        "Sprawdzić i wysłać już zatwierdzone zmiany (Push)?", parent=self):
                    return
            elif not self.final_selection_confirmation(path, selected, staged, remote, message):
                return
        except (GitError, ValueError) as exc:
            self.fail(str(exc))
            return

        self.worker("Zatwierdzanie i wysyłanie zmian z " + path.name,
                    lambda: self.commit_and_push(path, selected, message, first=False),
                    "Zakończono wysyłanie na GitHuba: " + path.name)

    def open_kate_clicked(self) -> None:
        try:
            path = self.require_repo(self.sync_path.get())
            if shutil.which("kate") is None:
                raise ValueError("Nie znaleziono programu Kate. Zainstaluj go lub otwórz katalog ręcznie.")
            subprocess.Popen(["kate", str(path)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            self.log("Otworzono projekt w Kate: " + str(path))
        except (GitError, ValueError, OSError) as exc:
            self.fail(str(exc))


def main() -> int:
    try:
        app = App()
    except tk.TclError as exc:
        print(f"Nie można uruchomić okna graficznego: {exc}", file=sys.stderr)
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
