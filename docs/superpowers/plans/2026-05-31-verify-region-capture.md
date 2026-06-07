# Verify Region Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the PDF region capture so clicking "✓ Verify" on a field automatically captures a screenshot of the highlighted PDF region and stores it as evidence alongside the correction.

**Architecture:** `DocumentViewer` holds all the pieces — the PDF canvas ref, the active match coordinates, the current page, and the page viewport. It creates a `captureCurrentHighlight()` function using `useRegionCapture` and passes it down to `SchemaReviewPane`, which calls it inside `handleVerify` before saving the correction. `ExtractionField` gets minor feedback improvements (page reference after verify, auto-locate status hint).

**Tech Stack:** React, react-pdf/pdf.js, useRegionCapture hook (already built at `frontend/src/hooks/useRegionCapture.js`), existing SchemaReviewPane + ExtractionField components.

---

## Background

The `useRegionCapture` hook was built and works correctly — it can crop a region from the react-pdf canvas as a base64 PNG. But it was never connected to the verify flow. Currently clicking "✓ Verify" saves `{type: 'auto_highlight', note: '...'}` with no `page`, `region`, or `image_b64`. The full evidence chain requires all four fields.

All the pieces already exist:
- `pageContainerRef` — ref on the div wrapping `<Page>` in DocumentViewer
- `activeMatch` — `{x, y, width, height}` from `useFieldHighlight`
- `pageViewport` — pdfjs viewport with `.height` for y-axis flip
- `currentPage` — current page number
- `useRegionCapture(pageContainerRef)` — returns `{ capture, startDraw }`

The work is connecting them.

---

## File Map

**Modify:**
- `frontend/src/pages/workspace/DocumentViewer.jsx` — re-import useRegionCapture, create captureCurrentHighlight, pass to SchemaReviewPane
- `frontend/src/components/documents/SchemaReviewPane.jsx` — accept captureCurrentHighlight prop, call it in handleVerify for auto_highlight type
- `frontend/src/components/documents/ExtractionField.jsx` — show page reference after verify, show auto-locate status hint

---

## Task 1: DocumentViewer — create captureCurrentHighlight

**Files:**
- Modify: `frontend/src/pages/workspace/DocumentViewer.jsx`

- [ ] **Step 1: Re-import useRegionCapture and create the capture function**

At line 13, replace the comment+deferred note:
```javascript
// useRegionCapture deferred: manual draw mode (drag-to-capture) needs a callback
// threaded from DocumentViewer → SchemaReviewPane → ExtractionField. Follow-on task.
```

With the actual import:
```javascript
import { useRegionCapture } from '../../hooks/useRegionCapture'
```

Then add these two lines immediately after the existing `useFieldHighlight` call (after line 118):

```javascript
  const { capture } = useRegionCapture(pageContainerRef)

  const captureCurrentHighlight = useCallback(() => {
    if (!activeMatch || !pageViewport) return null
    const image_b64 = capture(activeMatch, pageViewport.height, 1.0)
    return {
      page: currentPage,
      region: activeMatch,
      image_b64,
    }
  }, [activeMatch, pageViewport, currentPage, capture])
```

- [ ] **Step 2: Pass captureCurrentHighlight to SchemaReviewPane**

Find the `<SchemaReviewPane` render in DocumentViewer. Add `captureCurrentHighlight` as a prop:

```jsx
              <SchemaReviewPane
                schema={schema}
                extractions={extractions}
                workspaceId={workspaceId}
                documentId={documentId}
                onFieldFocus={handleFieldFocus}
                captureCurrentHighlight={captureCurrentHighlight}
                onSaveComplete={() => {
                  getExtractions(workspaceId, documentId).then((r) => setExtractions(r.data))
                }}
              />
```

