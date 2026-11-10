---
name: Adal
description: A calm auction house where every bid weighs the same and one clock decides the result.
colors:
  paper: "#F4F6F3"
  card: "#FFFFFF"
  rule: "#D5DBD5"
  control-edge: "#98A39B"
  ink: "#0F1512"
  body-text: "#27302B"
  muted: "#505B54"
  moss: "#40705A"
  moss-tint: "#E6F0EA"
  moss-deep: "#2F5545"
  brass: "#85601C"
  brass-tint: "#F1EAD8"
  brass-on-dark: "#F0CF84"
  on-dark-soft: "#E3ECE6"
typography:
  display:
    fontFamily: "Bricolage Grotesque, system-ui, sans-serif"
    fontSize: "92px"
    fontWeight: 300
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Bricolage Grotesque, system-ui, sans-serif"
    fontSize: "52px"
    fontWeight: 300
    lineHeight: 1.1
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Bricolage Grotesque, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 400
    lineHeight: 1.2
  body:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.4
  figure:
    fontFamily: "Instrument Sans, system-ui, sans-serif"
    fontSize: "80px"
    fontWeight: 500
    lineHeight: 1.1
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
rounded:
  control: "10px"
  image: "16px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "48px"
components:
  button-primary:
    backgroundColor: "{colors.moss}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "52px"
    padding: "0 28px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "48px"
    padding: "0 20px"
  preset:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "48px"
  preset-selected:
    backgroundColor: "{colors.moss-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "48px"
  field:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "48px"
    padding: "0 14px"
  desk:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.image}"
    padding: "22px 24px"
  status-live:
    backgroundColor: "{colors.moss-tint}"
    textColor: "{colors.moss}"
    rounded: "{rounded.pill}"
    padding: "7px 14px"
  status-outbid:
    backgroundColor: "{colors.brass-tint}"
    textColor: "{colors.brass}"
    rounded: "{rounded.pill}"
    padding: "7px 14px"
---

# Design System: Adal

## Overview

**Creative North Star: "The Level Beam"**

Adal means fair and honest, and the system makes fairness visible as balance. The mark is two identical weights on a level beam, balanced on a fulcrum with a single brass point where it rests. The rest of the system behaves the same way: calm stone ground, quiet type, one primary action, and a bidding desk that gives every bidder the same facts in the same place.

The mood is a quiet viewing room, not a sales floor. Photography of real objects is the main material, shown large and unframed, with soft grain and low light. Headlines are light grotesque with one brass word; numbers are clean and tabular so they can be read and compared. Motion is slow and eased, and happens once.

Confirmed rejections: loud colors, the earlier arch and clock marks, hard black rules, hype wording, decorative gold, and the earlier warm beige and terracotta palette.

**Key Characteristics:**
- Cool paper ground, sage moss for action, brass used sparingly for what needs attention.
- Real photographs lead; dark moss fields frame the cover, hero and winning moment.
- Bricolage Grotesque Light for headlines with one brass word; Instrument Sans for everything read; Outfit Medium for the wordmark; tabular figures for every number.
- Soft 10px and 16px corners, 1px rules, one faint layered shadow on the bidding desk only.
- Every status is a word plus an icon.

## Colors

A cool, muted palette. Almost everything is paper and ink; moss carries action; brass marks the few things that need attention.

