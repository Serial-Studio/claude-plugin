---
name: serial-studio
description: Read live telemetry and operate Serial Studio through its MCP tools. Use when the user mentions Serial Studio, a serial, UART, Modbus, CAN, Bluetooth LE, MQTT, OPC UA, S7 or EtherNet/IP device, a telemetry dashboard, a .ssproj project, or asks to read sensor values, log data, export a session, or change a dashboard.
---

# Serial Studio

Serial Studio is a telemetry dashboard that runs on the user's computer. This plugin's MCP
server (`serial-studio`) forwards every call to the running application over a local TCP
port. Nothing here reaches the internet.

## Prerequisite

Serial Studio must be running with its API server enabled: **Preferences → General →
API & Plugins → Enable API Server**. When it is not, the MCP server shows as failed and its
last log line reads "Enable the API server: Preferences → General → API & Plugins → Enable
API Server". Tell the user that, in those words, and stop; the plugin cannot start Serial
Studio or change that setting.

## Read first

1. `io.getStatus`: whether a device is connected, which bus, and the link state.
2. The resource `serialstudio://frame/current`, or `dashboard.getData`: the latest processed
   values, per group and dataset. If `hasData` is false, no frame has arrived yet; say so
   rather than reporting zeros.
3. `project.getStatus` and `project.exportJson`: what the current project defines (groups,
   datasets, widgets, the frame parser) before editing any of it.

Only then change something. Prefer the narrowest command (`io.uart.setBaudRate` over a
whole-project edit), and read back after a write.

## Hints and consent

Every tool carries `readOnlyHint` or `destructiveHint` derived from Serial Studio's own
safety tiers. Reads run freely. The delete, clear, open-replace, credential and
device-control families are destructive: name what will change and ask before calling one.

Some commands are gated in Serial Studio itself, independently of Claude: installing a
script or frame parser, writing bytes to the device, driving the user interface, and
starting a program each open a consent prompt in the Serial Studio window the first time a
session uses them. If a call returns a refusal that mentions consent, explain that the user
has to answer the prompt in Serial Studio and retry only after they say they did. A
licensing refusal (a Pro feature on a free build) is final; do not retry it.

## Commands that are not listed

The licensing mutations (`licensing.activate`, `deactivate`, `setLicense`, `enableTrial`,
`activateOffline`, `validate`) and the process launcher (`system.exec`, `system.kill`,
`system.runningProcesses`) are not in the tool list. Do not try to call
them by name; tell the user to use the application for licensing and a control script for
processes.

## Large replies

`api.getCommands` returns the whole command catalog (tens of kilobytes); the tool list you
already have covers the same ground, so avoid it. `dashboard.tailFrames` and the Historian
reads can be large; ask for a bounded range and summarize instead of echoing raw frames.

## Failure messages

- "Session not initialized": the MCP handshake was lost; reconnect the server.
- "Unknown tool": the name is not registered in this Serial Studio version, or it is one
  of the unlisted commands above.
- A "must be" validation error names the parameter and the type it expects; fix the
  argument type (numbers, not strings) before retrying.
