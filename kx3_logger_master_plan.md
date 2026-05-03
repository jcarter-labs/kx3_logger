# KX3 Logger — Prototype Master Plan
# TDD Development Plan for Claude Code

## Project Overview

Prototype ham radio contact logger for macOS (MacBook Air).
Rig: Elecraft KX3 via USB-Serial (FTDI/CH340 driver, pre-installed).
Language: Python 3. UI: tkinter. Log: CSV append. No database.

---

## Stack and Environment

- Python 3 (system or venv)
- tkinter (stdlib)
- pyserial (pip install pyserial)
- threading + queue (stdlib)
- csv (stdlib)
- datetime (stdlib, UTC only)
- No external frameworks

Serial device: /dev/cu.usbserial-* (enumerate at startup)
Baud: 4800, 8N1
CAT command: FA; (VFO A frequency)
Poll interval: 200ms
Timeout: 1.0s with single retry, then hold last known frequency

Log file: kx3_log.csv in same directory as script, append mode.
CSV fields (header row): timestamp_utc,callsign,operator,qth,comments,frequency_hz

---

## Architecture

### Module Layout

```
kx3_logger/
  main.py          # Entry point, launches GUI
  rig.py           # Serial/CAT interface, background polling thread
  logger.py        # CSV write logic
  ui.py            # tkinter GUI
  tests/
    test_rig.py
    test_logger.py
    test_ui.py
```

### Concurrency Model

- Main thread: tkinter event loop (blocking, must not be touched from worker)
- Worker thread: daemon thread in rig.py, polls FA; every 200ms
- IPC: queue.Queue(maxsize=1) — worker puts frequency string, UI reads via after() polling
- No shared mutable state outside the Queue
- On serial failure: log warning, hold last known value, keep retrying

### CAT Layer Design Note

Wrap all KX3-specific logic in a RigController base class or protocol.
KX3Controller subclasses it. Future rigs add new subclasses. No polymorphism
needed for prototype — just isolate KX3 logic cleanly for later extension.

---

## TDD Stages

---

### STAGE 1 — Rig Control (rig.py)

Goal: Verified serial communication and frequency polling before any UI.

#### Unit Tests (test_rig.py) — write tests first

1. test_parse_fa_response
   - Input: "FA00014225000;" → expect 14225000 (int, Hz)
   - Input: malformed / empty string → expect None or raise ValueError
   - Input: partial response (timeout sim) → expect None

2. test_serial_port_enumeration
   - Mock serial.tools.list_ports
   - Verify returns list of /dev/cu.* ports
   - Verify raises RuntimeError if none found

3. test_poll_populates_queue
   - Mock serial.Serial with canned FA; response
   - Instantiate RigController, start polling
   - Assert queue receives integer frequency within 500ms
   - Teardown: stop thread cleanly

4. test_serial_timeout_holds_last_value
   - Mock serial to raise serial.SerialTimeoutException on second call
   - Assert queue still contains last valid frequency after failed poll

5. test_thread_stops_cleanly
   - Call stop() on RigController
   - Assert thread joins within 1s
   - Assert no exception raised

#### Implementation Targets (rig.py)

- enumerate_ports() → list[str]
- RigController(port, queue, baud=4800)
  - start() — launches daemon thread
  - stop() — signals thread exit via threading.Event
  - _poll_loop() — private, 200ms interval, FA; query, parse, queue.put_nowait()
  - _send_cat(cmd: str) → str — send command, read until ";" with timeout
  - _parse_fa(response: str) → int — strip "FA", strip ";", return int

#### Failure Points

- /dev/cu.* vs /dev/tty.*: use cu exclusively
- KX3 response is NOT newline-terminated: read until ";" byte, not readline()
- Queue overflow: use put_nowait() with try/except Full; drop stale readings
- Thread leak: always set daemon=True and join on exit
- pyserial write requires bytes: send b"FA;" not "FA;"

#### Stage 1 Done Criteria

All 5 unit tests pass with mocked serial.
Manual integration test: script connects to KX3, prints frequency to stdout at 200ms intervals for 10 seconds without error.

---

### STAGE 2 — Scaffolding and UI (ui.py, main.py)

Goal: Functional tkinter window with all input fields and frequency display, wired to rig thread.

#### Unit Tests (test_ui.py) — write tests first

Note: tkinter testing is constrained. Use narrow unit tests on logic only;
avoid testing widget rendering directly.

1. test_frequency_display_formats_hz
   - Unit test a format_frequency(hz: int) → str helper
   - 14225000 → "14.225000 MHz"
   - None → "---"

