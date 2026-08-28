# Backend Developer Agent — Future Improvements

## Post-Sprint 1: Add Prettier Hook

Once the codebase has `package.json` and `.prettierrc` configured, add a `postToolUse` hook to auto-format files after every write:

```json
"hooks": {
  "postToolUse": [
    {
      "matcher": "write",
      "command": "npx prettier --write"
    }
  ]
}
```

This runs Prettier on every file the agent creates or modifies, enforcing formatting without manual intervention.

See: https://kiro.dev/docs/cli/hooks/
