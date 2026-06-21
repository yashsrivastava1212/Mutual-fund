---
name: Premium Wealth
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#44474d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#75777e'
  outline-variant: '#c4c6ce'
  surface-tint: '#4d5f7d'
  primary: '#000615'
  on-primary: '#ffffff'
  primary-container: '#0b1f3a'
  on-primary-container: '#7587a7'
  inverse-primary: '#b5c7ea'
  secondary: '#0051d5'
  on-secondary: '#ffffff'
  secondary-container: '#316bf3'
  on-secondary-container: '#fefcff'
  tertiary: '#000801'
  on-tertiary: '#ffffff'
  tertiary-container: '#00250b'
  on-tertiary-container: '#009b44'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#b5c7ea'
  on-primary-fixed: '#071c36'
  on-primary-fixed-variant: '#364764'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#7ffc97'
  tertiary-fixed-dim: '#62df7d'
  on-tertiary-fixed: '#002109'
  on-tertiary-fixed-variant: '#005320'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  container-max: 1280px
  gutter: 24px
  margin-desktop: 48px
  margin-mobile: 16px
  stack-xs: 4px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 24px
  stack-xl: 48px
---

## Brand & Style
The brand personality is authoritative yet accessible, focusing on clarity, precision, and institutional trust. The target audience includes individual investors and financial planners who require high data density without cognitive overload. 

This design system utilizes a **Corporate / Modern** aesthetic with a lean toward **Minimalism**. It prioritizes legibility and structural hierarchy to ensure complex financial data feels manageable. The emotional response should be one of confidence, stability, and professional-grade sophistication, achieved through generous whitespace, a constrained color palette, and high-quality typographic detailing.

## Colors
The palette is anchored by a deep Navy primary to evoke institutional credibility. The Secondary Blue is used for interactive elements and highlights, while the semantic colors (Green, Red, Amber) are strictly reserved for data visualization and status indicators.

- **Primary Navy**: Use for headers, primary buttons, and heavy navigational elements.
- **Secondary Blue**: Use for text links, selection states, and primary call-to-action accents.
- **Surface**: The background follows a tiered approach with a light grey base (#F8FAFC) and pure white (#FFFFFF) for elevated content containers.

## Typography
The system employs a dual-font strategy: **Plus Jakarta Sans** for headlines to provide a modern, slightly softer character, and **Inter** for all body text and data points to maximize legibility and systematic precision.

- **Scale**: Use `display-lg` exclusively for page titles. `headline-md` and `sm` are for section headers and card titles respectively.
- **Data Display**: For tabular data and fund performance figures, use `body-md` with tabular lining figures (monospaced numbers) to ensure columns align perfectly.
- **Labels**: Small uppercase labels are used for metadata and category tags to differentiate them from actionable text.

## Layout & Spacing
The layout uses a **Fixed Grid** model for desktop, centered within the viewport. 

- **Desktop (1200px+)**: 12-column grid, 24px gutters, 48px side margins.
- **Tablet (768px - 1199px)**: 8-column grid, 20px gutters, 32px side margins.
- **Mobile (Up to 767px)**: 4-column grid, 16px gutters, 16px side margins.

Vertical rhythm is maintained through a strictly defined stack scale. Use `stack-md` (16px) for internal card padding and `stack-lg` (24px) for spacing between major sections or cards.

## Elevation & Depth
Depth is conveyed through **Tonal Layers** and **Ambient Shadows** to differentiate between the background and interactive surfaces.

- **Level 0 (Base)**: `#F8FAFC` background.
- **Level 1 (Cards)**: Pure white `#FFFFFF` surface with a 1px border of `#E2E8F0`.
- **Level 2 (Hover/Active)**: Low-opacity ambient shadow (`0px 4px 20px rgba(11, 31, 58, 0.05)`) applied to cards on hover to indicate interactivity.
- **Level 3 (Modals/Dropdowns)**: Higher contrast shadow with a slight Navy tint to ensure separation from the content below.

Avoid heavy black shadows; all depth effects should use a hint of the Primary Navy to maintain the premium color harmony.

## Shapes
The design system uses a **Rounded** (Level 2) logic to soften the analytical nature of the data. 

- **Core Radius**: 12px (0.75rem) for cards, input fields, and main containers.
- **Inner Elements**: 8px (0.5rem) for smaller items like buttons or internal nested elements.
- **Pill**: Used exclusively for status chips (e.g., "High Growth", "Equity") to distinguish them from actionable buttons.

## Components
Consistent implementation of these components ensures a professional, data-led experience:

- **Buttons**:
  - **Primary**: Solid Navy (#0B1F3A) with white text. 12px radius.
  - **Secondary**: Outlined with 1px Navy or Blue border. Transparent background.
- **Cards**: Pure white background, 12px border radius, 1px `#E2E8F0` border. Use for fund summaries and comparison modules.
- **Charts**:
  - **Line Charts**: Use 2px stroke width with Secondary Blue. Areas should have a very subtle gradient fade.
  - **Donut Charts**: Use a 12px stroke width with a palette of Primary Navy, Secondary Blue, and Neutrals for asset allocation.
- **Star Ratings**: Solid Amber (#D97706) for filled stars, light grey for empty stars. 16px icon size.
- **Input Fields**: 1px `#E2E8F0` border, 12px radius. On focus, the border transitions to Secondary Blue with a 2px outer "halo" of the same color at 10% opacity.
- **Data Tables**: Remove vertical borders. Use horizontal dividers (`#F1F5F9`). Row hover states should use a subtle `#F8FAFC` background shift.