- [ ] **Step 3: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: clean build, no errors.

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/pages/workspace/DocumentViewer.jsx && git commit -m "feat: create captureCurrentHighlight from active PDF match, pass to SchemaReviewPane"
```

---

## Task 2: SchemaReviewPane — capture region in handleVerify

**Files:**
- Modify: `frontend/src/components/documents/SchemaReviewPane.jsx`

- [ ] **Step 1: Accept captureCurrentHighlight prop**

In the component props destructuring (line 20-23), add `captureCurrentHighlight`:

```jsx
export default function SchemaReviewPane({
  schema, extractions, workspaceId, documentId,
  onFieldFocus, onSaveComplete, captureCurrentHighlight,
}) {
```

- [ ] **Step 2: Call capture in handleVerify before building evidence**

Find `handleVerify` (starts around line 60). Replace the evidence construction block:

```javascript
  const handleVerify = useCallback(async (fieldName, value, note, evidenceType, skipCallback = false) => {
    // For auto_highlight: capture the currently highlighted PDF region
    let captureData = null
    if (evidenceType === 'auto_highlight' && captureCurrentHighlight) {
      captureData = captureCurrentHighlight()
    }

    const evidence = evidenceType
      ? {
          type: evidenceType,
          note: note || undefined,
          ...(captureData || {}),
        }
      : null

    const extraction = extractionByName[fieldName]

    if (extraction) {
      await correctExtraction(workspaceId, documentId, extraction.id, value, evidence)
    } else {
      const field = (schema.fields || []).find((f) => f.name === fieldName)
      await createExtraction(
        workspaceId, documentId, fieldName, value,
        field?.type || 'text', schema.id, evidence
      )
    }

    setPendingChanges((prev) => {
      const next = { ...prev }
      delete next[fieldName]
      return next
    })
    if (!skipCallback) onSaveComplete()
  }, [extractionByName, schema, workspaceId, documentId, onSaveComplete, captureCurrentHighlight])
```

Note: `captureCurrentHighlight` added to the dependency array.

- [ ] **Step 3: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: clean build.

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/components/documents/SchemaReviewPane.jsx && git commit -m "feat: capture highlighted PDF region on verify — stores page, region coords, and image_b64 in evidence"
```

---

## Task 3: ExtractionField — feedback improvements

**Files:**
- Modify: `frontend/src/components/documents/ExtractionField.jsx`

This task adds two small feedback improvements:
1. After verify, show "✓ Verified · pg. N" if the evidence captured a page number
2. When a field is active and focused, show "↑ located on PDF" or "⚠ not found on PDF" hint

- [ ] **Step 1: Read ExtractionField to find the verified badge and active state**

The verified badge is at the line with `{verified && <span ...>✓ Verified</span>}`. The `isActive` field determines the active label color. The `extraction?.evidence` is available if the field was previously verified.

- [ ] **Step 2: Update the verified badge to show page reference**

Find the verified badge in the label row:
```jsx
          {verified && <span className="text-xs text-green-400 font-medium">✓ Verified</span>}
```

Replace with:
```jsx
          {verified && (
            <span className="text-xs text-green-400 font-medium">
              ✓ Verified{extraction?.evidence?.page ? ` · pg. ${extraction.evidence.page}` : ''}
            </span>
          )}
```

- [ ] **Step 3: Add auto-locate status hint on active field**

In the label row, after the field name label and before the confidence pills, add a subtle hint when the field is active. Find the label element:

```jsx
        <label className={`text-xs font-medium ${isActive ? 'text-blue-400' : 'text-slate-500'}`}>
          {field.name}
          {field.required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
```

This component doesn't have direct access to `matches.length`. We need to pass an `hasMatch` prop from SchemaReviewPane that indicates whether the current highlight found the value.

**Simpler approach — skip the auto-locate hint for now.** The page reference in "✓ Verified · pg. N" already tells the operator the capture worked. The no-match case will be addressed when manual draw is wired. Skip this sub-step.

- [ ] **Step 4: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: clean build.

- [ ] **Step 5: Restart Docker frontend to pick up changes**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && docker-compose restart frontend && sleep 8 && docker-compose logs --tail=3 frontend 2>&1 | grep -v "level=warning"
```

Expected: `➜  Local:   http://localhost:5173/`

- [ ] **Step 6: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/components/documents/ExtractionField.jsx && git commit -m "feat: show page reference in verified badge — '✓ Verified · pg. N'" && git push
```

---

## Self-Review

### Spec Coverage

| Design Requirement | Task |
|---|---|
| Clicking Verify captures highlighted PDF region | Task 1 (captureCurrentHighlight), Task 2 (handleVerify calls it) |
| Evidence includes page, region coords, image_b64 | Task 2 (spread captureData into evidence object) |
| "Source region captured" feedback | Task 3 (✓ Verified · pg. N) |
| captureCurrentHighlight returns null when no active match | Task 1 (null guard: `if (!activeMatch \|\| !pageViewport) return null`) |

### Deferred (out of scope for this plan)
- Manual draw wiring (drag-to-select region when text search fails)
- Auto-locate success/failure indicator in field label ("↑ located · pg. N" vs "⚠ not found")
- Tab key navigation between fields
- "Source region captured" thumbnail image preview in field

### Type Consistency
- `captureCurrentHighlight: () => {page, region, image_b64} | null` — consistent across DocumentViewer definition, SchemaReviewPane prop, and handleVerify call ✅
- `evidence: {type, note, page?, region?, image_b64?}` — consistent with the `evidence JSONB` column spec ✅
- `useRegionCapture(pageContainerRef)` returns `{ capture, startDraw }` — only `capture` is used here ✅
