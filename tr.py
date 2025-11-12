# tr.py
# pip install pygetwindow

import argparse, ctypes, pygetwindow as gw
from ctypes import wintypes

# ---- Constantes Win32 ----
GWL_EXSTYLE       = -20
WS_EX_LAYERED     = 0x00080000
WS_EX_TRANSPARENT = 0x00000020     # ignora cliques (passa-através)
LWA_ALPHA         = 0x00000002
SW_RESTORE        = 9

user32 = ctypes.windll.user32
GetWindowLongW = user32.GetWindowLongW
SetWindowLongW = user32.SetWindowLongW
SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
ShowWindow = user32.ShowWindow

def list_windows():
    titles = sorted(set([t for t in gw.getAllTitles() if t.strip()]))
    print("Janelas abertas:")
    for t in titles:
        print(" -", t)

def find_windows_by_title(substr: str):
    subs = (substr or "").lower()
    return [w for w in gw.getAllWindows() if subs in (w.title or "").lower()]

def pick_best_window(wins):
    # preferência: começa com "Tibia -", não minimizada; senão a primeira
    for w in wins:
        if (w.title or "").lower().startswith("tibia -") and not w.isMinimized:
            return w
    for w in wins:
        if not w.isMinimized:
            return w
    return wins[0] if wins else None

def ensure_visible(hwnd):
    try:
        ShowWindow(hwnd, SW_RESTORE)
    except Exception:
        pass

def set_transparency(hwnd, opacity, click_through=False):
    alpha = max(0, min(255, int(opacity)))
    exstyle = GetWindowLongW(hwnd, GWL_EXSTYLE)
    exstyle |= WS_EX_LAYERED
    if click_through:
        exstyle |= WS_EX_TRANSPARENT
    else:
        exstyle &= ~WS_EX_TRANSPARENT
    SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)
    ok = SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
    return ok != 0

def reset_transparency(hwnd):
    exstyle = GetWindowLongW(hwnd, GWL_EXSTYLE)
    exstyle &= ~WS_EX_LAYERED
    exstyle &= ~WS_EX_TRANSPARENT
    SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)

def main():
    ap = argparse.ArgumentParser(description="Transparência de janela (Windows).")
    ap.add_argument("--title", "-t", default="Tibia",
                    help="Trecho do título da janela (padrão: 'Tibia').")
    ap.add_argument("--opacity", "-o", type=int, default=135,
                    help="0..255 (0 invisível, 255 opaco).")
    ap.add_argument("--clickthrough", "-c", action="store_true",
                    help="Janela ignora cliques (passa-através).")
    ap.add_argument("--reset", "-r", action="store_true",
                    help="Remover transparência.")
    ap.add_argument("--list", "-l", action="store_true",
                    help="Listar janelas e sair.")
    ap.add_argument("--index", "-i", type=int, default=None,
                    help="Índice quando várias janelas baterem (0-based).")
    args = ap.parse_args()

    if args.list:
        list_windows()
        return

    matches = find_windows_by_title(args.title)
    if not matches:
        print("❌ Janela não encontrada. Use --list para ver títulos.")
        return

    win = matches[args.index] if args.index is not None else pick_best_window(matches)
    hwnd = win._hWnd
    ensure_visible(hwnd)

    if args.reset:
        reset_transparency(hwnd)
        print(f"✅ Transparência removida de: {win.title}")
        return

    if set_transparency(hwnd, args.opacity, args.clickthrough):
        print(f"✅ Aplicado em '{win.title}': opacity={args.opacity}/255, click_through={args.clickthrough}")
    else:
        print("⚠️ Falha ao aplicar. Tente rodar o Python como Administrador.")

if __name__ == "__main__":
    main()
