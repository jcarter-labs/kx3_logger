# KX3 Logger

A lightweight ham radio contact logger for the Elecraft KX3 on macOS.
Polls VFO A frequency via USB-Serial CAT, displays it live, and appends
contacts to a CSV log file.

---

## Requirements

- macOS (tested on MacBook Air)
- Python 3
- pyserial (`pip install pyserial`)
- KX3 connected via USB (FTDI/CH340 driver pre-installed)

---

## Setup

```bash
git clone git@github.com:jcarter-labs/kx3_logger.git
cd kx3_logger
python3 -m venv .venv
source .venv/bin/activate
pip install pyserial
```

---

## Run

```bash
source .venv/bin/activate
python main.py
```

The app auto-detects `/dev/cu.usbserial-*` at startup. If multiple ports
are found, a selection dialog appears.

---

## Calling Diagram

```
main.py
├── enumerate_ports()          [rig.py]
│     └── serial.tools.list_ports  [pyserial - external]
│
├── queue.Queue()              [stdlib]
│
├── RigController(port, queue) [rig.py]
│     └── start()
│           └── _poll_loop()       [daemon thread]
│                 ├── _send_cat()
│                 │     └── serial.Serial  [pyserial - external / KX3 hardware]
│                 └── _parse_fa()
│                       └── queue.put_nowait()
│
└── MainWindow(queue)          [ui.py]
      ├── _poll_frequency()        [via tkinter after() loop]
      │     └── queue.get_nowait()
      │
      ├── _on_log()
      │     └── LogWriter.write_entry()  [logger.py]
      │           └── kx3_log.csv        [filesystem]
      │
      └── mainloop()               [tkinter - external]

On window close:
  └── RigController.stop()     [rig.py]
        └── thread.join()
```

---

## Log File

Appended to `kx3_log.csv` in the project directory.

```
timestamp_utc,callsign,operator,qth,comments,frequency_hz
2026-05-03T14:32:00Z,W1AW,HIRAM,NEWINGTON,TEST,14225000
```

---

## Project Status

- [x] Stage 1 — Serial/CAT layer (`rig.py`) — unit tests passing
- [ ] Stage 2 — UI (`ui.py`, `main.py`)
- [ ] Stage 3 — Log functionality (`logger.py`)

---

## Out of Scope

ADIF export, dupe checking, contest scoring, DX cluster, log upload,
SQLite, configuration persistence.
