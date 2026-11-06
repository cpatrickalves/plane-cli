# Testing

## Automated tests

- Tests run offline: mock the SDK and resolvers rather than calling a Plane instance. Prefer testing pure logic (normalizers, fuzzy matching, resolution) directly.
- `conftest.py` autouses a `mem://` cache backend and provides a `mock_plane_client` fixture.
- Async tests need no decorator (`asyncio_mode = "auto"`).

## Running a PR's code

Use `uvx`, because the installed `planecli` is an editable install that runs whatever this checkout has checked out:

```bash
uvx --from git+https://github.com/<owner>/plane-cli@<branch> planecli ...
```

`planecli --version` shows the commit that runs (`0.5.1+18c7682`).
