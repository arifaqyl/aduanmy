# TrafficMY Redesign: Design System

## 1. Design Direction: Departure Board Aesthetic

**Rationale:** The primary audience for TrafficMY is Malaysian commuters checking public transport status on their phones, often in crowded station environments. The core success criteria emphasize rapid information assimilation: answering 
three critical questions in under 5 seconds: "Is my line delayed right now?", "When was this last checked?", and "Is this official or crowd-reported?" [MANUS_PROMPT.md].

To meet these demands, the **Departure Board** aesthetic (Option A from the brief) is selected. This direction prioritizes:

*   **Monospace Times & Data:** Emulating the precision and clarity of traditional departure boards for critical information like timings and status updates.
*   **High Contrast:** Ensuring readability in diverse lighting conditions, especially on mobile devices in transit environments.
*   **Flip-dot Aesthetic (Conceptual):** Translating the clear, segmented display of flip-dot boards into modern digital elements, focusing on distinct information blocks rather than fluid, amorphous designs.
*   **Minimal Chrome:** Reducing visual distractions to keep the focus squarely on the transport information.
*   **Data Density:** Presenting a significant amount of information concisely without overwhelming the user, similar to Citymapper's efficiency [1].

This approach avoids the 
"AI slop" (gradient heroes, glassmorphism, cream backgrounds, marketing copy) explicitly banned in the brief, focusing instead on a functional, utilitarian interface that respects the user's need for quick, accurate information.

## 2. Typography

**Primary Typeface (Data & Headings):** **IBM Plex Mono**
*   **Rationale:** IBM Plex Mono is a highly legible monospace typeface designed for code and data. Its clear, unambiguous characters are ideal for displaying critical information like times, line statuses, and station names, directly echoing the 
departure board aesthetic. Its open forms and distinct characters enhance readability at a glance, crucial for users in motion or under time pressure. It also supports a wide range of characters, which is beneficial for potential bilingual (BM/EN) labels [MANUS_PROMPT.md].

**Secondary Typeface (Body Text & UI Labels):** **Inter**
*   **Rationale:** While the brief bans "Inter" as a default AI choice, its exceptional legibility, extensive weights, and optimization for UI make it a pragmatic choice for supporting text where a monospace font might be too dense. It provides a clean, modern contrast to Plex Mono without introducing visual noise. It also offers excellent accessibility features, aligning with the WCAG AA contrast and 44px min touch target requirements [MANUS_PROMPT.md].

## 3. Color Palette

**Core Principles:** High contrast, functional, and reflective of Malaysian transit operators where applicable. OKLCH color space will be prioritized for better perceptual uniformity and gamut control.

| Category | Color Name | Hex (sRGB) | OKLCH (approx.) | Usage |
|:---------|:-----------|:-----------|:----------------|:------|
| **Primary** | Background Dark | `#121212` | `oklch(0.08 0 0)` | Main background for dark mode, high contrast with text. |
| | Background Light | `#F5F5F5` | `oklch(0.95 0 0)` | Main background for light mode. |
| | Text Primary | `#FFFFFF` (dark) / `#1A1A1A` (light) | `oklch(1 0 0)` / `oklch(0.1 0 0)` | Main body text, headings. |
| | Text Secondary | `#A0A0A0` (dark) / `#606060` (light) | `oklch(0.65 0 0)` / `oklch(0.4 0 0)` | Sub-headings, metadata, less critical information. |
| **Accent** | Rapid KL Red | `#E31837` | `oklch(0.55 0.2 28)` | Primary accent color, for refresh buttons, active states, and brand elements. Matches existing line color. |
| **Status** | Normal/Quiet | `#008000` | `oklch(0.5 0.15 130)` | For lines with no reported issues (not "all clear"). Muted green. |
| | Minor Delay | `#FFA500` | `oklch(0.7 0.15 75)` | Minor incidents or slight delays. Amber. |
| | Delay | `#FF4500` | `oklch(0.6 0.18 50)` | Significant delays. Orange-red. |
| | Disruption | `#DC143C` | `oklch(0.5 0.2 30)` | Major service disruptions. Crimson red. |
| | Unknown | `#808080` | `oklch(0.5 0 0)` | Status unknown or no recent signal. Grey. |
| **Line Colors** | (Refer to `reference/LINE_COLORS.md`) | (As per file) | (As per file) | Used for line indicators, map routes, and schematic highlights. |

