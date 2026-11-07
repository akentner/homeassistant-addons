# Quick 261105-ffy: haos-monitor 0.7.2-0 (replay limit, syncing state)

Source: brief-impl.md (session scratchpad). Executed inline in this worktree (no subagents).

1. Limit kernel log replay in the REMOTE block (uptime - 300 s), cheaper log().
2. `syncing` state: SYNC markers in monitor.sh, status.sh `syncing`, UI badge, metric, docs, 0.7.2-0.
3. admin-ui cache hardening (optional): deferred, see summary.
