---
name: Migration Workbench
description: A precise, compact review surface for ERP data migration exceptions.
colors:
  pine: "#174640"
  pine-hover: "#215f56"
  teal: "#26756e"
  teal-soft: "#e2f1ee"
  amber: "#9c6900"
  amber-soft: "#fff5d8"
  red: "#b53635"
  red-soft: "#fff0ee"
  blue: "#235f84"
  blue-soft: "#edf5fa"
  page: "#f3f6f5"
  panel: "#ffffff"
  panel-alt: "#edf2f1"
  ink: "#1d3035"
  muted: "#5e6d73"
  line: "#d8e0df"
  pass: "#24604d"
  pass-soft: "#eaf4ee"
  pass-line: "#c9dfd1"
  focus-ring: "#397e75"
  selection: "#cde7df"
typography:
  headline:
    fontFamily: "'Chau Philomene One', 'Arial Narrow', system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.14
    letterSpacing: "-0.02em"
rounded:
  xs: "3px"
  sm: "4px"
  md: "5px"
components:
  button-primary:
    backgroundColor: "{colors.pine}"
    height: "2.1rem"
    padding: "0.25rem 0.55rem"
  queue-selected:
    backgroundColor: "{colors.teal-soft}"
    textColor: "{colors.pine}"
    height: "2.15rem"
    padding: "0.25rem 0.48rem"
  file-reference:
    backgroundColor: "#fbfcfc"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0.22rem 0.45rem"
  status-warning:
    backgroundColor: "{colors.amber-soft}"
    textColor: "{colors.amber}"
    rounded: "{rounded.sm}"
    padding: "0.25rem 0.52rem"
  status-error:
    backgroundColor: "{colors.red-soft}"
    textColor: "{colors.red}"
    rounded: "{rounded.sm}"
    padding: "0.25rem 0.52rem"
  search-input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
  record-card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.md}"
  mapping-card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.md}"
  audit-card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.md}"
  summary-card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.md}"
---

# Design System: Migration Workbench

## Overview

**Creative North Star: "The Reconciliation Desk"**

The visual system treats migration review as a focused desk for comparing evidence. Cool gray-green ground, white work surfaces, quiet rules, and compact labels keep dense financial data readable; deep pine gives the main action a clear anchor. Red, amber, and blue are reserved for semantic status, while teal marks selection and supporting actions.

The interface stays close to the established Streamlit UI for most controls and uses a distinct condensed face only for the lead finding title. Local/session context and the value-reveal control remain visible but secondary to the evidence. The approved exception-review comp is a useful expression of this visual language; its particular queue-and-detail composition is specific to that screen.

**Key Characteristics:**
- Cool, low-glare gray-green canvas with white, finely bordered work surfaces.
- Deep pine actions, teal selection, and text-labeled semantic status colors.
- Compact data tables, tabular numeric values, and one condensed finding-title accent.

## Colors

Cool paper and ink carry most of the interface. Deep pine anchors primary action; teal supports selection; status colors distinguish errors, warnings, information, and passing results.

### Primary
- **Deep Pine:** The brand and primary-action color, used on the run action and local/session cue.
- **Working Teal:** A supporting accent for selection markers and links; its pale tint supplies selected-row fills.

### Secondary
- **Warning Amber:** Used for warning pills and the compared-field highlight.
- **Error Red:** Used for error pills and exception emphasis.
- **Information Blue:** Reserved for informational status.

### Neutral
- **Cool Mist:** The page canvas that separates the work area from the app frame.
- **White:** Main card, table, and input surfaces.
- **Pale Header Fill:** Repeated across card headings to separate evidence sections without elevation.
- **Charcoal Ink:** Main text and values.
- **Slate Muted:** Supporting labels, captions, and secondary metadata.
- **Quiet Divider:** Thin table and panel rules.

### Semantic Signals
- **Passing Green:** A distinct pass treatment for clean reconciliation states.
- **Focus Teal:** A visible outline for keyboard focus.
- **Selection Wash:** The text-selection background.

**The Status by Meaning Rule.** Keep errors red, warnings amber, informational findings blue, and passing results green; pair each color with a visible status label.

