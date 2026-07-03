# PlaneCLI

Command-line client for Plane.so (SaaS or self-hosted). Its defining trait is **fuzzy
resource resolution**: any resource can be referenced by name, identifier, or UUID. This
glossary pins the vocabulary the CLI exposes to users, which sometimes differs from the
names Plane's API uses internally.

## Language

**Work item**:
The unit of tracked work (a bug, task, story). This is the CLI's user-facing noun and the
`wi` command group. Plane's own API, SDK, and database call the same thing an **issue** — the
`issue` command alias and `resolve_work_item` (which hits the API's `/work-items` → `IssueComment`
serializers) both reflect that heritage. Prefer "work item" in user-facing text; "issue" survives
only where it mirrors the underlying API.
_Avoid_: task, ticket, card, story (as synonyms for the CLI noun).

**Reference**:
Any string a user gives to point at a resource. A reference is one of three **forms**, tried in
this order during resolution: **UUID** → **identifier** → **name**.

**Identifier**:
The human-readable, project-scoped code for a work item, e.g. `ABC-123` (project prefix + number).
Distinct from the UUID and from the free-text name.
_Avoid_: id (ambiguous with UUID), key, slug.

**Resolution**:
Turning a reference into a concrete resource by trying UUID, then identifier, then a fuzzy
name match. The verb is "resolve" (`resolve_work_item`, `resolve_project`). A failed name match
yields "did you mean …?" suggestions.

**Comment**:
An HTML note attached to a work item by an author. Fetched per work item, ordered oldest→newest.
Its plain-text form (HTML stripped) is the `body_text`.

**Author**:
The workspace member who wrote a comment. The API returns this as `actor` (a bare member UUID);
the CLI resolves it to a **display name** via the members cache for output, falling back to the
raw UUID when the member is unknown or the members list is unavailable. "Author" is the
user-facing role name; "actor" is the raw API field.
_Avoid_: actor, user, creator, commenter (as the user-facing label for this role).
