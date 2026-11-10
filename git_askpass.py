#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Małe, odrębne okno autoryzacji Git. Nie zapisuje haseł ani tokenów."""
import sys
import tkinter as tk
from tkinter import simpledialog

prompt = sys.argv[1] if len(sys.argv) > 1 else "GitHub — uwierzytelnianie"
root = tk.Tk()
root.withdraw()
try:
    is_secret = any(word in prompt.lower() for word in ("password", "passphrase", "token"))
    answer = simpledialog.askstring("Git — autoryzacja", prompt,
                                    show="*" if is_secret else None, parent=root)
    if answer is None:
        raise SystemExit(1)
    print(answer)
finally:
    root.destroy()
