# Workspace Access And Recovery

## Workspace access

`my_grc` now protects the operator workspace with a local authenticated access gate.

### First secure start

1. open the workspace
2. create the first workspace user
3. choose a strong password
4. sign in and continue with onboarding

### CLI alternatives

```bash
aws-local-audit auth status
aws-local-audit auth bootstrap grc.lead --display-name "GRC Lead"
aws-local-audit auth set-password grc.lead
```

## Backup and restore

The platform now supports SQLite backup creation, verification, and restore.

### Create a backup

```bash
aws-local-audit platform backup-create --label pre-release
```

### List backups

```bash
aws-local-audit platform backup-list
```

### Verify a backup

```bash
aws-local-audit platform backup-verify <backup-name>
```

### Restore a backup

```bash
aws-local-audit platform backup-restore <backup-name>
```

When a restore runs, the platform first creates a `pre-restore` snapshot of the current database.

## Observability

The platform now records:

- structured application logs
- audit logs
- metric events
- trace events

Use:

```bash
aws-local-audit platform observability
```

to inspect the current runtime summary from the CLI.
