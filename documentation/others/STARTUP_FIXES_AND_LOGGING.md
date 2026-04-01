# Startup Fixes And Logging

## Issues Addressed

### Streamlit CORS/XSRF Warning

Resolved by aligning the Streamlit server configuration so `enableCORS` no longer conflicts with `enableXsrfProtection`.

### Database Initialization Failure

Resolved by making startup migration-first and idempotent:

- Alembic baseline creation now uses `checkfirst=True`
- application startup no longer runs `Base.metadata.create_all()` after a successful migration
- database initialization is guarded so Streamlit reruns do not repeatedly re-bootstrap the schema in-process

### Streamlit Deprecation Warning

Resolved by replacing `use_container_width=True` with `width="stretch"` across the workspace.

## Logging Added

The application now writes rotating logs with two channels:

- application log: runtime diagnostics and startup information
- audit log: structured action events

The current audit coverage includes:

- CLI command invocation
- Streamlit workspace navigation
- lifecycle transitions
- generic asset catalog create, update, and delete operations
- database rollback errors

## Remaining Verification Limits

Source-level fixes were completed and a WSL validation attempt was made, but full runtime verification is still partially blocked by the current environment:

- `pytest` is not installed in the tested WSL Python environment
- the tested WSL command path reported missing `sqlalchemy`
- WSL also reported a separate `S:` mount warning during command execution

Because of that, final verification in this pass is code-reviewed plus partially executed, not a complete green runtime certification.
