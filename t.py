# t2_retry.py — PyAutoGUI + Pro Micro — fluxo pedido (right-click automático em upboatthais.png)

import os
import time
import pyautogui as pg
import serial

print("PyAutoGUI + Pro Micro — fluxo solicitado")

# ===== AJUSTES =====
COM_PORT = "COM13"          # troque para sua porta (ex.: "COM7", "/dev/ttyACM0")
BAUD     = 115200

# Detecção de imagem:
CONF              = 0.78
LOCATE_TIMEOUT    = 8.0         # por tentativa
LOCATE_POLL_S     = 0.15
MISS_RETRY_GAP_S  = 5.0         # espera entre re-tentativas
MISS_MAX_RETRIES  = 6           # nº de re-tentativas após a primeira busca

# Movimento fino via Pro Micro:
PAUSE_MS          = 16
STEP_CAP          = 12
MAX_CENTER_TIME   = 6.0

# PyAutoGUI
pg.FAILSAFE = True
pg.PAUSE    = 0

# Imagens que devem receber CLIQUE DIREITO
RIGHT_CLICK_SET = {"upboatthais.png", "upc1.png", "upc2.png", "upab1.png", "upab2.png", "upab3.png", "upab4.png", "upab5.png", "upboatab.png"}

# ===== UTIL =====
def wait_exact(seconds, label=None, show_result=True):
    start = time.monotonic(); end = start + seconds
    while True:
        rem = end - time.monotonic()
        if rem <= 0: break
        time.sleep(min(0.25, rem))
    if show_result and seconds >= 1:
        real = time.monotonic() - start
        if label: print(f"… {label}: esperado {seconds:.2f}s, real {real:.2f}s")
        else:     print(f"… esperado {seconds:.2f}s, real {real:.2f}s")

def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v

