---
name: JomTransit
colors:
  surface: '#fbf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fbf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3f2'
  surface-container: '#f0eded'
  surface-container-high: '#eae8e7'
  surface-container-highest: '#e4e2e1'
  on-surface: '#1b1c1c'
  on-surface-variant: '#3f4a36'
  inverse-surface: '#303030'
  inverse-on-surface: '#f3f0f0'
  outline: '#6f7b64'
  outline-variant: '#becbb1'
  surface-tint: '#2b6c00'
  primary: '#2b6c00'
  on-primary: '#ffffff'
  primary-container: '#58cc02'
  on-primary-container: '#1e5000'
  inverse-primary: '#6be026'
  secondary: '#006590'
  on-secondary: '#ffffff'
  secondary-container: '#2fb8ff'
  on-secondary-container: '#004666'
  tertiary: '#8c5000'
  on-tertiary: '#ffffff'
  tertiary-container: '#ff9c27'
  on-tertiary-container: '#683a00'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#87fe45'
  primary-fixed-dim: '#6be026'
  on-primary-fixed: '#082100'
  on-primary-fixed-variant: '#1f5100'
  secondary-fixed: '#c8e6ff'
  secondary-fixed-dim: '#88ceff'
  on-secondary-fixed: '#001e2e'
  on-secondary-fixed-variant: '#004c6e'
  tertiary-fixed: '#ffdcbf'
  tertiary-fixed-dim: '#ffb872'
  on-tertiary-fixed: '#2d1600'
  on-tertiary-fixed-variant: '#6a3b00'
  background: '#fbf9f8'
  on-background: '#1b1c1c'
  surface-variant: '#e4e2e1'
  status-critical: '#FF4B4B'
  status-critical-dark: '#EA2B2B'
  surface-soft: '#F7F7F7'
  line-kelana: '#E31837'
  line-ampang: '#F7941D'
  line-kajang: '#007A33'
  line-putrajaya: '#F4C300'
  line-monorail: '#8DC63F'
  line-ktm: '#0066B3'
  success-soft: '#D7FFB8'
  ink-secondary: '#777777'
typography:
  display-logo:
    fontFamily: Nunito Sans
    fontSize: 20px
    fontWeight: '900'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-card:
    fontFamily: Nunito Sans
    fontSize: 20px
    fontWeight: '900'
    lineHeight: '1.2'
  headline-card-mobile:
    fontFamily: Nunito Sans
    fontSize: 18px
    fontWeight: '900'
    lineHeight: '1.2'
  title-section:
    fontFamily: Nunito Sans
    fontSize: 17px
    fontWeight: '900'
    lineHeight: '1.3'
  body-bold:
    fontFamily: Nunito Sans
    fontSize: 15px
    fontWeight: '900'
    lineHeight: '1.4'
  body-main:
    fontFamily: Nunito Sans
    fontSize: 15px
    fontWeight: '600'
    lineHeight: '1.4'
  label-action:
    fontFamily: Nunito Sans
    fontSize: 14px
    fontWeight: '800'
    lineHeight: '1.2'
  label-small:
    fontFamily: Nunito Sans
    fontSize: 13px
    fontWeight: '800'
    lineHeight: '1.1'
  caption:
    fontFamily: Nunito Sans
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1.4'
  timestamp:
    fontFamily: Nunito Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: '1.1'
  micro-tag:
    fontFamily: Nunito Sans
    fontSize: 10px
    fontWeight: '900'
    lineHeight: '1'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  gap-xs: 4px
  gap-sm: 8px
  gap-md: 12px
  gap-lg: 16px
  page-margin: 16px
  touch-target-min: 44px
---

## Brand & Style

The design system adopts a **Playful Commuter** aesthetic, heavily influenced by the high-clarity, gamified UX of modern educational apps. The goal is to transform the stress of Malaysian transit delays into a manageable, tactile experience that feels like a "friendly assistant" in your pocket.

The style is **Tactile Flat (Neubrutalist-lite)**. It prioritizes physical metaphors—buttons that look like they can be pressed and cards that sit firmly on the page. The personality is honest and local, using Malaysian-centric terminology (BM/EN bilingual labels) and mascot-driven communication to soften the blow of service disruptions.

**Key Visual Principles:**
- **Clarity over Slop:** No generic gradients or "soft" shadows. Everything is defined by thick, purposeful lines.
- **Urgency with Kindness:** Critical alerts are bold and red but wrapped in rounded, friendly shapes.
- **High Density, High Organization:** Information is packed tightly for the "one-handed rush hour" user, but separated by clear hierarchical chunks.

## Colors

The palette is vibrant and functional, using high-contrast saturation to denote action and status.

