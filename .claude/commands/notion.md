---
name: notion
description: "Use this skill before ANY Notion operation — reading pages, creating pages, appending content, editing content, or linking between pages. Triggers include: any mention of Notion, fetching a Notion URL, writing to Notion, updating a Notion page, creating a subpage, or inserting a link between Notion pages. Always read this skill first even for simple Notion reads or writes."
---

# Notion Operations Skill

## Linking Between Pages
Always use a Notion internal page reference when linking between pages — never paste a raw URL as plain text. A raw URL renders as an unclickable string. An internal page reference renders as a clickable page title with icon.

When linking to another page, reference it by page ID using the Notion MCP tools, not by inserting a URL string into content.

## Editing Existing Pages — CRITICAL
**Never use `replace_content` with a full page rewrite to make a targeted edit.** This overwrites everything on the page.

For targeted edits:
- Use `replace_content` with `old_str` and `new_str` — replace only the specific text that needs to change
- Always fetch the page fresh immediately before editing — stale context leads to mismatched `old_str`

For appending new content:
- Use `insert_content` with `position: end`
- Never rewrite the full page just to add content at the bottom

## Fetch Before Edit
Always fetch the page immediately before any edit operation. Do not rely on page content seen earlier in the conversation — the user may have edited it since.

## Page Hierarchy
When creating a subpage, always confirm the correct parent page ID before creating. Ask the user if unclear — creating a page under the wrong parent is hard to undo cleanly.

## Common Mistakes to Avoid
- Inserting raw URLs instead of internal page references
- Using `replace_content` without `old_str`/`new_str` (overwrites entire page)
- Relying on stale page content without re-fetching
- Creating pages without confirming the correct parent