# Serial Studio plugin for Claude

Read live telemetry and operate a running [Serial Studio](https://serial-studio.com) instance
from Claude Code or Cowork. The plugin connects Claude to the MCP server built into Serial
Studio: every API command becomes a tool with a title and read-only or destructive hints, the
latest telemetry frame is a resource, and a bundled skill tells Claude what has to be true
first and the safe order of work.

## What it does

- **Tools.** More than 440 Serial Studio commands: connection status and control, driver
  settings for UART, network, Bluetooth LE, Modbus, CAN Bus, OPC UA, S7, EtherNet/IP and
  IEC 104 sources, dashboard reads, project editing, exports, the Historian and alarms.
  Reads carry `readOnlyHint`; the delete, clear, open-replace, credential and device-control
  families carry `destructiveHint`. The licensing mutations and the process launcher are not
  listed at all.
- **Resources.** `serialstudio://frame/current` (the latest processed frame as JSON) and
  `serialstudio://frame/history` (the same frame as a one-element array).
- **Skill.** `serial-studio` states the prerequisite, the read-first workflow, the consent
  prompts the user will see in Serial Studio, and the commands that are not listed, so
  Claude explains a refusal instead of retrying it.

## Requirements

- Serial Studio 4.2 or later, running, with the API server enabled (tool titles and hints
  appear with the first release after 4.2.1; earlier 4.2 builds list the same tools without
  them):
  **Preferences → General → API & Plugins → Enable API Server** (port 7777).
- Python 3 on the `PATH`. The bridge uses the standard library only.
- Claude Code or a Cowork session on the same computer as Serial Studio. The chat surface of
  claude.ai and the desktop app do not load plugin servers.

## Install

From the Claude directory: add **Serial Studio** and start a Claude Code session. The plugin
starts the bridge from its own folder; no configuration file is edited.

From Claude Code directly, in one step:

```
/plugin install serial-studio --marketplace Serial-Studio/claude-plugin
```

For development, from a checkout of this repository:

```bash
claude --plugin-dir /path/to/claude-plugin
```

## Usage

With Serial Studio running and connected to a device, ask Claude for what you want to know
or change. Typical first requests:

- "Is Serial Studio connected, and to what?"
- "Show me the latest values of every dataset."
- "Which groups and datasets does the current project define?"
- "Set the UART baud rate to 115200 and reconnect."

Claude reads status before it acts. A mutation that Serial Studio gates behind a consent
(installing a script, writing to the device, driving the interface, starting a program)
opens a prompt in the Serial Studio window the first time; Claude cannot answer it for you.

## Settings

The plugin has one setting, **Python launcher**, default `python3`. macOS, Linux and Windows
with the Microsoft Store Python resolve `python3`; a python.org install on Windows usually
provides `python` or `py` instead, so set the launcher to the one that starts Python 3 on
your computer.

## Data handling and failure modes

The bridge forwards newline-delimited JSON-RPC between Claude's standard input and output
and `127.0.0.1:7777`. If Serial Studio is not running or the API server is off, the bridge
retries for six seconds, exits with status 1, and its last log line names the setting to
enable, so Claude's MCP status shows the cause. A connection that drops mid-session ends the
bridge; reconnect the MCP server after restarting Serial Studio.

## Privacy Policy

This plugin runs entirely on your computer. It sends data only to the Serial Studio instance
listening on the local TCP port 7777 and receives only what that instance answers. It
collects no data, keeps no logs beyond the standard error stream that Claude shows you, uses
no analytics, and contacts no server on the internet. What Claude does with the telemetry it
reads is governed by Anthropic's own terms, not by this plugin.

## Source and support

- Serial Studio: https://github.com/Serial-Studio/Serial-Studio
- This plugin: https://github.com/Serial-Studio/claude-plugin
- Manual, API Reference, MCP section: https://serial-studio.com (Help Center)
- Issues: https://github.com/Serial-Studio/Serial-Studio/issues

## License

GPL-3.0-or-later. See `LICENSE`.
