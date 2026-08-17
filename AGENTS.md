
# RTK Usage Rules for Codex CLI

When executing shell commands that may produce large amounts of output, you must prioritize using RTK (Rust Token Killer) to compress and summarize the output.

Mandatory rewrites:

- git status -> rtk git status
- git diff -> rtk git diff
- cat <file></file> -> rtk read <file></file>
- rg <pattern></pattern> -> rtk grep <pattern></pattern> .
- pytest / cargo test -> rtk pytest / rtk cargo test

Only fall back to original commands if RTK output is insufficient to diagnose the issue or raw logs are required for deep debugging.
