#include <Mouse.h>
#include <Keyboard.h>

// ===== LED (Leonardo/Pro Micro) =====
// Se a placa tiver macros RXLED0/RXLED1 (32u4), usamos elas.
// Caso contrário, caímos no LED_BUILTIN.
#if defined(RXLED0) && defined(RXLED1)
  inline void LED_ON_CALL()  { RXLED0; }  // ativo-baixo (acende)
  inline void LED_OFF_CALL() { RXLED1; }  // apaga
  #define USE_RX_LED 1
#else
  #define LED_PIN LED_BUILTIN
  inline void LED_ON_CALL()  { digitalWrite(LED_PIN, HIGH); }
  inline void LED_OFF_CALL() { digitalWrite(LED_PIN, LOW);  }
  #define USE_RX_LED 0
#endif

bool running = false;
bool ledOn    = false;           // <<< nome correto (não use 'ledIsOn')
unsigned long lastBlink = 0;
const unsigned long BLINK_MS = 500;

static inline int clamp(int v, int lo, int hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

void ledSolidOn()  { LED_ON_CALL();  ledOn = true;  }
void ledSolidOff() { LED_OFF_CALL(); ledOn = false; }
void ledToggle()   { if (ledOn) { LED_OFF_CALL(); ledOn = false; } else { LED_ON_CALL(); ledOn = true; } }

void ledBlinkTick(unsigned long now){
  if (running) {                 // ativo = LED fixo aceso
    if (!ledOn) ledSolidOn();
    return;
  }
  if (now - lastBlink >= BLINK_MS) {   // ocioso = piscando
    ledToggle();
    lastBlink = now;
  }
}

void setup() {
#if !USE_RX_LED
  pinMode(LED_PIN, OUTPUT);
#endif
  ledSolidOff();

  Serial.begin(115200);
  Serial.setTimeout(100);
  delay(1200);                 // tempo para enumerar a CDC no Windows

  Mouse.begin();
  Keyboard.begin();

  Serial.println(F("READY"));
}

void loop() {
  ledBlinkTick(millis());

  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  // Protocolo:
  //   B1 / B0                      -> LED estado (rodando/ocioso)
  //   R dx dy                      -> move relativo [-127..127]
  //   C                            -> clique esquerdo
  //   CR (ou RC)                   -> clique direito
  //   AC                           -> Alt + clique esquerdo
  //   KE <KEY>                     -> tecla especial (ENTER, ESC, TAB, SPACE, UP, DOWN, LEFT, RIGHT, BKSP)
  //   KT <texto>                   -> digitar texto (ASCII simples)
  // Retorna "OK" ou "ERR CMD"

  // -------- estados de LED ----------
  if (line == "B1") {
    running = true;
    ledSolidOn();
    Serial.println(F("OK"));
    return;
  }
  if (line == "B0") {
    running = false;
    ledSolidOff(); // volta a piscar no próximo tick
    Serial.println(F("OK"));
    return;
  }

  // -------- movimento relativo ----------
  if (line.startsWith("R ")) {
    int sp1 = line.indexOf(' ');
    int sp2 = (sp1 >= 0) ? line.indexOf(' ', sp1 + 1) : -1;
    if (sp1 <= 0 || sp2 <= sp1) { Serial.println(F("ERR CMD")); return; }

    int dx = line.substring(sp1 + 1, sp2).toInt();
    int dy = line.substring(sp2 + 1).toInt();
    dx = clamp(dx, -127, 127);
    dy = clamp(dy, -127, 127);

    Mouse.move((int8_t)dx, (int8_t)dy, 0);
    Serial.println(F("OK"));
    return;
  }

  // -------- clique esquerdo ----------
  if (line == "C" || line == "c") {
    Mouse.press(MOUSE_LEFT);
    delay(50);
    Mouse.release(MOUSE_LEFT);
    Serial.println(F("OK"));
    return;
  }

  // -------- clique direito ----------
  if (line == "CR" || line == "RC") {
    Mouse.press(MOUSE_RIGHT);
    delay(50);
    Mouse.release(MOUSE_RIGHT);
    Serial.println(F("OK"));
    return;
  }

  // -------- Alt + clique esquerdo ----------
  if (line == "AC") {
    Keyboard.press(KEY_LEFT_ALT);
    delay(10);
    Mouse.press(MOUSE_LEFT);
    delay(50);
    Mouse.release(MOUSE_LEFT);
    Keyboard.release(KEY_LEFT_ALT);
    Serial.println(F("OK"));
    return;
  }

  // -------- teclas especiais ----------
  if (line.startsWith("KE ")) {
    String key = line.substring(3);
    key.trim();
    uint8_t k = 0;

    if (key == "ENTER") k = KEY_RETURN;
    else if (key == "ESC") k = KEY_ESC;
    else if (key == "TAB") k = KEY_TAB;
    else if (key == "SPACE") k = ' ';
    else if (key == "UP") k = KEY_UP_ARROW;
    else if (key == "DOWN") k = KEY_DOWN_ARROW;
    else if (key == "LEFT") k = KEY_LEFT_ARROW;
    else if (key == "RIGHT") k = KEY_RIGHT_ARROW;
    else if (key == "BKSP" || key == "BACKSPACE") k = KEY_BACKSPACE;

    if (k == 0) { Serial.println(F("ERR CMD")); return; }

    Keyboard.press(k);
    delay(10);
    Keyboard.release(k);
    Serial.println(F("OK"));
    return;
  }

  // -------- digitar texto ----------
  if (line.startsWith("KT ")) {
    String txt = line.substring(3);
    for (size_t i = 0; i < txt.length(); i++) {
      Keyboard.write((uint8_t)txt[i]); // ASCII simples
      delay(2);
    }
    Serial.println(F("OK"));
    return;
  }

  Serial.println(F("ERR CMD"));
}