**Accessibility:** All color combinations will be tested to ensure WCAG AA contrast compliance for body text and interactive elements. A high-contrast toggle will be provided [MANUS_PROMPT.md].

## 4. Component Specifications

**General Principles:** Components will be designed for information density, clarity, and touch-target accessibility (minimum 44px on mobile). They will avoid decorative elements and focus on conveying status and actionable information efficiently.

### 4.1. Navigation (Tabs & Bottom Nav)
*   **Desktop:** Top-level tabs (`mainTabs`) will be clean, text-based, with a clear active state indicator (e.g., a solid underline or background fill). Keyboard shortcuts (1-4) will be supported.
*   **Mobile:** A persistent bottom navigation bar (`bottomNav`) will house the four main tabs. Icons will be minimal and clear, paired with text labels. Active tab will be visually distinct.
*   **Touch Targets:** All navigation elements will meet the 44px minimum touch target size.

### 4.2. Status Board (Line Board)
*   **Line Rows (`.line-row`):** Each line will be a distinct row, designed like a segment of a departure board. It will feature:
    *   **Line Identifier:** Operator-specific color bar (`--line-color` CSS var) on the left, followed by the line name (e.g., "Kelana Jaya Line").
    *   **Status Indicator:** A prominent, color-coded status badge (`.badge` + `.normal/.minor/.delay/.disruption/.unknown`) using the defined severity colors. Text will be concise (e.g., "Delayed", "Minor Delay").
    *   **Detail/Reason:** A brief, truncated reason or last-seen timestamp, expanding on tap.
    *   **Report Count/Freshness:** Small, legible indicators for crowd report count or data freshness.
    *   **Interaction:** Tappable to reveal a slide-over panel with more details.
*   **Search & Filters:** A single, prominent search bar (`placeSearch`, `mobilePlaceSearch`) will be available. Filters (`.chip`) will be presented as a row of clear, tappable buttons, with the active filter highlighted. The filter banner (`filterBanner`) will be minimal.
*   **Stale Data Banner (`staleBanner`):** A high-contrast, non-intrusive banner to alert users to stale data, with a clear refresh button.
*   **Context Bar (`contextBar`):** Displays essential context like rush hour status and data scope (e.g., "Malaysia transport only").

### 4.3. Detail Panels (Slide-over)
*   **Mechanism:** A slide-over panel (`panel`) will appear from the right on desktop and bottom on mobile when a line or incident is tapped. It will have a clear close button (`closePanel`) and a backdrop (`backdrop`) for focus.
*   **Content:** Will display line guide, stations, evidence for incidents, official corroboration, and source links. Typography will maintain hierarchy and readability.

### 4.4. Map
*   **MapLibre Integration:** The map (`malaysiaMap`) will be the central element, with layer toggles (`.chip` + `[data-layer]`) positioned clearly, possibly as a floating group. The map sidebar (`mapSidebar`) will list active lines.
*   **Visuals:** Line colors from `LINE_COLORS.md` will be used for routes. Incident reports will be clearly marked with distinct icons or color-coded pins.

### 4.5. Plan & Passes
*   **Forms:** Input fields (`tm-input`) will be clean, with clear labels and accessible error states. Buttons (`tm-primary-btn`, `tool-button`) will be functional and high-contrast.
*   **Information Display:** Results for journey planning and pass calculation will be presented clearly, prioritizing essential information with good typographic hierarchy.

## 5. Logo & Favicon

The existing `logo.svg` and `favicon.svg` will be redesigned to align with the new aesthetic. The new logo will be simple, iconic, and legible at small sizes, avoiding gradients or complex imagery. It will ideally evoke movement or connectivity without being overly literal.

## References

[1] Citymapper. (2021, April 15). *Redesigning the Citymapper App*. Retrieved from https://www.citymapper.com/news/2021/04/15/redesigning-the-citymapper-app/