### Primary
- **Sage Moss** (#40705A): primary buttons, links, the selected preset outline, and the dark photographic fields (moss-deep #2F5545 as their edge, lifted to #3F6E59 at the centre of the gradient).

### Secondary
- **Brass** (#85601C): Outbid, Ending soon, and the balance point in the mark. On dark fields the mark's point is a lighter brass (#F0CF84, 5.6:1 on moss-deep). Brass text on paper is 5.2:1.

### Neutral
- **Paper** (#F4F6F3): the page ground. **Card** (#FFFFFF): desks, fields. **Rule** (#D5DBD5): dividers only. **Control Edge** (#98A39B): borders of fields and presets.
- **Ink** (#0F1512): headings and figures. **Body Text** (#27302B) and **Muted** (#505B54, 6.5:1 on paper): reading and secondary text.
- **Moss Tint** (#E6F0EA) and **Brass Tint** (#F1EAD8): status and selected-preset fills.

### Named Rules
**The One Brass Rule.** Brass is for the balance point, Outbid and Ending soon. It is never a button, a decoration or a large field.

**The Words Beat Color Rule.** Status is a word plus an icon; color is never the only signal.

## Typography

**Display Font:** Bricolage Grotesque (with system-ui)
**Body Font:** Instrument Sans (with system-ui)
**Wordmark Font:** Outfit Medium, for the name "Adal" only. **Figures:** Instrument Sans with tabular figures

**Character:** A light, tight grotesque for the big statements and a clear text face for every task. One word in a headline takes the brass colour; there is no italic. The wordmark is set in a round geometric face so its letters echo the circles of the mark.

### Hierarchy
- **Display** (300, up to 92px, 1.05, -0.02em): cover and hero, with one brass word.
- **Headline** (300, 52px, 1.1): section titles.
- **Title** (400, 24px): format names, trust-strip heads.
- **Body** (400, 17px, 1.6): descriptions, up to about 65ch.
- **Label** (600, 14px): status, captions, buttons.
- **Figure** (500, up to 80px, tabular): the current price, timers, bid history.

### Named Rules
**The Tabular Rule.** Every number uses tabular figures so a ticking value never shifts its neighbors.

## Layout

Web content sits in a 1200px container with 48px side padding. The home page opens with a full-bleed photographic field, then a three-promise strip, then a gallery that pairs one large portrait lot with two smaller ones, then the formats as ruled rows. The auction page places photography on the left and the bidding desk on the right; on phones the desk follows the photo. Spacing steps are 8, 12, 16 and 48px, with generous separation between sections and tight grouping inside them. Targets are at least 44px.

## Elevation & Depth

Mostly flat, with tonal layering. The bidding desk alone carries a faint two-layer shadow (a 1px contact shadow and a soft 32px ambient one) so it reads as the one object to act on. Nothing else floats.

### Named Rules
**The One Raised Object Rule.** Only the bidding desk is lifted. Everything else sits on the page.

## Shapes

Soft and level. Controls are 10px, images and the desk 16px, status chips are pills. The beam in the mark is always horizontal; the only tilt in the system is the one-time settle animation when the mark first appears.

## Components

### Buttons
- **Primary:** moss fill, paper text, 10px radius, 52px tall; it repeats the amount ("Place bid · 245.00"). One per view.
- **Secondary:** transparent with a 1px ink border. On dark fields, a paper fill for the primary and a translucent paper outline for the secondary.
- **Hover / Active / Focus:** hover brightens slightly over 300ms; press eases to 0.97 over 250ms; focus is a 2px moss outline with 2px offset. Reduced motion removes movement.

### Bid presets
- **Style:** three equal buttons, card fill, 1px control-edge border, 10px radius.
- **State:** the selected preset has a 1.5px moss border and moss tint. The first (current plus 5) is preselected.

### Inputs / Fields
- **Style:** 48px, card fill, 1px control-edge border, 10px radius, visible label above, tabular figures.
- **Error:** a brass message with the next step and an icon, never color alone.

### Status
- **Live / Winning:** moss tint pill with moss text and a dot or check. **Outbid:** brass tint pill with a down arrow. **Ending soon:** brass text. **Upcoming, No sale:** plain muted text.

### Photographs
Real object photography at 16px radius, shown large; hover scales the image 1.04 over about 1.1 seconds. Grain overlays belong to the dark fields, never on photographs. Never place the mark over a photograph.

### The Bidding Desk (signature component)
A card with the faint layered shadow. Top row: "Current price" and the Live pill. The price at 80px in tabular figures. Below it, the countdown and the written closing time. Then the Winning or Outbid line, three presets, "A bid is a binding commitment to buy.", and the primary button. Dutch shows an accept-price button; sealed and Vickrey take one hidden bid.

## Do's and Don'ts

### Do:
- **Do** write the closing time out beside every countdown.
- **Do** lead with large, real photography in even, low light.
- **Do** keep one primary action per view, in moss.
- **Do** keep the beam level and the weights identical in the mark; let it settle once on first appearance.
- **Do** credit photographs that need it (demo images are The Metropolitan Museum of Art, CC0).

### Don't:
- **Don't** add gold, bright accents, gradients on text, or hard shadows.
- **Don't** use brass for buttons or large areas.
- **Don't** tilt the beam, make the weights differ, or recolor the balance point.
- **Don't** use exclamation marks, emoji or hype wording.
- **Don't** put a second raised object on the page.

## Open decisions

Currency symbol; minimum increment; sniping extension length; whether a sealed bid can be revised before close. Demo photographs are museum public-domain images and must be replaced with sellers' own listing photos.

Brandbook (7 boards, private): https://claude.ai/artifact/DdaGY8GP3Qj1Bvi1aNEJrX