## Typography

**Display Font:** 'Chau Philomene One' (with 'Arial Narrow', system-ui, sans-serif)
**Body Font:** Inherited Streamlit sans-serif stack; the app does not declare a project-owned body face.
**Label/Mono Font:** No separate label or mono family is declared.

**Character:** Most interface typography is compact and framework-native. The finding title is the single condensed display accent, tightened and weighted to create a clear reading anchor.

### Hierarchy
- **Headline** (700, 22px, 1.14): The general finding-title style; inside the case banner it is reduced to 1.1rem to fit beside status and position.
- **Body and labels:** Inherited Streamlit sizing, with locally declared utility and data labels generally between 0.67rem and 0.82rem.
- **Numeric values:** Use tabular numerals for facts and reconciliation totals where declared.

## Layout

The desktop Review page uses a compact three-column working split: navigation at 11%, exception queue at 20%, and selected finding detail at 69%. The top identity bar spans the app, while the file strip aligns with the detail area. Within that pane, paired source/target records sit side by side, followed by mapping, session activity, and reconciliation summary surfaces.

At widths below 1,051px, the six-column fact and summary grids reduce to three columns. Below 761px, the workspace stacks with detail before the queue, fact and summary grids reduce to two columns, and the file strip becomes vertical. The selected-finding controls stay on one row. Local CSS uses component-specific gaps and padding rather than a named spacing scale.

The approved exception-review mock expresses this queue-and-detail arrangement. Treat that arrangement as a composition for the Review surface, not as a required shell for File setup, Reconciliation, or Export.

## Elevation & Depth

The system is nearly flat: white panels sit on the cool page ground, with pale header bands and thin borders doing the separation. Standard cards do not use elevation shadows. The selected queue row uses a narrow inset teal marker as a state cue, not as surface lift.

**The Flat Surface Rule.** Separate evidence with tonal headers and borders; reserve the inset teal marker for the selected queue row and avoid ambient card shadows.

## Shapes

The form language is compact and lightly softened. Count chips use the smallest corner, file and status chips use the small corner, and evidence panels use the medium corner. Borders are thin and cool; table rows use horizontal rules, and the selected mapped field receives a soft amber band. Status pills remain compact rounded rectangles rather than full capsules.

## Components

### Buttons
Primary actions use deep pine with a compact label; the run action is full width within its toolbar cell. Secondary actions retain Streamlit's white, quiet-border treatment. The selected exception button changes to a pale teal fill with a left inset marker. Keyboard focus uses a clear outline.

### Chips
Status and count chips keep a short text label, a pale semantic fill, and a thin matching border. File references use a neutral bordered surface with a truncating filename and a muted row count.

### Cards / Containers
Record, mapping, audit, and summary containers share a white surface, fine border, and pale header band. Tables stay dense, with thin horizontal rules and no card shadow. The compared-field row is the targeted exception: it uses the warning wash to connect the mapping rule to the source and target values.

### Inputs / Fields
Search and other fields use a white fill with the shared divider color. Keyboard focus is a 3px teal outline with a 2px offset. The app does not add custom error or disabled treatments beyond Streamlit's control states.

### Navigation
Workspace navigation is a compact Streamlit radio list in the narrow first column. Its labels and control states remain framework-native; on small screens, the detail pane moves before the exception queue.

### Signature Component: Exception Evidence Stack
The Review detail area groups the finding title and status, six key facts, paired source/target record tables, mapping rule, in-memory session activity, and reconciliation totals. It is a screen-specific sequence for investigating one exception; it should not be copied as a universal page template.

## Do's and Don'ts

### Do:
- **Do** use deep pine for primary actions and teal for selected queue state.
- **Do** keep source and target records separate and use thin rules to support dense reading.
- **Do** pair each status color with a visible text label.
- **Do** keep the value-reveal control and its privacy note clear when local uploaded values are shown.

### Don't:
- **Don't** use red, amber, or blue as general decoration outside their status roles.
- **Don't** treat the Review page's 11/20/69 split as the global layout for every page.
- **Don't** add ambient shadows to standard evidence cards.