def wait_ready(ser, timeout=2.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        line = ser.readline().decode(errors="ignore").strip()
        if line in ("READY", "OK"): return True
    return False

def send_line(ser, s: str, timeout=1.2, retries=2):
    for _ in range(retries + 1):
        try: ser.reset_input_buffer()
        except Exception: pass
        ser.write((s + "\n").encode("ascii"))
        ser.flush()
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            resp = ser.readline().decode(errors="ignore").strip()
            if resp == "OK": return True
            if resp.startswith("ERR"):
                print("Arduino:", resp); break
    print("Arduino: sem ACK para", s)
    return False

def move_to_exact(ser, tx, ty, pause_ms=PAUSE_MS, step_cap=STEP_CAP, max_time_s=MAX_CENTER_TIME):
    t0 = time.monotonic()
    last = pg.position()
    stuck_cnt = 0
    while time.monotonic() - t0 < max_time_s:
        rx, ry = pg.position()
        dx, dy = tx - rx, ty - ry
        if dx == 0 and dy == 0: return True

        dist = max(abs(dx), abs(dy))
        base = max(1, dist // 6)
        mag  = min(step_cap, base)

        ddx = clamp(dx, -mag, mag)
        ddy = clamp(dy, -mag, mag)

        if not send_line(ser, f"R {ddx} {ddy}"): return False
        wait_exact(pause_ms / 1000.0, show_result=False)

        cur = pg.position()
        if cur == last:
            stuck_cnt += 1
            if stuck_cnt >= 4 and mag > 1:
                stepx = 0 if dx == 0 else (1 if dx > 0 else -1)
                stepy = 0 if dy == 0 else (1 if dy > 0 else -1)
                for _ in range(mag):
                    if not send_line(ser, f"R {stepx} {stepy}"): return False
                    wait_exact(0.006, show_result=False)
                stuck_cnt = 0
        else:
            stuck_cnt = 0
            last = cur
    return False

def resolve_img(path):
    abspath = os.path.abspath(path)
    if not os.path.exists(abspath):
        print(f"❌ Arquivo de imagem não encontrado: {abspath}")
    return abspath

def locate_center_once(path, confidence=CONF, timeout=LOCATE_TIMEOUT, poll=LOCATE_POLL_S):
    base = os.path.basename(path)
    path = resolve_img(path)
    print(f"[BUSCA] {base} (timeout {timeout:.1f}s) — tela inteira")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        c = None
        try: c = pg.locateCenterOnScreen(path, confidence=confidence)
        except Exception: c = None
        if not c:
            try: c = pg.locateCenterOnScreen(path)
            except Exception: c = None
        if not c:
            try: c = pg.locateCenterOnScreen(path, confidence=confidence, grayscale=True)
            except Exception: c = None
        if c:
            return int(c.x), int(c.y)
        wait_exact(poll, show_result=False)
    return None

def locate_with_retry(path, retries=MISS_MAX_RETRIES, gap_s=MISS_RETRY_GAP_S):
    pos = locate_center_once(path)
    if pos: return pos
    for i in range(retries):
        print(f"✗ Não encontrado. Aguardando {gap_s:.0f}s e tentando novamente ({i+1}/{retries})…")
        wait_exact(gap_s, label="retry-gap")
        pos = locate_center_once(path)
        if pos: return pos
    return None

def move_click_flag(ser, img_path, wait_after_click_s):
    """
    Mantém a assinatura original. upboatthais.png é clicado com botão direito automaticamente.
    """
    pos = locate_with_retry(img_path)
    if not pos:
        print(f"✗ Não encontrei {img_path} após novas verificações. Abortando.")
        return False

    x, y = pos
    base = os.path.basename(img_path).lower()
    click = 'right' if base in RIGHT_CLICK_SET else 'left'
    print(f"✓ {img_path} em ({x},{y}) — centralizando e clicando ({click})...")

    send_line(ser, "B1")
    if not move_to_exact(ser, x, y):
        print("Falha ao centralizar (timeout).")
        send_line(ser, "B0")
        return False

    wait_exact(0.05, show_result=False)
    if click == 'left':
        send_line(ser, "C")
    else:
        send_line(ser, "CR")

    send_line(ser, "B0")

    if wait_after_click_s > 0:
        print(f"… aguardando {wait_after_click_s}s")
        wait_exact(wait_after_click_s, label=img_path)
    return True

def alt_click_flag(ser, img_path):
    pos = locate_with_retry(img_path)
    if not pos:
        print(f"✗ Não encontrei {img_path} após novas verificações. Abortando ALT+clique.")
        return False
    x, y = pos
    print(f"✓ {img_path} para ALT+clique em ({x},{y})")

    send_line(ser, "B1")
    if not move_to_exact(ser, x, y):
        print("Falha ao centralizar (ALT+clique).")
        send_line(ser, "B0")
        return False

    wait_exact(0.05, show_result=False)
    send_line(ser, "AC")
    send_line(ser, "B0")
    return True

# ===== sequências de teclado =====
def type_sequence(ser):
    # ENTER -> 'spiritual' -> ENTER -> ENTER -> 'yes' -> ENTER -> ESC
    send_line(ser, "KE ENTER");     wait_exact(0.50, show_result=False)
    send_line(ser, "KT spiritual"); wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");     wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");     wait_exact(1.00, show_result=False)
    send_line(ser, "KT yes");       wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");     wait_exact(0.50, show_result=False)
    send_line(ser, "KE ESC");       wait_exact(0.50, show_result=False)

def type_sequence1(ser):
    # ENTER -> 'hi' -> ENTER -> 'carlin' -> ENTER -> ENTER -> 'yes'
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT hi");     wait_exact(2.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT carlin"); wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KT yes");    wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)

def type_sequence2(ser):
    # ENTER -> 'hi' -> ENTER -> 'carlin' -> ENTER -> ENTER -> 'yes'
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT hi");     wait_exact(2.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT embrace"); wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KT yes");    wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)

def type_sequence3(ser):
    # ENTER -> 'hi' -> ENTER -> 'carlin' -> ENTER -> ENTER -> 'yes'
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT hi");     wait_exact(2.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT ab'dendriel"); wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KT yes");    wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)

def type_sequence4(ser):
    # ENTER -> 'hi' -> ENTER -> 'carlin' -> ENTER -> ENTER -> 'yes'
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT hi");     wait_exact(2.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT fire"); wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KT yes");    wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)

def type_sequence5(ser):
    # ENTER -> 'hi' -> ENTER -> 'carlin' -> ENTER -> ENTER -> 'yes'
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT hi");     wait_exact(2.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(1.00, show_result=False)
    send_line(ser, "KT edron"); wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)
    send_line(ser, "KT yes");    wait_exact(1.00, show_result=False)
    send_line(ser, "KE ENTER");  wait_exact(0.50, show_result=False)

