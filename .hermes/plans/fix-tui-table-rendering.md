# Fix TUI Markdown Table Rendering — Implementation Plan (v2)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make `renderTable()` in `ui-tui/src/components/markdown.tsx` width-aware so tables degrade gracefully at any terminal width — proportional column shrinking, word-wrap inside cells, and vertical key-value fallback when the table can't fit.

**Architecture:** Adopt Claude Code's rendering model: build complete row strings (not adjacent `<Text>` siblings) and render them as a single `<Text>` block so Ink can't reflow table layout. Four-tier column sizing: ideal → proportional shrink → hard scale-down → vertical fallback (safety check + row-height threshold). Keep the existing borderless aesthetic.

**Key design choice — inline markdown in table cells:** For this patch, **all** table cells render as **plain text** (via `stripInlineMarkup`). This is an explicit trade-off: the full-line string rendering model is incompatible with per-cell `<MdInline>` React components, and width-correct wrapping is more important than preserving bold/italic/code inside cells. Inline formatting inside table cells is deferred to a follow-up (requires formatting to ANSI first, then ANSI-aware wrapping like `free-code`'s `wrapText` at L44-L62 of `MarkdownTable.tsx`).

**Tech Stack:** TypeScript, React (Ink), `@hermes/ink` (`stringWidth`, `Box`, `Text`), vitest

**Reproduction test suite:** `ui-tui/src/__tests__/tableRepro.test.ts` (30 tests) and `ui-tui/src/__tests__/tableFuzz.test.ts` (80 tests) — run after every task.

---

## Decisions Summary

| Decision | Choice |
|---|---|
| Border style | Keep current borderless (thin `─` separator), no box-drawing chars |
| Rendering model | Build full row strings, render as single `<Text>` block (like `free-code` L320: `<Ansi>{tableLines.join('\n')}</Ansi>`) — avoids Ink reflow |
| Width source | Thread `cols` prop down through `MdProps` → `renderTable` |
| Vertical fallback threshold | Scaled by column count: `numCols <= 3 ? 8 : numCols <= 6 ? 5 : 4` |
| Cell text | Plain text (`stripInlineMarkup`) in all tiers — inline markdown preservation deferred to ANSI follow-up |
| Safety margin | 4 cols |
| Min column width | 3 chars |
| `paddingLeft` accounting | `renderTable` subtracts its own `paddingLeft={2}` from `cols` since `transcriptBodyWidth()` (L171) only subtracts message gutter, not table indent |
| Post-render safety check | After building horizontal lines, measure max `stringWidth`; if > `cols - SAFETY_MARGIN`, fall back to vertical |
| Hard wrap grapheme safety | Use `Intl.Segmenter` where available, fall back to `[...word]` code-point split |
| Rounding remainder | Distribute leftover cols to columns with largest fractional remainder |
| E2E test approach | tmux + `hermes --tui --yolo` from worktree, **deterministic pasted markdown** (not model-generated) |

---

## Code Path References

### Hermes TUI — files we're modifying

**`ui-tui/src/components/markdown.tsx`** (main file, ~868 lines)
- `renderTable()` — **lines 203-244** — the broken function. Signature L203, body L204-L243.
  - `cellWidth()` — L210 — uses `stringWidth(stripInlineMarkup(raw))`
  - `widths` — L212 — naive max-content-width per column, no terminal constraint
  - `sep` — L220 — `'─'.repeat(w)` joined with `'  '`, wraps destructively
  - JSX return — L222-L243 — `<Box>` per row, `<Text>` per cell, space-padded, no `wrap="truncate-end"`
- `splitRow()` — L130 — splits `|`-delimited row into cells
- `isTableDivider()` — L138 — detects `|---|---|`
- `stripInlineMarkup()` — L185 — strips bold/italic/code/links for width measurement
- `MdInline` — L246 — inline markdown renderer; used at L229 for cell content today
- Table parse site 1 — L779 → calls `renderTable` at L788
- Table parse site 2 — L825-L830 → calls `renderTable` at L841
- `MdImpl` — L398 — main render function
- Cache key — L401 — `\`${compact ? '1' : '0'}|${text}\`` — **must add `cols`**
- `useMemo` deps — L855 — `[compact, t, text]` — **must add `cols`**
- `MdProps` — L864 — **must add `cols?: number`**
- `stringWidth` import — L1

**`ui-tui/src/components/messageLine.tsx`** (~219 lines)
- `cols` prop — L29
- `transcriptBodyWidth` import — L8
- Parent Box width — L202 — `<Box width={transcriptBodyWidth(cols, msg.role, t.brand.prompt)}>`
- `<StreamingMd>` — L146 — needs `cols={bodyWidth}`
- `<Md>` — L148 — needs `cols={bodyWidth}`

**`ui-tui/src/components/streamingMarkdown.tsx`** (~173 lines)
- `StreamingMdProps` — L169 — **must add `cols?`**
- `StreamingMd` — L131 — must pass `cols` to inner `<Md>` calls at L154, L158, L163, L164

**`ui-tui/src/lib/inputMetrics.ts`** (read-only reference)
- `transcriptBodyWidth()` — L171-L172 — `totalCols - gutter - 2`. Subtracts message gutter + scrollbar. Does NOT subtract `renderTable`'s `paddingLeft={2}`, so `renderTable` must account for it.

### Internal ink APIs (read-only, not modifying)

**`ui-tui/packages/hermes-ink/src/ink/wrapAnsi.ts`** — L13 — not exported from public API, ANSI-level
**`ui-tui/packages/hermes-ink/src/ink/wrap-text.ts`** — L129 — Ink internal, drives `<Text wrap="...">`

### Claude Code — reference implementation

**`~/github/free-code/src/components/MarkdownTable.tsx`** (~321 lines)
- Constants: `SAFETY_MARGIN=4` L15, `MIN_COLUMN_WIDTH=3` L18, `MAX_ROW_LINES=4` L25
- `wrapText()` — L44-L62 — ANSI-aware cell wrapper
- `MarkdownTable()` — L72 — component entry
- `getMinWidth()` — L94 — longest word per cell
- `getIdealWidth()` — L102 — full content width
- **Three-tier width calc — L128-L156:**
  - `availableWidth` — L128
  - Tier 1 (ideal fits) — L137
  - Tier 2 (proportional shrink) — L140-L149
  - Tier 3 (hard scale) — L150-L156
- `useVerticalFormat` — L184
- `renderRowLines()` — L188-L223 — multi-line cells, vertical centering, `padAligned`
- `renderBorderLine()` — L226-L238 — box-drawing chars
- `renderVerticalFormat()` — L241-L288 — key-value fallback
- **Post-render safety check** — L311-L316 — if max line width > terminal, fall back to vertical
- **Final render** — L320 — `<Ansi>{tableLines.join('\n')}</Ansi>` — single block

**`~/github/free-code/src/utils/markdown.ts`** — `padAligned()` L366-L381
**`~/github/free-code/src/components/Markdown.tsx`** — table dispatch L144-L146

### Test files

**`ui-tui/src/__tests__/tableRepro.test.ts`** — `renderAtWidth` L34, createElement L47-L50 — must add `cols`
**`ui-tui/src/__tests__/tableFuzz.test.ts`** — `renderAtWidth` L29, createElement L42-L45 — same
**`ui-tui/src/__tests__/markdown.test.ts`** — CJK test L256-L301 — must not regress

---

## File Inventory

| File | Action | LOC estimate |
|---|---|---|
| `ui-tui/src/components/markdown.tsx` | Rewrite `renderTable` (L203-244), update `MdProps` (L864), `MdImpl` cache (L401, L855) | ~150 net new |
| `ui-tui/src/components/streamingMarkdown.tsx` | Add `cols` to `StreamingMdProps`, thread to `<Md>` | ~5 changed |
| `ui-tui/src/components/messageLine.tsx` | Pass `cols` to `<Md>` and `<StreamingMd>` | ~5 changed |
| `ui-tui/src/__tests__/tableRepro.test.ts` | Fix `renderAtWidth`, add structural assertions | ~40 changed |
| `ui-tui/src/__tests__/tableFuzz.test.ts` | Fix `renderAtWidth`, add overflow assertions | ~30 changed |

## Implementation Order

```
Phase 1: Thread `cols` + update cache (no rendering change)
  Task 1 → Task 2 → Task 3
  Run vitest: all existing tests pass (behavior unchanged)

Phase 2: Width calculation + full-line string rendering for horizontal tables
  Task 2 — four-tier: ideal → proportional shrink → hard scale → (safety/row-height vertical fallback in Phase 4)
  Run vitest repro suites: visual diff shows improvement at narrow widths

Phase 3: Cell wrapping within allocated widths
  Task 3 — wrapCell, multi-line row building, safety condition computed (but vertical fallback not yet wired)
  Run vitest repro suites: tables that overflow now wrap cells

Phase 4: Vertical key-value fallback + safety fallback wiring
  Task 4 — wires safety check + row-height threshold → vertical format
  Run vitest: extreme-disparity + kitchen-sink fixtures show vertical format
  ⚔ Adversarial review gate (Claude Code)

Phase 5: Structural tests + deterministic tmux E2E
  Task 7 → Task 8
  All 110 tests pass with structural assertions

Phase 6 (deferred): Inline markdown preservation in wrapped cells
  Not in this patch — noted in code as TODO
```

### Review findings incorporated

1. **Render rows as complete strings** — not adjacent `<Text>` siblings (from consolidated review point 1)
2. **Explicit plain-text rendering for wrapped cells** — no false `stripInlineMarkup` → `<MdInline>` round-trip (point 2)
3. **Subtract `paddingLeft` from available width** — `transcriptBodyWidth` does NOT account for table indent (point 3)
4. **Post-render safety check** — measure `stringWidth` of rendered lines, fall back if overflow (point 4)
5. **Distribute rounding remainders** — largest-fractional-remainder pass (point 5)
6. **Grapheme-safe hard wrapping** — `Intl.Segmenter` with `[...word]` fallback (point 6)
7. **Task 4+5 kept executable** — old render path replaced atomically with full-line approach (point 7)
8. **Edge cases in vertical fallback** — header-only, empty rows, ragged, tiny cols (point 8)
9. **Deterministic E2E inputs** — paste fixed markdown, not model-generated (point 9)
10. **Assertions use `stringWidth`** — not `.length` (point 10)
11. **Cache key + useMemo deps** — `cols` added (from first review)
12. **Scaled MAX_ROW_LINES** — by column count (from first review)

---

## Phase 1: Thread `cols` and update cache

### Task 1: Add `cols` to MdProps, thread to renderTable, update cache

**Objective:** Single task — plumb `cols` from `MessageLine` through `StreamingMd` → `Md` → `renderTable`. Update cache key and useMemo deps. Zero rendering change.

**Files:**
- Modify: `ui-tui/src/components/markdown.tsx` (L203 signature, L401 cache, L855 deps, L864 interface)
- Modify: `ui-tui/src/components/streamingMarkdown.tsx` (L131, L154, L158, L163, L164, L169)
- Modify: `ui-tui/src/components/messageLine.tsx` (L146, L148)

**Changes in `markdown.tsx`:**

```typescript
// L864: Add cols to interface
interface MdProps {
  cols?: number
  compact?: boolean
  t: Theme
  text: string
}

// L398: Destructure cols
function MdImpl({ cols, compact, t, text }: MdProps) {

// L401: Include cols in cache key
const cacheKey = `${compact ? '1' : '0'}|${cols ?? ''}|${text}`

// L855: Include cols in useMemo deps
}, [cols, compact, t, text])

// L203: Add cols to renderTable signature
const renderTable = (k: number, rows: string[][], t: Theme, cols?: number) => {

// L788, L841: Pass cols at call sites
nodes.push(renderTable(key, rows, t, cols))
```

**Changes in `streamingMarkdown.tsx`:**

```typescript
// L169: Add cols to interface
interface StreamingMdProps {
  cols?: number
  compact?: boolean
  t: Theme
  text: string
}

// L131: Destructure
export const StreamingMd = memo(function StreamingMd({ cols, compact, t, text }: StreamingMdProps) {

// L154, L158, L163, L164: Pass to every <Md>
<Md cols={cols} compact={compact} t={t} text={...} />
```

**Changes in `messageLine.tsx`:**

```typescript
// Before L146: compute bodyWidth
const bodyWidth = transcriptBodyWidth(cols, msg.role, t.brand.prompt)

// L146:
<StreamingMd cols={bodyWidth} compact={compact} t={t} text={...} />

// L148:
<Md cols={bodyWidth} compact={compact} t={t} text={...} />
```

**Verify:**

```bash
cd ui-tui && node_modules/.bin/vitest run 2>&1 | tail -5
# All existing tests pass — no rendering change
```

**Commit:**

```bash
git add ui-tui/src/components/markdown.tsx ui-tui/src/components/streamingMarkdown.tsx ui-tui/src/components/messageLine.tsx
git commit -m "refactor(tui): thread cols through Md/StreamingMd/renderTable, update cache key"
```

---

## Phase 2: Width calculation + full-line string rendering

### Task 2: Replace renderTable with width-aware full-line-string renderer

**Objective:** Replace the entire body of `renderTable()` (L203-L244) with: three-tier column width calculation, full-line string building per row, and `<Text wrap="truncate-end">` per line. Non-wrapped tables (tier 1) still use `<MdInline>` for cell content; shrunk/wrapped tables (tier 2) render plain text (explicitly no inline markdown).

This follows `free-code`'s core approach: `MarkdownTable.renderRowLines()` (L188-L223) builds complete row strings, and the final render (L320) is a single `<Ansi>` block.

**Files:**
- Modify: `ui-tui/src/components/markdown.tsx` — replace L203-L244

**Step 1: Run repro tests, save "before" baseline**

```bash
cd ui-tui && node_modules/.bin/vitest run src/__tests__/tableRepro.test.ts src/__tests__/tableFuzz.test.ts 2>&1 > /tmp/table-before.txt
```

**Step 2: Replace renderTable**

```typescript
const SAFETY_MARGIN = 4
const MIN_COL_WIDTH = 3
const COL_GAP = 2  // '  ' between columns
const TABLE_PADDING_LEFT = 2  // paddingLeft={2} on the <Box>

const renderTable = (k: number, rows: string[][], t: Theme, cols?: number) => {
  // Guard: empty table
  if (rows.length === 0 || rows[0]!.length === 0) return null

  const cellDisplayWidth = (raw: string) => stringWidth(stripInlineMarkup(raw))

  // Minimum width: longest word in a cell (to avoid breaking words)
  const minCellWidth = (raw: string) => {
    const text = stripInlineMarkup(raw)
    const words = text.split(/\s+/).filter(w => w.length > 0)
    if (words.length === 0) return MIN_COL_WIDTH
    return Math.max(...words.map(w => stringWidth(w)), MIN_COL_WIDTH)
  }

  const numCols = rows[0]!.length

  // Normalize ragged rows: ensure every row has numCols cells
  const normalizedRows = rows.map(row => {
    if (row.length >= numCols) return row.slice(0, numCols)
    return [...row, ...Array(numCols - row.length).fill('')]
  })

  // Ideal widths: max cell content per column
  const idealWidths = normalizedRows[0]!.map((_, ci) =>
    Math.max(...normalizedRows.map(r => cellDisplayWidth(r[ci] ?? '')), MIN_COL_WIDTH)
  )

  // Min widths: longest word per column
  const minWidths = normalizedRows[0]!.map((_, ci) =>
    Math.max(...normalizedRows.map(r => minCellWidth(r[ci] ?? '')), MIN_COL_WIDTH)
  )

  // Available width: cols minus table padding minus column gaps minus safety
  // Note: transcriptBodyWidth (source of cols) subtracts message gutter + scrollbar,
  // but NOT this table's paddingLeft. We must subtract it here.
  const gapOverhead = (numCols - 1) * COL_GAP
  const availableWidth = cols
    ? Math.max(cols - TABLE_PADDING_LEFT - gapOverhead - SAFETY_MARGIN, numCols * MIN_COL_WIDTH)
    : Infinity

  const totalIdeal = idealWidths.reduce((a, b) => a + b, 0)
  const totalMin = minWidths.reduce((a, b) => a + b, 0)

  let columnWidths: number[]
  let needsWrap = false

  if (totalIdeal <= availableWidth) {
    // Tier 1: everything fits
    columnWidths = idealWidths
  } else if (totalMin <= availableWidth) {
    // Tier 2: proportional shrink — distribute extra space beyond minimums
    needsWrap = true
    const extraSpace = availableWidth - totalMin
    const overflows = idealWidths.map((ideal, i) => ideal - minWidths[i]!)
    const totalOverflow = overflows.reduce((a, b) => a + b, 0)
    if (totalOverflow === 0) {
      columnWidths = [...minWidths]
    } else {
      // Allocate proportionally, then distribute remainders
      const rawAlloc = minWidths.map((min, i) =>
        min + (overflows[i]! / totalOverflow) * extraSpace
      )
      columnWidths = rawAlloc.map(v => Math.floor(v))
      let remainder = availableWidth - columnWidths.reduce((a, b) => a + b, 0)
      // Give leftovers to columns with largest fractional part
      const fracs = rawAlloc.map((v, i) => ({ i, frac: v - Math.floor(v) }))
        .sort((a, b) => b.frac - a.frac)
      for (const { i } of fracs) {
        if (remainder <= 0) break
        columnWidths[i]!++
        remainder--
      }
    }
  } else {
    // Tier 3: even min-widths don't fit — scale proportionally, allow hard breaks
    needsWrap = true
    const scaleFactor = availableWidth / totalMin
    const rawAlloc = minWidths.map(w => w * scaleFactor)
    columnWidths = rawAlloc.map(v => Math.max(Math.floor(v), MIN_COL_WIDTH))
    let remainder = availableWidth - columnWidths.reduce((a, b) => a + b, 0)
    const fracs = rawAlloc.map((v, i) => ({ i, frac: v - Math.floor(v) }))
      .sort((a, b) => b.frac - a.frac)
    for (const { i } of fracs) {
      if (remainder <= 0) break
      columnWidths[i]!++
      remainder--
    }
  }

  // ... wrapping and rendering continue in Task 3 (Phase 3) ...
  // For now, use the old render path with the new columnWidths.
  // This is intentional — Task 2 proves the width calc is correct,
  // Task 3 adds wrapping.

  // Tier 1 (no wrapping needed): render plain text with full-line strings
  if (!needsWrap) {
    const sep = columnWidths.map(w => '─'.repeat(Math.max(1, w))).join('  ')
    return (
      <Box flexDirection="column" key={k} paddingLeft={TABLE_PADDING_LEFT}>
        {normalizedRows.map((row, ri) => (
          <Fragment key={ri}>
            <Text
              bold={ri === 0}
              color={ri === 0 ? t.color.accent : undefined}
              wrap="truncate-end"
            >
              {row.map((cell, ci) => {
                const text = stripInlineMarkup(cell)
                const pad = ' '.repeat(Math.max(0, columnWidths[ci]! - stringWidth(text)))
                const gap = ci < numCols - 1 ? '  ' : ''
                return text + pad + gap
              }).join('')}
            </Text>
            {ri === 0 && normalizedRows.length > 1 ? (
              <Text color={t.color.muted} dimColor wrap="truncate-end">{sep}</Text>
            ) : null}
          </Fragment>
        ))}
      </Box>
    )
  }

  // Tier 2/3 (needs wrapping): placeholder — truncated for now.
  // Task 3 replaces this with wrapCell + multi-line row rendering.
  const sep = columnWidths.map(w => '─'.repeat(Math.max(1, w))).join('  ')
  return (
    <Box flexDirection="column" key={k} paddingLeft={TABLE_PADDING_LEFT}>
      {normalizedRows.map((row, ri) => (
        <Fragment key={ri}>
          <Text
            bold={ri === 0}
            color={ri === 0 ? t.color.accent : undefined}
            wrap="truncate-end"
          >
            {row.map((cell, ci) => {
              const text = stripInlineMarkup(cell)
              const pad = ' '.repeat(Math.max(0, columnWidths[ci]! - stringWidth(text)))
              const gap = ci < numCols - 1 ? '  ' : ''
              return text + pad + gap
            }).join('')}
          </Text>
          {ri === 0 && normalizedRows.length > 1 ? (
            <Text color={t.color.muted} dimColor wrap="truncate-end">{sep}</Text>
          ) : null}
        </Fragment>
      ))}
    </Box>
  )
}
```

Key points:
- **Full-line strings** — each row is one `<Text>` with the complete row as a string, not N adjacent `<Text>` elements. This mirrors `free-code` L320.
- `wrap="truncate-end"` — prevents Ink from destructively wrapping past the allocated width.
- Tier 1 renders cells as plain text in this version. `<MdInline>` support for non-wrapped tables is preserved by checking `!needsWrap`.
- Tier 2/3 placeholder truncates — Task 3 replaces with real wrapping.

**Step 3: Run tests, compare**

```bash
cd ui-tui && node_modules/.bin/vitest run src/__tests__/tableRepro.test.ts src/__tests__/tableFuzz.test.ts 2>&1 > /tmp/table-after-task2.txt
diff /tmp/table-before.txt /tmp/table-after-task2.txt | head -60
```

Tables that fit should look the same (tier 1). Wide tables at narrow widths should now truncate cleanly instead of garbling.

**Step 4: Run full test suite**

```bash
cd ui-tui && node_modules/.bin/vitest run 2>&1 | tail -5
```

**Commit:**

```bash
git add ui-tui/src/components/markdown.tsx
git commit -m "feat(tui): three-tier width calc + full-line string rendering in renderTable"
```

---

## Phase 3: Cell wrapping + safety fallback

### Task 3: Add wrapCell and multi-line row rendering

**Objective:** When a table needs wrapping (tier 2/3), wrap cell text within allocated column widths and render each visual line as a complete string. Compute the post-render safety condition (max line width vs available space) — the actual vertical fallback is wired in Task 4.

Follows `free-code` pattern: `renderRowLines()` at L188-L223 builds multi-line rows, and the safety check at L311-L316 catches edge cases.

**Files:**
- Modify: `ui-tui/src/components/markdown.tsx`

**Step 1: Add wrapCell helper**

```typescript
// Grapheme-safe hard-break: prefer Intl.Segmenter, fall back to code-point split
const segmenter = typeof Intl !== 'undefined' && 'Segmenter' in Intl
  ? new Intl.Segmenter(undefined, { granularity: 'grapheme' })
  : null

const graphemes = (s: string): string[] =>
  segmenter
    ? [...segmenter.segment(s)].map(seg => seg.segment)
    : [...s]

/**
 * Word-wrap plain text to fit within `width` display columns.
 * Operates on stripped text (no ANSI/markdown) for correct width measurement.
 * Returns array of lines.
 */
const wrapCell = (raw: string, width: number, hard: boolean): string[] => {
  const text = stripInlineMarkup(raw)
  if (width <= 0) return [text]
  if (stringWidth(text) <= width) return [text]

  const words = text.split(/\s+/).filter(w => w.length > 0)
  const lines: string[] = []
  let current = ''
  let currentWidth = 0

  for (const word of words) {
    const w = stringWidth(word)
    if (currentWidth === 0) {
      if (hard && w > width) {
        // Word wider than column — break on grapheme boundaries
        for (const ch of graphemes(word)) {
          const cw = stringWidth(ch)
          if (currentWidth + cw > width && current) {
            lines.push(current)
            current = ''
            currentWidth = 0
          }
          current += ch
          currentWidth += cw
        }
      } else {
        current = word
        currentWidth = w
      }
    } else if (currentWidth + 1 + w <= width) {
      current += ' ' + word
      currentWidth += 1 + w
    } else {
      lines.push(current)
      current = word
      currentWidth = w
    }
  }
  if (current) lines.push(current)
  return lines.length > 0 ? lines : ['']
}
```

**Step 2: Replace tier 2/3 rendering with full-line wrapping**

Replace the tier 2/3 placeholder in `renderTable` with:

```typescript
  // Tier 2/3: needs wrapping — build complete row strings
  const isHard = totalMin > availableWidth  // tier 3

  // Build complete lines for one row (uses normalizedRows for consistent column count)
  const buildRowLines = (row: string[]): string[] => {
    const cellLines = row.map((cell, ci) =>
      wrapCell(cell, columnWidths[ci]!, isHard)
    )
    const maxLines = Math.max(...cellLines.map(l => l.length), 1)

    const result: string[] = []
    for (let li = 0; li < maxLines; li++) {
      let line = ''
      for (let ci = 0; ci < numCols; ci++) {
        const cl = cellLines[ci] ?? ['']
        const cellText = li < cl.length ? cl[li]! : ''
        const pad = ' '.repeat(Math.max(0, columnWidths[ci]! - stringWidth(cellText)))
        line += cellText + pad
        if (ci < numCols - 1) line += '  '
      }
      result.push(line)
    }
    return result
  }

  const sep = columnWidths.map(w => '─'.repeat(Math.max(1, w))).join('  ')

  // Build all lines with metadata for styling
  type LineEntry = { text: string; kind: 'header' | 'separator' | 'body' }
  const allEntries: LineEntry[] = []
  normalizedRows.forEach((row, ri) => {
    const kind = ri === 0 ? 'header' as const : 'body' as const
    buildRowLines(row).forEach(text => allEntries.push({ text, kind }))
    if (ri === 0 && normalizedRows.length > 1) {
      allEntries.push({ text: sep, kind: 'separator' })
    }
  })

  // POST-RENDER SAFETY CHECK (mirrors free-code L311-L316)
  const maxLineWidth = Math.max(...allEntries.map(e => stringWidth(e.text)))
  // Safety condition computed — vertical fallback wired in Task 4.
  // For now, just render truncated if it overflows.

  return (
    <Box flexDirection="column" key={k} paddingLeft={TABLE_PADDING_LEFT}>
      {allEntries.map((entry, i) => (
        <Text
          bold={entry.kind === 'header'}
          color={entry.kind === 'header' ? t.color.accent : entry.kind === 'separator' ? t.color.muted : undefined}
          dimColor={entry.kind === 'separator'}
          key={i}
          wrap="truncate-end"
        >
          {entry.text}
        </Text>
      ))}
    </Box>
  )
```

**Step 3: Run repro tests**

```bash
cd ui-tui && node_modules/.bin/vitest run src/__tests__/tableRepro.test.ts src/__tests__/tableFuzz.test.ts 2>&1 | tee /tmp/table-after-task3.txt
```

Wide tables at narrow widths should now wrap cells instead of truncating.

**Step 4: Run full suite**

```bash
cd ui-tui && node_modules/.bin/vitest run 2>&1 | tail -5
```

**Commit:**

```bash
git add ui-tui/src/components/markdown.tsx
git commit -m "feat(tui): cell wrapping + post-render safety check in renderTable"
```

---

## Phase 4: Vertical key-value fallback

### Task 4: Add vertical format rendering

**Objective:** When rows would exceed a scaled line threshold, or the safety check fails, render as key-value pairs. Handle edge cases: header-only tables, empty rows, ragged rows, very small `cols`.

Follows `free-code`'s `renderVerticalFormat()` at L241-L288.

**Files:**
- Modify: `ui-tui/src/components/markdown.tsx`

**Step 1: Add vertical format logic**

After building `allLines` and the safety check, replace the placeholder:

```typescript
  // Scaled vertical threshold (from review)
  const maxRowLinesThreshold = numCols <= 3 ? 8 : numCols <= 6 ? 5 : 4

  // Check if any row exceeds threshold
  const tallestRow = Math.max(...normalizedRows.slice(1).map(row =>
    Math.max(...row.map((cell, ci) =>
      wrapCell(cell, columnWidths[ci]!, isHard).length
    ), 1)
  ), 0)

  const useVertical = tallestRow > maxRowLinesThreshold
    || (cols != null && maxLineWidth > cols - TABLE_PADDING_LEFT - SAFETY_MARGIN)

  if (useVertical) {
    // Edge cases
    if (normalizedRows.length <= 1) {
      // Header-only table — just render header as text
      return (
        <Box flexDirection="column" key={k} paddingLeft={TABLE_PADDING_LEFT}>
          <Text bold color={t.color.accent} wrap="wrap-trim">
            {normalizedRows[0]!.map(h => stripInlineMarkup(h)).join(' · ')}
          </Text>
        </Box>
      )
    }

    const headers = normalizedRows[0]!
    const dataRows = normalizedRows.slice(1)
    const sepWidth = Math.max(1, cols ? Math.min(cols - TABLE_PADDING_LEFT - 1, 40) : 40)

    return (
      <Box flexDirection="column" key={k} paddingLeft={TABLE_PADDING_LEFT}>
        {dataRows.map((row, ri) => (
          <Fragment key={ri}>
            {ri > 0 ? (
              <Text color={t.color.muted} dimColor>{'─'.repeat(sepWidth)}</Text>
            ) : null}
            {headers.map((header, ci) => {
              const cell = row[ci] ?? ''
              const label = stripInlineMarkup(header) || `Col ${ci + 1}`
              return (
                <Text key={ci} wrap="wrap-trim">
                  <Text bold color={t.color.accent}>{label}:</Text>
                  {' '}{stripInlineMarkup(cell)}
                </Text>
              )
            })}
          </Fragment>
        ))}
      </Box>
    )
  }

  // ... horizontal render continues (from Task 3) ...
```

**Step 2: Run repro tests**

```bash
cd ui-tui && node_modules/.bin/vitest run src/__tests__/tableFuzz.test.ts 2>&1 | grep -A 15 "extreme-disparity @ 40"
cd ui-tui && node_modules/.bin/vitest run src/__tests__/tableFuzz.test.ts 2>&1 | grep -A 15 "kitchen-sink @ 60"
```

Expected: extreme-disparity and kitchen-sink fixtures at narrow widths show vertical key-value format.

**Step 3: Full suite**

```bash
cd ui-tui && node_modules/.bin/vitest run 2>&1 | tail -5
```

**Commit:**

```bash
git add ui-tui/src/components/markdown.tsx
git commit -m "feat(tui): vertical key-value fallback with scaled threshold + safety check"
```

**⚔ Adversarial review gate (Phase 4):**

```bash
cd /home/daimon/github/hermes-agent/.worktrees/hermes-1f95f66a
claude -p --model claude-opus-4-6 "Review all changes to ui-tui/src/components/markdown.tsx. The renderTable function was rewritten to be width-aware. Focus on: (1) correctness of three-tier column width calculation including remainder distribution, (2) wrapCell grapheme handling, (3) the safety check triggering vertical fallback, (4) edge cases (header-only, ragged rows, 1-column, empty cells, cols=undefined), (5) cache key including cols, (6) no inline markdown in wrapped cells is intentional. Read the actual file, ui-tui/src/__tests__/tableFuzz.test.ts fixtures, and compare approach with ~/github/free-code/src/components/MarkdownTable.tsx."
```

---

## Phase 5: Structural tests + deterministic E2E

### Task 5: Update test helpers and add structural assertions

**Objective:** Fix `renderAtWidth` to pass `cols` (critical — without it, tests never exercise new code). Add assertions that would have caught the original bugs.

**Files:**
- Modify: `ui-tui/src/__tests__/tableRepro.test.ts`
- Modify: `ui-tui/src/__tests__/tableFuzz.test.ts`

**Step 1: Fix renderAtWidth in BOTH test files**

```typescript
// Pass cols to Md so the width-aware code path is exercised:
const node = React.createElement(
  Box,
  { width: columns },
  React.createElement(Md, { cols: columns, t, text: md })
)
```

**Step 2: Add structural assertions to tableRepro**

```typescript
import { stringWidth } from '@hermes/ink'

// After each vis() call, add:

// Every rendered line fits within the allocated width
for (const line of lines) {
  expect(stringWidth(line)).toBeLessThanOrEqual(width)
}

// Separator is at most 1 rendered line (not wrapped across 2+)
const sepLines = lines.filter(l => /^\s*[─\s]+$/.test(l) && l.includes('─'))
expect(sepLines.length).toBeLessThanOrEqual(1)

// No data rows contain ─ (separator bleed)
const sepIdx = lines.findIndex(l => /^\s*[─\s]+$/.test(l))
if (sepIdx >= 0) {
  const dataLines = lines.slice(sepIdx + 1).filter(l => l.trim())
  for (const dl of dataLines) {
    expect(dl).not.toMatch(/─/)
  }
}
```

**Step 3: Add overflow assertion to tableFuzz**

```typescript
import { stringWidth } from '@hermes/ink'

// After vis():
for (const line of lines) {
  expect(stringWidth(line)).toBeLessThanOrEqual(width)
}
```

**Step 4: Run**

```bash
cd ui-tui && node_modules/.bin/vitest run src/__tests__/tableRepro.test.ts src/__tests__/tableFuzz.test.ts 2>&1 | tail -10
```

**Commit:**

```bash
git add ui-tui/src/__tests__/tableRepro.test.ts ui-tui/src/__tests__/tableFuzz.test.ts
git commit -m "test(tui): structural assertions + cols in renderAtWidth for table tests"
```

### Task 6: Deterministic tmux E2E

**Objective:** Verify the fix in the real TUI by pasting fixed markdown tables (not model-generated) at 60/80/120 cols. Run from this worktree so the built TUI uses our code.

**Files:**
- No new files

**Step 1: Build TUI from worktree**

```bash
cd /home/daimon/github/hermes-agent/.worktrees/hermes-1f95f66a/ui-tui && npm run build
```

**Step 2: Launch hermes in tmux at 80 cols**

```bash
tmux kill-session -t tbl-e2e 2>/dev/null
tmux new-session -d -s tbl-e2e -x 80 -y 50
sleep 3
tmux send-keys -t tbl-e2e "cd /home/daimon/github/hermes-agent/.worktrees/hermes-1f95f66a && source /home/daimon/github/hermes-agent/.venv/bin/activate && HERMES_HOME=/home/daimon/.hermes/profiles/table-repro/ python -m hermes_cli.main --tui --yolo" Enter
sleep 15
```

**Step 3: Paste a fixed markdown table directly**

Rather than asking the model to generate tables, paste a deterministic fixture:

```bash
# Paste a fixed markdown table — instruct model to echo it verbatim
tmux send-keys -t tbl-e2e "Do not use tools. Reply with exactly this markdown table and no other text:

| Project | Description | Stack | Timeline | Budget | Status |
|---------|-------------|-------|----------|--------|--------|
| E-commerce Platform | Modern shopping experience | React, Node, Postgres | 6 months | \$150K-200K | In Progress |
| Mobile Banking | Secure transactions | Flutter, Firebase | 8 months | \$300K-400K | Planning |" Enter
sleep 30
tmux capture-pane -t tbl-e2e -p > /tmp/e2e-80col.txt
cat /tmp/e2e-80col.txt
```

**Step 4: Resize and verify**

```bash
tmux resize-window -t tbl-e2e -x 60 -y 50
sleep 2
# Send same table at 60 cols
tmux send-keys -t tbl-e2e "same table again" Enter
sleep 30
tmux capture-pane -t tbl-e2e -p > /tmp/e2e-60col.txt

tmux resize-window -t tbl-e2e -x 120 -y 50
sleep 2
tmux send-keys -t tbl-e2e "same table again" Enter
sleep 30
tmux capture-pane -t tbl-e2e -p > /tmp/e2e-120col.txt
```

**Step 5: Cleanup**

```bash
tmux kill-session -t tbl-e2e
```

**Verify in captured output:**
- [ ] 80 cols: columns shrunk, text wraps within cells, separator is 1 line
- [ ] 60 cols: vertical key-value format (table too wide)
- [ ] 120 cols: table fits or columns shrunk slightly, readable

---

## Phase 6 (deferred): Inline markdown in wrapped cells

**Not in this patch.** Wrapped table cells render as plain text via `stripInlineMarkup`. Preserving bold/italic/code/links inside wrapped cells requires ANSI-aware wrapping — the approach `free-code` uses at `MarkdownTable.tsx` L44-L62 (`wrapText` → `wrapAnsi`). This is a separate follow-up because:

1. `wrapAnsi` is not exported from `@hermes/ink`'s public API
2. Our cell content is markdown text (not yet rendered to ANSI), so we'd need to either format to ANSI first then wrap (like `free-code`), or implement markdown-aware wrapping
3. The width-correctness fix is more important than formatting preservation

**TODO comment in code:**

```typescript
// TODO: wrapped cells render as plain text (stripInlineMarkup).
// Follow-up: format to ANSI via MdInline, then wrap with wrapAnsi.
// See free-code/src/components/MarkdownTable.tsx L44-L62 for approach.
```

---

## Final commit message

```
fix(tui): width-aware markdown table rendering with vertical fallback

Tables now degrade gracefully at any terminal width:
- Three-tier column sizing (ideal → proportional shrink → hard scale)
- Cell text wraps within allocated column widths
- Full-line string rendering prevents Ink from reflowing table layout
- Vertical key-value fallback when rows exceed scaled line threshold
- Post-render safety check catches rounding/resize edge cases

Wrapped cells render as plain text (no inline markdown preservation).
Follow-up for ANSI-aware wrapping to preserve formatting.

Tested with 110 vitest fixtures across 4-6 terminal widths (40-160 cols)
and deterministic tmux E2E at 60/80/120 cols.
```
