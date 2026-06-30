# REEFIKI Website Landing

This folder contains a static product landing page for REEFIKI.

Open locally from the repository root:

```powershell
python -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173/site/
```

## Research Notes

Open-source project websites that work well usually do five things quickly:

- state the product promise in the first viewport;
- keep install, docs and GitHub CTAs visible;
- show product proof instead of abstract marketing;
- continue the README story, so GitHub visitors do not see a disconnected brand site;
- use trust signals such as license, local install, GitHub links, docs and clear boundaries.

References reviewed:

- GitHub Docs: About READMEs - https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
- Open Source Guides: Starting an Open Source Project - https://opensource.guide/starting-a-project/
- Vite homepage - https://vite.dev/
- Astro homepage - https://astro.build/
- Docusaurus homepage - https://docusaurus.io/
- Playwright homepage - https://playwright.dev/

## Direction Chosen For REEFIKI

Best fit:

- mascot-led product explanation;
- animated distillation flow: chat noise -> filter -> markdown memory cards;
- install/docs/GitHub CTAs above the fold;
- local-first and private/public boundary as product trust;
- token economy as rough ranges, not benchmark claims;
- compact markdown-card visual language for decisions, skills, concepts, synthesis and sources.

Rejected:

- generic AI SaaS purple/blue gradient hero;
- stock dashboard mockups;
- cloud memory claims;
- oversized feature-card grids that do not show the distillation mechanism;
- hosted marketplace or managed sync claims before those surfaces exist.

## Design Skill Pass

Post-implementation polish used:

- `impeccable` brand/polish references: removed side-stripe card accents, tightened focus states, checked copy against no-em-dash site copy and kept the hero as a deliberate brand surface rather than a generic card stack.
- `ui-ux-pro-max`: confirmed product-demo landing structure, early CTA, visible focus indicators, reduced-motion support, no horizontal scroll and responsive checks.
- `magic` / 21st.dev inspiration: reviewed product-demo hero patterns; kept the useful idea of a proof-led hero with staggered reveal, but did not import React/Tailwind snippets because this site is intentionally static HTML/CSS/JS.

## Assets Used

- `../assets/reefiki-hero-mascot.png`
- `../assets/reefiki-mascot.png`
- `../assets/reefiki-token-economy.png`
- `../assets/reefiki-graph-preview.svg`

The page references root assets instead of duplicating PNGs inside `site/`.

## Missing Image Prompts

Use these prompts if a dedicated image-generation pass is approved:

1. Rifiki holding compact markdown cards
   - "Polished mascot illustration of Rifiki, a small warm reef crab archivist, holding five compact markdown memory cards labelled decisions, skills, concepts, synthesis and sources. Warm parchment background, deep reef green and coral accents, refined open-source product website style, crisp edges, no generic AI gradient, no text outside the card labels."

2. Rifiki feeding noisy chat bubbles into a distillation gate
   - "Rifiki the reef crab archivist guiding messy translucent chat bubbles into a small mechanical distillation gate, which outputs clean markdown cards. Warm technical craft, off-white parchment, muted teal, moss green, coral orange, graphite linework, product explainer composition, no stock SaaS dashboard."

3. Rifiki handing a bundle to the next AI agent
   - "Rifiki handing a tied bundle of markdown memory cards to a simple abstract AI agent silhouette at a project boundary. The mood is calm, local-first and trustworthy. Warm parchment, deep reef green, amber highlights, subtle git/history motifs, no cloud server imagery."

4. Rifiki near a bounded project graph
   - "Rifiki sitting beside a bounded project knowledge graph with a few pulsing nodes and markdown labels, showing project isolation and reusable memory. Refined minimal illustration, warm off-white background, muted teal and coral accents, no neon sci-fi, no purple gradient."

5. Spot icons for memory types
   - "Small cohesive spot icon set for REEFIKI memory types: decision, skill, source, concept, synthesis, handoff. Markdown-file inspired shapes, reef-green line art, coral and amber accents, warm parchment fill, clear at 64px, no text."

## Publish Boundary

No deployment or push is included in this slice. The site is public-safe as a product page because it references root docs and public assets only, not private `projects/*` wiki content.