- **Primary Green (#58CC02):** Used for positive actions, "Live" indicators, and the "Looking quiet" status. It represents the "Go" signal of the city.
- **Secondary Blue (#1CB0F6):** Used for navigation, active tab states, and GPS-related indicators (KTM).
- **Tertiary Orange (#FF9600):** Used for alerts and rider-sourced warnings.
- **Official Line Colors:** These are inviolable brand assets. They must be used as the primary identifier (stripes/pills) for their respective transit lines to ensure instant recognition by daily commuters.

**Implementation Note:** All chromatic colors must have a "Dark" counterpart (approximately 15-20% darker) used exclusively for the 2px borders and 4px bottom shadows to maintain the tactile depth.

## Typography

This design system uses **Nunito Sans** exclusively to maintain a chunky, rounded, and approachable feel. The typography is heavily weighted (weights 600-900) to stand up against the thick 2px borders of the UI.

- **Bilingual Labels:** Use a "Primary / Secondary" lockup for BM/EN support. The Primary language (User preference) uses `body-bold`, while the secondary translation uses `caption` in `ink-secondary` immediately below or beside it.
- **Hierarchy:** Importance is conveyed through weight (900 for titles) rather than just size, ensuring legibility on vibrating trains or in bright sunlight.
- **Micro-tags:** Always rendered in Uppercase with slight letter spacing for status badges and "Riding Now" indicators.

## Layout & Spacing

The system uses a **Fixed Grid** model optimized for mobile-first consumption. The maximum content width is **420px**, centered on larger screens to mimic the feel of a handheld device.

**Layout Rhythm:**
- **Vertical Stack:** The Home screen follows a strict top-down hierarchy: Glance Card → Live Feed → Filter Chips → Line Board.
- **Horizontal Feed:** "Live Today" signals are presented in a horizontal scrolling carousel to allow for quick scanning without pushing the "Line Board" too far down the page.
- **Touch Targets:** All interactive elements (buttons, chips, tabs) must maintain a minimum height of `44px` to accommodate one-handed operation during a commute.
- **Borders:** A consistent `2px` border is applied to all cards and interactive elements, effectively acting as the primary divider instead of traditional hairline rules.

## Elevation & Depth

This design system rejects blurred shadows in favor of **Solid Offset Shadows**. This creates a tactile, mechanical feel—like physical buttons on a dashboard.

- **Shadow Character:** Use a `0 4px 0` solid shadow for primary interactive elements (buttons, active chips). The shadow color should be the "Dark" version of the element's border color (e.g., a Green button gets a Dark Green shadow).
- **Standard Cards:** Use a `0 3px 0` solid shadow in `named_colors.surface-soft` or a light gray to lift them off the background.
- **Pressed State:** When an element is active or tapped, the shadow should transition to `0 0 0` (0px offset) and the element should translate Y by 2px-4px to simulate a physical "click."

## Shapes

The shape language is friendly and exuberant.

- **Standard Roundedness:** `0.5rem (8px)` is the base for small tags and status badges.
- **Container Roundedness:** `1rem (16px)` is used for all main cards, the Glance card, and the Map container.
- **Interactive Elements:** Buttons and input fields use `0.875rem (14px)` to feel slightly more specialized than standard cards.
- **Pills:** Use `999px` (fully rounded) for filter chips and the "Riding Now" badges to distinguish them from structural cards.
- **Icons:** Mascot containers and "Live" dots are always circular (`50%`).

## Components

### Buttons & Chips
- **Chunky Buttons:** 2px border, 4px bottom shadow. Text is `label-action` centered. 
- **Filter Chips:** Pill-shaped, 2px border. Unselected: White background, gray border. Selected: `secondary_blue` background, `secondary_blue_dark` border/shadow.

### Cards
- **Glance Card:** Large hero card at the top. Uses a background color corresponding to system health (Green for quiet, Orange/Red for trouble). Includes a mascot emoji.
- **Signal Cards:** Used in the "Live Today" feed. Must contain: 
    1. **Time + Source:** (e.g., "12m ago · Threads") using `timestamp` style.
    2. **Riding Now Badge:** A high-contrast pill (Red background) if live impact is detected.
    3. **Line Stripe:** A 6px vertical bar on the left edge using the `Official Line Color`.

### Line Board Rows
- **Structure:** 2px border, white background.
- **Left Rail:** 8px thick vertical stripe of the `Official Line Color`.
- **Status Pill:** A small rounded badge on the right (e.g., "Delay" in Orange).

### Map Controls
- **Layer Chips:** Floating horizontal list of pills with icons for LRT, MRT, Bus GPS.
- **Rider Pins:** Circular markers with 2px borders. Red/Orange for reports, Blue/Orange for live GPS.

### Bilingual Labels
- All persistent UI labels (e.g., "Plan Route / Rancang Perjalanan") should display both languages. Use a smaller, lighter font for the English translation if BM is primary, or vice versa.