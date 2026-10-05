# Apple Reminders plugin

A local Codex plugin with a dark Reminders-style interface, backed by your real Apple Reminders on this Mac.

The panel has colored summary tiles, your list colors, circular completion buttons, search, a completed-history view, and a form for titles, notes, notification times, priorities, and flags. It supports editing, reopening, and deleting a selected reminder.

## Open the panel

The live review panel is at [Apple Reminders](http://127.0.0.1:56944) while the local preview process is running. It opens inside Codex's browser panel.

The installed plugin also exposes `open_reminders`, an MCP Apps UI resource, and global and conversation entrypoint metadata. After reloading the plugin or reopening Codex, ask "Open my Apple Reminders dashboard." The host must support MCP Apps to render that embedded interface. The local browser preview and the embedded resource use the same built HTML and reminder tools. Native host rendering is not yet verified in this chat.

The dashboard reads incomplete reminders directly through Apple EventKit, so the main view does not wait for completed history or scripting calls. Completed history loads when you open Completed or select Show within a list. It includes only reminders completed within the last three calendar months, filtered by EventKit before returning their details. The Flagged count shows a dash until a separate background scripting read supplies flag states and list decorations. Other views remain usable during this read. Older completed reminders remain in Apple Reminders. Completed counts and searches cover this recent history. Switching lists and searching use the loaded snapshot. Edits update from the tool response without reloading that history. Use Refresh to pick up changes made in Apple Reminders elsewhere.

## Connection and behavior

The server uses a compiled Swift helper with Apple EventKit for reads and macOS JavaScript for Automation for writes, flags, and list decorations. Reminders stay in your Apple accounts and sync through your existing account setup. Results requested through Codex's tools enter the chat context. The plugin does not need an Apple password or a public web service.

EventKit requires Reminders access for the launching app under System Settings > Privacy & Security > Reminders. This Mac already has that access. macOS may also ask the launching app for Automation access to Reminders. If access is denied, allow Reminders for that app under System Settings > Privacy & Security > Automation.

The date form uses your Mac's local timezone. A new notification sets both the due time and notification time. Editing other fields preserves the existing date and notification time. Existing dates remain unchanged when the date field is left empty.

The pink tile is Overdue. Apple's Urgent smart list rules are not exposed through this automation interface. Recurrence, location alerts, attachments, subtasks, list creation, moving reminders, and clearing dates are outside this version. Notification delivery depends on your Apple Reminders and macOS notification settings.

## Source and installation

`plugins/apple-reminders` contains the plugin manifest, locked Node dependencies, MCP server, Swift source and compiled Apple Silicon helper, scripting bridge, UI source, and built UI resource. The installed source is under `~/.agents/plugins/apple-reminders-local`.

```sh
codex plugin marketplace add ~/.agents/plugins/apple-reminders-local
codex plugin add apple-reminders@schalk-local
```

From the plugin directory, `npm run build` builds the embedded HTML, `npm test` runs checks, and `npm run preview` starts a local review panel on an available loopback port. To reopen on this review port, run `node preview.mjs 56944`.

The generated `.mcp.json` uses the stable Node path installed on this Mac and runs from the installed plugin directory. Update that path if the runtime is removed. To use another Mac, install the exact dependencies from `package-lock.json`, update the Node path, and run `npm run build:native` with Apple command-line tools installed to compile the helper for that Mac.

## Verification

Five tests cover MCP tool validation and UI resource metadata, reminder mutations in an in-memory model, native date and reminder serialization, and background flag filtering at the history cutoff. The direct API read measured about 0.07 seconds including helper startup for both the initial active view and the recent-history read on this Mac. Flags and writes still use the slower scripting interface. The live dashboard snapshot was read from Apple Reminders. UI interactions are checked without changing live reminders. Live writes and notification delivery remain untested.

The UI follows [OpenAI's MCP Apps guidance](https://developers.openai.com/plugins/build/chatgpt-ui) and declares [sidebar and conversation entrypoints](https://developers.openai.com/plugins/build/extensions). The package uses the [supported Codex plugin compatibility format](https://developers.openai.com/plugins/build/plugins).
