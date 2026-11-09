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
API & Plugins → Enable API Server**. The plugin cannot start Serial Studio or change that
setting.

The bridge stays up while Serial Studio is away and reconnects by itself. If
`bridge.getStatus` is the only tool listed, or a call returns "Serial Studio is not
reachable", tell the user to start Serial Studio and "Enable the API server: Preferences →
General → API & Plugins → Enable API Server". The tools appear on their own once it answers,
so retry after the user says it is up.

If the MCP server itself shows as failed, the bridge could not start: ask the user to check
the plugin's Python launcher setting and run `/mcp` to reconnect.

## Read first

1. `io.getStatus`: whether a device is connected, which bus, and the link state.
2. `dashboard.getStatus` and `project.getStatus`: the operation mode, the widget and dataset
   counts, the project's title and whether it has unsaved changes. These stay small on any
   project.
3. `project.source.list` for the sources, `project.group.get` for one group and
   `project.dataset.getByTitle` for one dataset. Page `project.group.list` and
   `project.dataset.list` with `limit` and `offset`.
4. Values, only as many as the question needs. `dashboard.tailFrames` with `count` and
   `uniqueIds` reads plot-enabled datasets, and `project.dataTable.getValue` reads what a
   parser wrote to a table. The resource `serialstudio://frame/current` and
   `dashboard.getData` return the whole frame, so keep them for small projects. If the
   resource reports `hasData` false, or `dashboard.getData` has empty `frame.groups`, no
   frame has arrived yet; say so rather than reporting zeros.

Only then change something. Prefer the narrowest command (`io.uart.setBaudRate` over a
whole-project edit), and read back after a write.

## Try it before changing it

These run without touching the live project, so use them first:

- `project.validate` and `problems.list`: what Serial Studio already finds wrong.
- `project.frameParser.dryRun`: raw bytes through extraction, the decoder and `parse()`.
- `project.dataset.transform.dryRun` and `controlScript.dryRun`: one script, compiled and
  run against sample input.
- `project.dryRun.endToEnd`: a sample frame through the parser and every transform. It does
  not inject the table API, so test table-dependent transforms with
  `project.dataset.transform.dryRun`.

A parser that writes to data tables returns no rows by design; `rowCount: 0` is normal for
it.

## Hints and consent

Serial Studio derives each tool's hints from its own safety tiers:

- `readOnlyHint`: reads. They run freely.
- `destructiveHint`: the delete, clear, open-replace, credential and device-control
  families. Name what will change and ask before calling one.
- Neither hint: reversible changes to the project or the application, such as `project.save`
  or `dashboard.setOperationMode`. Make them when the user asked for that change, never just
  to explore.

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

Some replies grow with the project. At about 900 datasets, `project.exportJson`,
`project.group.list`, `project.dataset.list` and `dashboard.getData` each came to between
800 KB and 1.2 MB. Never call them unbounded on a project of unknown size; check the dataset
count in `project.getStatus` first, and prefer the narrow reads under "Read first".

`api.getCommands` returns the whole command catalog (tens of kilobytes); the tool list you
already have covers the same ground, so avoid it. `dashboard.tailFrames` and the Historian
reads can be large; ask for a bounded range and summarize instead of echoing raw frames.

## Failure messages

- "Session not initialized": the MCP handshake was lost; ask the user to run `/mcp` to
  reconnect the server.
- "Unknown tool": the name is not registered in this Serial Studio version, or it is one
  of the unlisted commands above.
- A "must be" validation error names the parameter and the type it expects; fix the
  argument type (numbers, not strings) before retrying.
