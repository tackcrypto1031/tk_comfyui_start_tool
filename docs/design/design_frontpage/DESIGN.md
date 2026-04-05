```markdown
# Design System Document: The Monolith Protocol

## 1. Overview & Creative North Star: "The Obsidian Edge"
This design system is not a template; it is a digital architecture of light and shadow. The Creative North Star is **"The Obsidian Edge"**—a philosophy that treats the interface as a high-precision, futuristic instrument carved from volcanic glass. 

We move beyond "Dark Mode" into "Pure Black." By utilizing an absolute black base (`#000000`), we eliminate the "grey-box" fatigue of standard UIs. The aesthetic breaks the traditional grid through intentional sharp angles (0px radius) and high-contrast typographic layering, creating an environment that feels both elite and utilitarian. This is an editorial approach to technical software: cold, precise, and undeniably premium.

---

## 2. Colors & Tonal Depth
In this system, color is not used for decoration—it is used for data-signaling and architectural definition.

### The Palette
*   **Background (Pure Void):** `#0e0e0e` (Surface) and `#000000` (Surface-Container-Lowest). This is the foundation.
*   **Primary (The Pulse):** `#cc97ff` (Neon Purple). Use this for high-priority actions and active states. It should feel like a laser cutting through the dark.
*   **Neutral (The Slate):** Muted grays (`#ababab`) and deep navy-inflections (`#191919`) provide the structural rhythm.

### The "No-Line" Rule
While the original brief mentions 1px borders, as a Director, I am evolving this: **Sectional containment must be achieved through background shifts first.** 1px borders are reserved *only* for the innermost interactive elements. Use `surface-container-low` (`#131313`) against `surface` (`#0e0e0e`) to define large regions.

### Signature Textures & Gradients
To avoid a "flat" feel, use a subtle **linear gradient** for primary CTAs: `primary_dim` (`#9c48ea`) to `primary` (`#cc97ff`). This adds a microscopic sense of volume that flat hex codes lack.

---

## 3. Typography: The Editorial Tech Scale
The typography is a dialogue between the technical geometry of **Space Grotesk** and the hyper-legibility of **Inter**.

*   **Display (The Statement):** `display-lg` (3.5rem, Space Grotesk). Use for hero numbers or impactful headers. Tighten letter-spacing to -0.04em.
*   **Headlines (The Anchor):** `headline-md` (1.75rem, Space Grotesk). These should feel like technical labels on a blueprint.
*   **Body (The Intelligence):** `body-md` (0.875rem, Inter). Set in `on-surface-variant` (`#ababab`) for secondary info, and `on-surface` (`#ffffff`) for primary reading.
*   **Labels (The Data):** `label-sm` (0.6875rem, Space Grotesk). Use All-Caps for a military-spec, futuristic feel.

---

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are forbidden. In a pure black environment, shadows are invisible. We achieve depth through **Luminance Stacking**.

*   **The Layering Principle:** 
    *   **Level 0 (Base):** `surface` (`#0e0e0e`)
    *   **Level 1 (Sections):** `surface-container-low` (`#131313`)
    *   **Level 2 (Cards):** `surface-container` (`#191919`)
    *   **Level 3 (Popovers/Modals):** `surface-container-highest` (`#262626`)
*   **The "Ghost Border":** For internal containers, use `outline-variant` (`#484848`) at **20% opacity**. This creates a "razor edge" that catches the light without cluttering the layout.
*   **Glassmorphism:** For floating navigation or sidebars, use `surface-container` with a `20px` backdrop-blur. This allows the neon accents to "glow" through the interface as the user scrolls.

---

## 5. Components: Precision Primitives
All components follow a **0px Border Radius** (Sharp) rule. No exceptions.

*   **Buttons:**
    *   **Primary:** Solid `primary` (`#cc97ff`) with `on_primary` text. No border.
    *   **Secondary:** `surface-container-highest` background with a `primary` 1px ghost border.
*   **Inputs:** 
    *   Background: `surface-container-lowest` (`#000000`).
    *   Border: 1px `outline-variant`. On focus: 1px `primary`.
    *   Label: `label-md` in All-Caps, positioned above the field.
*   **Cards:** 
    *   Forbid divider lines. Separate content using `32px` or `48px` vertical spacing.
    *   Use `surface-container-low` as the card base to create a subtle lift from the `0e0e0e` background.
*   **Chips:** 
    *   Rectangular, sharp edges. Use `secondary-container` with `on-secondary-container` text for a muted, technical look.
*   **Data Visualization:** 
    *   Use the `primary` neon purple for the main data line. Use `error` (`#ff6e84`) sparingly for critical alerts.

---

## 6. Do’s and Don’ts

### Do:
*   **Embrace Asymmetry:** Align text to the far left and data points to the far right with significant negative space between them.
*   **Use Mono-spacing:** Utilize Space Grotesk for any numerical data to reinforce the "instrument" feel.
*   **Contrast is King:** Ensure `on-surface` text is always `#ffffff` when placed on pure black for maximum "OLED" impact.

### Don’t:
*   **No Rounded Corners:** Do not use even a 2px radius. Every corner must be a 90-degree angle to maintain the "High-End Tech" soul.
*   **No Standard Grids:** Avoid simple 3-column layouts. Use wide margins (e.g., 120px) and let elements "float" in the void.
*   **No Heavy Borders:** Never use an opaque gray border. It breaks the illusion of the "infinite black" screen. Use background shifts instead.
*   **No Soft Shadows:** Avoid traditional "Drop Shadows." If an element needs to float, use a subtle `primary` outer glow (blur 15px, 10% opacity) to simulate light emission.

---

**Director’s Final Note:** This system succeeds when it feels "expensive." If it looks like a standard dashboard, you haven't used enough black. When in doubt, remove a line and add more space.```