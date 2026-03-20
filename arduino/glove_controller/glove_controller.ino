/*
 * ============================================================
 *  Hand Exoskeleton Glove Controller
 *  Author  : S. Sasmitha
 *  Hardware: Arduino Uno + 5x MG996R Servo Motors
 *  Paper   : "Development of an Intelligent Sorting Game with
 *             Real-Time Hand Gesture Control and MySQL
 *             Performance Analytics"
 * ============================================================
 *
 *  Serial Protocol (9600 baud, newline-terminated):
 *    "S<angle>\n"  – set all 5 fingers to <angle> degrees (0-90)
 *    "F<0-4>,<angle>\n" – set individual finger
 *    "O\n"         – OPEN  hand (all servos → 0°)
 *    "C\n"         – CLOSE hand (all servos → 90°)
 *    "E\n"         – Emergency stop (all → 0° immediately)
 *    "H\n"         – Heartbeat ping → replies "HB_OK\n"
 *    "R\n"         – Read current angles → "ANGLES:0,0,0,0,0\n"
 *
 *  Safety Features:
 *    - Watchdog timer: auto-resets to OPEN if no command for WATCHDOG_MS
 *    - Rate limiting:  max RATE_LIMIT_DEG per 20ms tick
 *    - Angle clamping: all angles clamped to [SERVO_MIN, SERVO_MAX]
 *    - Emergency stop: keyboard shortcut + voice command "stop"
 *
 *  Servo Mapping (paper Fig. 4):
 *    Servo 0 → Thumb    (pin 3)
 *    Servo 1 → Index    (pin 5)
 *    Servo 2 → Middle   (pin 6)
 *    Servo 3 → Ring     (pin 9)
 *    Servo 4 → Pinky    (pin 10)
 *
 *  Mechanical results (paper Section IV-C):
 *    OPEN   (0°)  → extended fingers
 *    CLOSE  (90°) → flexed fingers, peak grip force ~12.4 N
 *    Linear flex: ~0.83° finger flexion per 1° servo rotation
 * ============================================================
 */

#include <Servo.h>

// ── Pin assignments ──────────────────────────────────────────
const int SERVO_PINS[5]  = {3, 5, 6, 9, 10};
const char FINGER_NAMES[5][7] = {"THUMB","INDEX","MIDDL","RING ","PINKY"};

// ── Safety / motion constants ────────────────────────────────
const int  SERVO_MIN       =  0;    // degrees
const int  SERVO_MAX       = 90;    // degrees  (paper max)
const int  RATE_LIMIT      =  5;    // max deg per 20 ms tick
const long WATCHDOG_MS     = 2000;  // ms — reset on lost comms
const int  UPDATE_INTERVAL = 20;    // ms per servo update cycle

// ── State ────────────────────────────────────────────────────
Servo servos[5];
int   currentAngles[5] = {0, 0, 0, 0, 0};
int   targetAngles[5]  = {0, 0, 0, 0, 0};
long  lastCommandTime  = 0;
bool  emergencyStopped = false;

// ── Helpers ──────────────────────────────────────────────────
int clamp(int val, int lo, int hi) {
  if (val < lo) return lo;
  if (val > hi) return hi;
  return val;
}

void setTargetAll(int angle) {
  angle = clamp(angle, SERVO_MIN, SERVO_MAX);
  for (int i = 0; i < 5; i++) targetAngles[i] = angle;
}

void setTargetFinger(int finger, int angle) {
  if (finger < 0 || finger > 4) return;
  targetAngles[finger] = clamp(angle, SERVO_MIN, SERVO_MAX);
}

void applyImmediateAll(int angle) {
  angle = clamp(angle, SERVO_MIN, SERVO_MAX);
  for (int i = 0; i < 5; i++) {
    currentAngles[i] = angle;
    targetAngles[i]  = angle;
    servos[i].write(angle);
  }
}

/* Rate-limited step towards target — called every UPDATE_INTERVAL ms */
void stepServos() {
  for (int i = 0; i < 5; i++) {
    int diff = targetAngles[i] - currentAngles[i];
    if      (diff >  RATE_LIMIT) diff =  RATE_LIMIT;
    else if (diff < -RATE_LIMIT) diff = -RATE_LIMIT;
    currentAngles[i] += diff;
    servos[i].write(currentAngles[i]);
  }
}

void printAngles() {
  Serial.print("ANGLES:");
  for (int i = 0; i < 5; i++) {
    Serial.print(currentAngles[i]);
    if (i < 4) Serial.print(",");
  }
  Serial.println();
}

// ── Command parser ────────────────────────────────────────────
void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  lastCommandTime = millis();
  char first = cmd.charAt(0);

  if (first == 'E') {                         // Emergency stop
    emergencyStopped = true;
    applyImmediateAll(SERVO_MIN);
    Serial.println("ESTOP_OK");

  } else if (first == 'H') {                  // Heartbeat
    Serial.println("HB_OK");

  } else if (first == 'O') {                  // Open hand
    emergencyStopped = false;
    setTargetAll(SERVO_MIN);
    Serial.println("OPEN_OK");

  } else if (first == 'C') {                  // Close hand
    emergencyStopped = false;
    setTargetAll(SERVO_MAX);
    Serial.println("CLOSE_OK");

  } else if (first == 'R') {                  // Read angles
    printAngles();

  } else if (first == 'S') {                  // Set all to angle
    if (!emergencyStopped) {
      int angle = cmd.substring(1).toInt();
      setTargetAll(angle);
      Serial.print("ACK_ALL:");
      Serial.println(clamp(angle, SERVO_MIN, SERVO_MAX));
    }

  } else if (first == 'F') {                  // Set individual finger
    // Format: F<finger>,<angle>
    if (!emergencyStopped) {
      int comma  = cmd.indexOf(',');
      if (comma > 1) {
        int finger = cmd.substring(1, comma).toInt();
        int angle  = cmd.substring(comma + 1).toInt();
        setTargetFinger(finger, angle);
        Serial.print("ACK_F");
        Serial.print(finger);
        Serial.print(":");
        Serial.println(clamp(angle, SERVO_MIN, SERVO_MAX));
      }
    }
  }
}

// ── Setup ─────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);

  // Attach servos and initialise to OPEN (0°)
  for (int i = 0; i < 5; i++) {
    servos[i].attach(SERVO_PINS[i]);
    servos[i].write(0);
  }

  lastCommandTime = millis();

  // Startup handshake
  delay(500);
  Serial.println("GLOVE_READY");
  Serial.print("FINGERS:");
  for (int i = 0; i < 5; i++) {
    Serial.print(FINGER_NAMES[i]);
    if (i < 4) Serial.print(",");
  }
  Serial.println();
}

// ── Main loop ──────────────────────────────────────────────────
void loop() {
  // ── Parse serial input ───────────────────────────────────────
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }

  // ── Watchdog ─────────────────────────────────────────────────
  if (!emergencyStopped &&
      (millis() - lastCommandTime > WATCHDOG_MS)) {
    applyImmediateAll(SERVO_MIN);
    Serial.println("WATCHDOG_RESET");
    lastCommandTime = millis();
  }

  // ── Rate-limited servo update ─────────────────────────────────
  stepServos();
  delay(UPDATE_INTERVAL);
}