# ===== FLUXO PRINCIPAL (exatamente como você pediu) =====
def main():
    input("Prepare a janela do jogo. ENTER para iniciar...")
    try:
        with serial.Serial(COM_PORT, BAUD, timeout=1) as ser:
            wait_exact(1.8, show_result=False)  # 32u4 pode resetar
            ser.reset_input_buffer()
            wait_ready(ser, 1.0)

            # ---- ida thais ----
            # if not move_click_flag(ser, "flag1.png", 19):   return
            # if not move_click_flag(ser, "flag2.png", 38):  return
            # if not move_click_flag(ser, "flag3.png", 10):  return
            # if not move_click_flag(ser, "sqm1.png", 5):    return

            # ALT+clique + sequência (flag6)
            #if not alt_click_flag(ser, "norf.png"):  return
            #type_sequence(ser)  # <-- só segue após ESC ter sido enviado

            # flag7 (+10s)
            #if not move_click_flag(ser, "escdown.png", 10): return

            # ---- volta ----
            #if not move_click_flag(ser, "flag2.png", 56): return
            #if not move_click_flag(ser, "flag1.png", 19):  return

            # ida pro dp/barco
            #if not move_click_flag(ser, "flag5.png", 19):  return
            #if not move_click_flag(ser, "flag4.png", 10):  return
            #if not move_click_flag(ser, "upboatthais.png", 5):   return  # right-click automático
            #if not move_click_flag(ser, "flag1.png", 8):  return
            #type_sequence1(ser)  # <-- só segue após ESC ter sido enviado
            
            # ida carlin
            #if not move_click_flag(ser, "flag1.png", 8):  return
            #if not move_click_flag(ser, "flag2.png", 35):   return
            #if not move_click_flag(ser, "flag3.png", 25):   return
            #if not move_click_flag(ser, "upc1.png", 5):   return  # right-click automático
            
            #npc
            #if not move_click_flag(ser, "sqmcarlin.png", 12):  return
            #type_sequence2(ser)  # <-- só segue após ESC ter sido enviado

            #volta barco carlin
            #if not move_click_flag(ser, "flag5.png", 20):  return
            #if not move_click_flag(ser, "flag2.png", 20):   return
            #if not move_click_flag(ser, "flag1.png", 20):   return
            #if not move_click_flag(ser, "upc2.png", 5):   return  # right-click automático
            #if not move_click_flag(ser, "flag5.png", 8):  return
            #type_sequence3(ser)  # <-- só segue após ESC ter sido enviado

            # ida ab'dendriel
            #if not move_click_flag(ser, "flag1.png", 5):  return
            #if not move_click_flag(ser, "flag2.png", 68):   return
            #if not move_click_flag(ser, "upab1.png", 3):   return  # right-click automático
            #if not move_click_flag(ser, "upab2.png", 3):   return  # right-click automático
            #if not move_click_flag(ser, "upab3.png", 3):   return  # right-click automático
            #if not move_click_flag(ser, "upab4.png", 3):   return  # right-click automático
            #if not move_click_flag(ser, "upab5.png", 3):   return  # right-click automático

            #npc ab'dendriel
            #if not move_click_flag(ser, "flag1.png", 8):  return
            #type_sequence4(ser)  # <-- só segue após ESC ter sido enviado
            #if not move_click_flag(ser, "bye.png", 8):  return

            #volta barco ab'dendriel
            if not move_click_flag(ser, "dab1.png", 3):  return
            if not move_click_flag(ser, "flag1.png", 3):   return
            if not move_click_flag(ser, "flag1.png", 3):   return
            if not move_click_flag(ser, "flag1.png", 3):   return
            if not move_click_flag(ser, "flag5.png", 3):   return
            if not move_click_flag(ser, "flag3.png", 60):   return
            if not move_click_flag(ser, "upboatab.png", 5):   return  # right-click automático
            if not move_click_flag(ser, "flag4.png", 8):  return
            type_sequence5(ser)  # <-- só segue após ESC ter sido enviado

    except serial.SerialException as e:
        print("Erro ao abrir porta serial:", e)
        return
    except KeyboardInterrupt:
        print("\n⚠️ Cancelado pelo usuário (Ctrl+C).")

    print("✔️ Sequência finalizada.")

if __name__ == "__main__":
    main()
