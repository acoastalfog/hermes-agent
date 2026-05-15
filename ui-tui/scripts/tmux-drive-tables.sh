#!/usr/bin/env bash
#
# tmux-drive-tables.sh — launch hermes --tui --yolo in tmux, send table
# prompts, capture rendered output at multiple terminal widths.
#
# Usage:
#   ./scripts/tmux-drive-tables.sh [profile]
#
# Defaults to the "table-repro" profile (must exist — `hermes profile create
# table-repro --clone`).  Output goes to /tmp/table-repro-captures/.
#
# This is the "full-stack" repro — the vitest suite in
# src/__tests__/tableRepro.test.ts is faster for pure render testing.

set -euo pipefail

PROFILE="${1:-table-repro}"
SESSION="table-repro-$$"
OUT="/tmp/table-repro-captures"
mkdir -p "$OUT"

cleanup() {
  tmux kill-session -t "$SESSION" 2>/dev/null || true
}
trap cleanup EXIT

# ── prompts ──────────────────────────────────────────────────────────
# We ask the model to output exact markdown tables so we can see how
# the TUI renders them.  --yolo skips tool approvals.
PROMPT='Do NOT use any tools.  Output these markdown tables verbatim in your response text:

## Table 1 — simple
| Name | Age | City |
|------|-----|------|
| Alice Johnson | 28 | San Francisco |
| Bob Smith | 34 | New York |

## Table 2 — wide 6-col
| Project | Description | Stack | Timeline | Budget | Status |
|---------|-------------|-------|----------|--------|--------|
| E-commerce Platform | Modern shopping experience | React, Node, Postgres, Redis | 6 months | $150K-200K | In Progress |
| Mobile Banking | Secure transactions | Flutter, Firebase, K8s | 8 months | $300K-400K | Planning |

## Table 3 — long paths
| File Path | Description |
|-----------|-------------|
| /home/user/very/long/path/to/some/deeply/nested/file.py | Main entry point |
| /home/user/projects/backend/src/controllers/authentication/user_management.py | Auth controller |

## Table 4 — lopsided
| Code | Country | Detailed Description |
|------|---------|----------------------|
| US | United States | A federal republic consisting of 50 states and various territories, known for its diverse geography, technological innovation, and significant global economic influence across multiple industries |
| UK | United Kingdom | A sovereign country comprising England, Scotland, Wales, and Northern Ireland, historically significant for its maritime empire and industrial revolution |

## Table 5 — original bug report
| Path | What it is |
|------|------------|
| environments/ (43 files) | Entire RL environments directory — base env, agent loop, tool context, patches, SWE env, terminal test env, benchmarks (TerminalBench2, TBLite, YC bench), tool call parsers (hermes, llama, mistral, deepseek, qwen, kimi, glm, etc.) |
| rl_cli.py (~410 lines) | Standalone CLI for RL training via Tinker-Atropos |
| tools/rl_training_tool.py (~1400 lines) | All 10 rl_* tools (list/select/start/stop/configure/status/results/etc.) |'

# ── test at each width ───────────────────────────────────────────────
for WIDTH in 60 80 100 120 160; do
  echo "═══ Testing at ${WIDTH} columns ═══"

  # Create session at this width
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux new-session -d -s "$SESSION" -x "$WIDTH" -y 50

  # Wait for shell, then launch hermes
  sleep 2
  # Dismiss oh-my-zsh update if present
  tmux send-keys -t "$SESSION" "n" Enter 2>/dev/null || true
  sleep 1
  tmux send-keys -t "$SESSION" "${PROFILE} --tui --yolo" Enter
  sleep 12  # wait for TUI to start

  # Check it's up
  if ! tmux capture-pane -t "$SESSION" -p 2>/dev/null | grep -q "ready"; then
    echo "  ⚠ TUI didn't start at ${WIDTH} cols, skipping"
    continue
  fi

  # Send the prompt
  # tmux send-keys doesn't handle newlines in the string well for TUI input,
  # so we send it as a single line
  tmux send-keys -t "$SESSION" "Do NOT use any tools. Just output 5 markdown tables directly: (1) Name/Age/City 4 rows (2) 6 cols with project descriptions (3) long file paths + descriptions (4) 2-char country codes + 100-char descriptions (5) the AGENTS.md RL table from the bug report with environments/ rl_cli.py tools/rl_training_tool.py" Enter

  # Wait for response to complete
  echo "  Waiting for response..."
  for i in $(seq 1 60); do
    sleep 2
    if tmux capture-pane -t "$SESSION" -p 2>/dev/null | grep -q "^.─ ready"; then
      # Check it's not the initial ready (token count > 0)
      if tmux capture-pane -t "$SESSION" -p 2>/dev/null | grep "ready" | grep -qv "0/"; then
        echo "  ✓ Response complete"
        break
      fi
    fi
  done

  # Capture the full visible pane
  tmux capture-pane -t "$SESSION" -p > "$OUT/capture-${WIDTH}col.txt" 2>&1

  # Scroll through the entire response and capture each viewport
  for scroll in $(seq 1 20); do
    tmux send-keys -t "$SESSION" S-Up
    sleep 0.1
  done
  sleep 0.5

  PART=0
  while true; do
    tmux capture-pane -t "$SESSION" -p > "$OUT/capture-${WIDTH}col-part${PART}.txt" 2>&1
    # Check if we're at the top (banner visible)
    if grep -q "Messenger of the Digital Gods" "$OUT/capture-${WIDTH}col-part${PART}.txt" 2>/dev/null; then
      break
    fi
    PART=$((PART + 1))
    for scroll in $(seq 1 10); do
      tmux send-keys -t "$SESSION" S-Up
      sleep 0.1
    done
    sleep 0.3
    if [ "$PART" -gt 20 ]; then
      break
    fi
  done

  echo "  Saved $(ls "$OUT"/capture-${WIDTH}col*.txt | wc -l) captures to $OUT/"

  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
done

echo ""
echo "Done!  All captures in: $OUT/"
echo ""
echo "To inspect:"
echo "  cat $OUT/capture-80col.txt      # bottom of output at 80 cols"
echo "  cat $OUT/capture-60col-part0.txt # scrolled view at 60 cols"
echo ""
echo "For the fast unit-level repro (no tmux, no model):"
echo "  cd ui-tui && node_modules/.bin/vitest run src/__tests__/tableRepro.test.ts"