2. test_callsign_validation
   - validate_callsign("W1AW") → True
   - validate_callsign("") → False
   - validate_callsign("123") → False (no letters)
   - Use simple regex: at least one letter and one digit

3. test_queue_drain_returns_latest
   - Put multiple values in queue rapidly
   - Verify UI polling helper returns most recent, discards stale

#### Implementation Targets (ui.py)

- MainWindow(tk.Tk)
  - Widgets: frequency display label (read-only), Entry fields for
    callsign, operator, qth, comments; Log button; Status bar
  - _poll_frequency() — called via self.after(200, ...) loop; drains queue; updates label
  - _on_log() — validates callsign not empty, calls logger.write_entry()
  - _clear_fields() — clears entries after successful log
  - Status bar: shows last log timestamp or serial error state

#### main.py

- enumerate_ports(); if multiple, present simple selection dialog
- Instantiate queue, RigController, MainWindow
- Wire RigController.start() before mainloop()
- On window close: call RigController.stop(), join thread, exit

#### Failure Points

- Never call tkinter methods from worker thread: all UI updates via after()
- Frequency label must not block: drain queue non-blocking (get_nowait)
- If serial never connects, UI must still be usable (frequency shows "---")
- macOS tkinter focus quirks: explicitly call window.lift() and focus_force() on startup

#### Stage 2 Done Criteria

Application launches, frequency updates in real time from KX3.
All entry fields accept input. Log button active. No crashes on serial disconnect.

---

### STAGE 3 — Log Functionality: Integration and Functional Testing (logger.py)

Goal: Verified end-to-end log write; integration test exercises full stack.

#### Unit Tests (test_logger.py) — write tests first

1. test_csv_header_written_on_create
   - Point logger at temp file (tmp_path fixture)
   - Assert first line matches expected header

2. test_entry_written_correctly
   - Call write_entry() with known values
   - Read CSV back; assert field values match exactly
   - Assert timestamp is valid ISO 8601 UTC

3. test_append_does_not_duplicate_header
   - Call write_entry() twice
   - Read CSV; assert exactly one header row

4. test_frequency_hz_written_as_integer
   - Assert frequency field is integer string, not float

5. test_missing_callsign_raises
   - Call write_entry() with empty callsign → expect ValueError

#### Implementation Targets (logger.py)

- LogWriter(filepath: str)
  - _ensure_header() — write header if file does not exist or is empty
  - write_entry(callsign, operator, qth, comments, frequency_hz: int) → None
    - Validates callsign not empty
    - Generates timestamp: datetime.utcnow().isoformat() + "Z"
    - Appends row; flushes immediately

#### Integration Test (manual, documented procedure)

1. Launch application with KX3 connected and on 14.225 MHz
2. Confirm frequency display shows 14225000 Hz (or formatted equivalent)
3. Enter: callsign=W1AW, operator=HIRAM, qth=NEWINGTON, comments=TEST
4. Click Log
5. Open kx3_log.csv; verify row present with correct fields and UTC timestamp
6. Change KX3 frequency to 7.074 MHz; confirm display updates within 400ms
7. Log second contact; verify two rows, one header, correct second frequency

#### Functional Test Criteria (Definition of Done)

- [ ] Application starts without error on macOS with KX3 connected
- [ ] Serial port auto-detected or user-selected at startup
- [ ] Frequency displays live from KX3 VFO A within 400ms of change
- [ ] All four text fields accept free-form input
- [ ] Log button writes one CSV row with all six fields
- [ ] Timestamp is UTC ISO 8601
- [ ] Frequency in Hz matches KX3 display
- [ ] CSV appends on subsequent runs; header not duplicated
- [ ] Application exits cleanly; no zombie threads

---

## Out of Scope (Do Not Implement)

- Multi-rig support (abstract only, no second rig implementation)
- ADIF export
- Dupe checking
- Contest scoring
- DX cluster integration
- Log upload (LOTW, QRZ, eQSL)
- SQLite or any database
- Configuration file / settings persistence
- Spot and bandmap features

---

## Notes for Claude Code

- Write tests before implementation in each stage.
- Do not proceed to Stage 2 until Stage 1 tests pass.
- Do not proceed to Stage 3 until Stage 2 tests pass.
- Use unittest (stdlib); do not introduce pytest unless explicitly requested.
- Mock serial.Serial using unittest.mock.patch for all serial unit tests.
- Keep all modules under 200 lines; refactor if exceeded.
- No global mutable state.
- All timestamps UTC only; never local time.
- pyserial is the only permitted third-party dependency.
