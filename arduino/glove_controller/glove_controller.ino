/*
 * ============================================================
 *  Hand Exoskeleton Glove Controller
 *  Author  : S. Sasmitha
 *  Hardware: Arduino Uno + 2x Servo Motors (3-finger tendon drive)
 *
 *  Servo Mapping:
 *    Servo 0 → Index + Middle fingers  (pin 3)
 *    Servo 1 → Ring finger             (pin 5)
 *
 *  Serial Protocol (9600 baud, newline-terminated):
 *    "S<angle>\n"       – set both servos to <angle> degrees (0-90)
 *    "F<0-1>,<angle>\n" – set individual servo
 *    "O\n"              – OPEN  hand (all servos → 0°)
 *    "C\n"              – CLOSE hand (all servos → 90°)
 *    "E\n"              – Emergency stop (all → 0° immediately)
 *    "H\n"              – Heartbeat ping → replies "HB_OK\n"
 *    "R\n"              – Read current angles → "ANGLES:0,0\n"
 *
 *  Safety Features:
 *    - Watchdog timer : auto-resets to OPEN if no command for 2000 ms
 *    - Rate limiting  : max 5° per 20 ms tick
 *    - Angle clamping : all angles clamped to [0, 90]
 *    - Emergency stop : 'E' command or voice command "stop"
 *
 *  Mechanical:
 *    OPEN  (0°)  → extended fingers
 *    CLOSE (90°) → flexed fingers, ~12.4 N peak grip force
 * ============================================================
 */

#include <Servo.h>

// ── Configuration ─────────────────────────────────────────────
#define N_SERVOS       2
#define SERVO_MIN      0
#define SERVO_MAX      90
#define RATE_LIMIT     5      // max degrees per 20 ms tick
#define WATCHDOG_MS    2000   // ms before auto-reset
#define UPDATE_MS      20     // servo update interval

// ── Pin assignments ───────────────────────────────────────────
const int SERVO_PINS[N_SERVOS] = {3, 5};

// ── Servo names ───────────────────────────────────────────────
const char SERVO_NAMES[N_SERVOS][14] = {
  "INDEX+MIDDLE",
  "RING"
};

// ── State ─────────────────────────────────────────────────────
Servo servos[N_SERVOS];
int   currentAngles[N_SERVOS] = {0, 0};
int   targetAngles[N_SERVOS]  = {0, 0};
long  lastCommandTime          = 0;
bool  emergencyStopped         = false;

// ── Helpers ───────────────────────────────────────────────────
int clampAngle(int val) {
  if (val < SERVO_MIN) return SERVO_MIN;
  if (val > SERVO_MAX) return SERVO_MAX;
  return val;
}

void setTargetAll(int angle) {
  angle = clampAngle(angle);
  for (int i = 0; i < N_SERVOS; i++) {
    targetAngles[i] = angle;
  }
}

void setTargetServo(int idx, int angle) {
  if (idx < 0 || idx >= N_SERVOS) return;
  targetAngles[idx] = clampAngle(angle);
}

void applyImmediateAll(int angle) {
  angle = clampAngle(angle);
  for (int i = 0; i < N_SERVOS; i++) {
    currentAngles[i] = angle;
    targetAngles[i]  = angle;
    servos[i].write(angle);
  }
}

/* Rate-limited step — called every UPDATE_MS */
void stepServos() {
  for (int i = 0; i < N_SERVOS; i++) {
    int diff = targetAngles[i] - currentAngles[i];
    if      (diff >  RATE_LIMIT) diff =  RATE_LIMIT;
    else if (diff < -RATE_LIMIT) diff = -RATE_LIMIT;
    currentAngles[i] += diff;
    servos[i].write(currentAngles[i]);
  }
}

void printAngles() {
  Serial.print("ANGLES:");
  for (int i = 0; i < N_SERVOS; i++) {
    Serial.print(currentAngles[i]);
    if (i < N_SERVOS - 1) Serial.print(",");
  }
  Serial.println();
}

// ── Command parser ────────────────────────────────────────────
void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  lastCommandTime = millis();
  char first = cmd.charAt(0);

  if (first == 'E') {
    // Emergency stop
    emergencyStopped = true;
    applyImmediateAll(SERVO_MIN);
    Serial.println("ESTOP_OK");

  } else if (first == 'H') {
    // Heartbeat
    Serial.println("HB_OK");

  } else if (first == 'O') {
    // Open hand
    emergencyStopped = false;
    setTargetAll(SERVO_MIN);
    Serial.println("OPEN_OK");

  } else if (first == 'C') {
    // Close hand
    emergencyStopped = false;
    setTargetAll(SERVO_MAX);
    Serial.println("CLOSE_OK");

  } else if (first == 'R') {
    // Read current angles
    printAngles();

  } else if (first == 'S') {
    // Set all servos to angle
    if (!emergencyStopped) {
      int angle = clampAngle(cmd.substring(1).toInt());
      setTargetAll(angle);
      Serial.print("ACK_ALL:");
      Serial.println(angle);
    }

  } else if (first == 'F') {
    // Set individual servo: "F<index>,<angle>"
    if (!emergencyStopped) {
      int comma = cmd.indexOf(',');
      if (comma > 1) {
        int idx   = cmd.substring(1, comma).toInt();
        int angle = clampAngle(cmd.substring(comma + 1).toInt());
        setTargetServo(idx, angle);
        Serial.print("ACK_F");
        Serial.print(idx);
        Serial.print(":");
        Serial.println(angle);
      }
    }
  }
}

// ── Setup ─────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);

  for (int i = 0; i < N_SERVOS; i++) {
    servos[i].attach(SERVO_PINS[i]);
    servos[i].write(SERVO_MIN);   // start OPEN
  }

  lastCommandTime = millis();
  delay(500);

  Serial.println("GLOVE_READY");
  Serial.print("SERVOS:");
  for (int i = 0; i < N_SERVOS; i++) {
    Serial.print(SERVO_NAMES[i]);
    if (i < N_SERVOS - 1) Serial.print(",");
  }
  Serial.println();
}

// ── Main loop ─────────────────────────────────────────────────
void loop() {
  // Read serial command
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }

  // Watchdog — reset if comms lost
  if (!emergencyStopped &&
      (millis() - lastCommandTime > WATCHDOG_MS)) {
    applyImmediateAll(SERVO_MIN);
    Serial.println("WATCHDOG_RESET");
    lastCommandTime = millis();
  }

  // Smooth servo motion
  stepServos();
  delay(UPDATE_MS);
}
