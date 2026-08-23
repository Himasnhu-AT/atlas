# Design

The visual system for Atlas. It exists so a page nobody has built yet already looks
like it belongs.

**The one rule: this is a workbook, not a dashboard.** Paper, ink, hairline rules where a
book would put rules, and a great deal of empty space. A student spends hours reading
these pages, so the page behaves like something printed and the interface stays out of
the way. If a change makes a screen feel more like an admin panel, it is wrong even when
it looks good in isolation.

There is one theme. Paper is the product.

## Tokens

Everything lives in the `@theme` block in `packages/ui/src/styles.css`. Use the Tailwind
utilities it generates. Never write a hex value into a component.

### Colour

| Token | Value | Utility | Use |
|---|---|---|---|
| `--color-paper` | `#f7f4ee` | `bg-paper` | The page. Warm, because pure white glares under the lamp someone reads a chapter under at 11pm. |
| `--color-paper-raised` | `#fffdf9` | `bg-paper-raised` | Hover on a ruled row, and the popover. |
| `--color-paper-sunken` | `#efeae1` | `bg-paper-sunken` | Inline code, and the pressed state. |
| `--color-ink` | `#1a1714` | `text-ink` | Headlines and anything read first. Warm near-black, not `#000`. |
| `--color-ink-soft` | `#4a443c` | `text-ink-soft` | Body copy. Most words in the product. |
| `--color-muted` | `#6d6558` | `text-muted` | Eyebrows, meta lines, marginal notes. |
| `--color-rule` | `#ddd6c9` | `border-rule` | Every hairline. Always 1px. |
| `--color-rule-strong` | `#c4bbaa` | `border-rule-strong` | A rule that has to be seen: an input underline, a blockquote. |
| `--color-accent` | `#2d4a72` | `text-accent` | Fountain-pen blue-black. Display sizes. |
| `--color-accent-deep` | `#24395a` | `text-accent-deep` | The same hue for links and anything under 24px. |
| `--color-pass` | `#2f6b46` | `text-pass` | A passing test. |
| `--color-fail` | `#9c3328` | `text-fail` | A failing test, and form errors. |
| `--color-warn` | `#8a6218` | `text-warn` | A setup problem the student can fix. |

**The accent rule: one idea per screen wears it.** On a page that means the italic word in
the headline, plus the small structural marks that repeat (the rule under the hero, the
progress hairline). Accent on a whole paragraph, or on two competing headlines, spends
the only emphasis the palette has.

**Verdict colours are never decoration.** `pass`, `fail` and `warn` report whether a test
passed or whether the toolchain is ready. That is why there is no scale for them: one
green, one red, one amber, used for one purpose each.

### Type

Three families, self-hosted through `@fontsource-variable` so nothing is fetched from a
font CDN and the desktop app renders identically with no network.

- **Literata** (`font-serif`) for headings, leads, and pull quotes. It is a reading face,
  drawn for long-form screen text. Italic carries emphasis.
- **Inter** (`font-sans`) for body copy, navigation, labels, and buttons.
- **JetBrains Mono** (`font-mono`) for code, and for numerals that are genuinely
  measurements. Never as a costume for "technical".

Seven sizes, and every piece of text is one of them:

| Utility | Size | Where |
|---|---|---|
| `text-eyebrow` | 11px, `0.16em`, uppercase | The label above a headline. |
| `text-display` | `clamp(38px, 6.4vw, 68px)` | The home headline. One per site. |
| `text-title` | `clamp(30px, 4.2vw, 44px)` | The `h1` of an inner page. One per page. |
| `text-lead` | `clamp(17px, 1.7vw, 20px)` | The serif paragraph under an `h1`. |
| `text-section` | 21px | A row title, meaning `h2`. |
| `text-quote` | `clamp(19px, 2.2vw, 25px)` | The closing italic line. |
| `text-caption` | 13px | Meta, nav, buttons, form labels. |

Measure is capped at `62ch` for body and `56ch` for leads and quotes. Lesson prose is
capped at `--container-reading` (`68ch`). A 1080px column of unbroken prose is unreadable,
and the caps are what make the layout feel typeset rather than filled.

### Space

The column is `max-w-page` (1120px) with `px-6` gutters, `px-8` from `sm`. `Wrap` is the
only thing that applies it. Inner pages open at `pt-20`, `pt-24` from `sm`. Ruled rows are
`py-8`, `py-9` from `sm`. A closing pull quote sits `mt-20` under the last rule.

Prefer these numbers over inventing new ones. The rhythm is worth more than any individual
measurement being perfect.

## Components

All in `apps/web/components/layout.tsx`, all server components apart from `Reveal`.

```tsx
<main id="main" className="pt-20 pb-28 sm:pt-24">
  <Wrap>
    <PageHeader
      eyebrow="What you will build"
      title={<>The <em className="italic text-accent">curriculum</em></>}
      lead="One serif paragraph. Two sentences, three at the outside."
    />

    <RuledList>
      <RuledRow aside="03" title="A row title" meta="4 lessons · 8h" href="/learn/x">
        The body of the row. Plain sentences.
      </RuledRow>
    </RuledList>

    <PullQuote>&ldquo;The line worth remembering.&rdquo;</PullQuote>
  </Wrap>
</main>
```

- **`Wrap`** is the column. Nothing sits outside it.
- **`Eyebrow`** is the caps label that opens a page or a late section.
- **`PageHeader`** is the label, the `h1`, and the lead, with reveal delays already set.
  Pass `title` as JSX so one word can carry the accent.
- **`RuledList` / `RuledRow`** is the only list style: a narrow left column for a numeral
  or status, the substance on the right. Collapses to one column below `sm`.
- **`PullQuote`** closes a page. At most one, and only when the line earns it.
- **`Rule`** is a standalone hairline that draws itself in from the left.
- **`Reveal`** wraps anything that should arrive when scrolled to.

**There are no cards.** A card is the lazy container, and a grid of same-size cards is the
fastest way to make a considered product look generated. Where a card is tempting, the
answer is a `RuledRow`. If you need a shadow, a gradient, or a corner radius above 6px,
the answer is almost certainly a `RuledRow` too.

## The game's marks

The game adds four shapes, in `packages/ui/src/game/marks.tsx`. All four are
inline SVG using `currentColor` and sized in `em`, so they take the ink colour of
whatever they sit beside and scale with it. There are no image files and no icon
font, because an asset that cannot take the ink colour would be the one thing on
the page not made of ink.

- **`RankStamp`** is a rank pressed into the page: two rings slightly out of true
  with each other and a roman numeral. The unevenness is fixed rather than
  random, so a rank is the same shape every time a reader sees it.
- **`WaxSeal`** marks an achievement. Filled when earned, an outline when not,
  and the outline is drawn at a legible weight rather than faded almost out:
  a seal a learner can see is a goal, one they cannot is a surprise.
- **`RuleMeter`** is the progress bar, and is deliberately not a bar. The page is
  already made of rules, so progress is one of them drawn partway. Never a ring,
  never a pill.
- **`WeekDots`** is the week as seven marks, filled for a day worked. Days past
  the target are still drawn, because the target is a floor the learner set and
  not a ceiling the product imposed.

They are exported from `@atlas/ui/game`, not from the package barrel. The barrel
reaches `LessonSidebar` and the other components that use hooks, so importing it
from a server component drags `useState` in behind these and the page fails to
render.

**The game does not get its own visual language.** No neon, no pixel art, no
progress rings, no confetti, no badges with drop shadows. Rank is a stamp, an
achievement is a seal, progress is a rule drawn partway, and a level-up is the
page ruling a line. If a proposed game element cannot be described as something
that happens to paper or ink, it does not belong, and that rule does not relax
because the screen is a scoreboard.

## Motion

**The gesture is ruling a line on paper.** A rule is never faded in; it is drawn, from the
left, as its content arrives. Everything else is a quiet arrival underneath that one idea.
If a proposed animation cannot be described as something that happens to paper or ink, it
does not belong.

One curve, `--ease-paper` (`cubic-bezier(0.16, 1, 0.3, 1)`). It decelerates hard, so
motion reads as a confident arrival rather than a slide. No bounce, no elastic, ever.

Three behaviours, and no fourth without amending this section:

**Arrival** (`Reveal`, default). Opacity 0 to 1 and 12px up, 0.65s.

**Settle** (`Reveal variant="settle"`). The same from 18px with `blur(4px)`, 0.85s. Ink
resolving into paper. This is the home headline and it should stay the only use: a focal
moment repeated on every page is not a focal moment.

**Rule** (`data-rule`). `scaleX(0)` to 1 from the left, 0.75s, 0.08s behind its content so
the line lands just after the words.

Reveals fire on `IntersectionObserver` (8% visible, 6% bottom margin), once. An entrance
that has already finished before the reader arrives is worse than no entrance, because the
page then just looks static to them.

**`data-reveal` on its own renders nothing.** It sets `opacity: 0` and waits for
`data-shown`, which `Reveal` adds when the observer fires. An element injected
after a click is never observed, so the attribute alone leaves it invisible: the
XP stamp on the complete button was rendered, announced to screen readers, and
never drawn. Something that appears in response to an action has to set
`data-shown` itself on the next frame.

Hover and focus are 200ms on the same curve. Nav links draw a 1px accent rule underneath,
the same gesture as the page rules, rather than only changing colour.

### Safety

The hidden pre-state lives inside `@media (scripting: enabled)`. With JavaScript off, none
of it applies and the page renders fully visible. No content can be hidden by a script
that failed to run.

**`prefers-reduced-motion` removes travel, not feedback.** The usual shortcut, a blanket
`animation-duration: 0.01ms !important` on `*`, takes hover, focus and open/close feedback
with it and leaves the interface feeling broken for exactly the people who asked for it to
be calmer. Transforms, blur and smooth scrolling go. Colour and opacity transitions stay
at 0.15s, because those communicate state without moving anything.

## Accessibility

Measured against paper (`#f7f4ee`):

| Colour | Ratio | Verdict |
|---|---|---|
| `ink` | 16.3:1 | AA and AAA at any size. |
| `ink-soft` | 8.8:1 | AA and AAA at any size. Body copy lives here. |
| `accent-deep` | 10.6:1 | AA and AAA at any size. |
| `accent` | 8.2:1 | AA and AAA at any size. |
| `fail` | 6.6:1 | AA at any size. |
| `pass` | 5.8:1 | AA at any size. |
| `muted` | 5.2:1 | AA at any size. Safe for 11px eyebrows. |
| `warn` | 5.0:1 | AA at any size. |
| `rule` | 1.3:1 | Decorative hairlines only. Never a border that carries meaning. |

If you retune the palette, re-measure. The ratio is `(L1 + 0.05) / (L2 + 0.05)` on relative
luminance, and getting it wrong is invisible to you and not to the person reading.

Standing rules:

- Focus is a 2px accent outline at 3px offset, set globally in the base layer. Never remove
  it locally.
- Every interactive control is at least 44px tall (`min-h-11`).
- A skip link is the first focusable element on every page; every page has one `<main id="main">`.
- Navigation stays visible at every width. The lesson contents become a `<details>`
  disclosure below `lg` rather than disappearing, because dropping the only structural
  navigation on a phone strands the reader at the bottom of a long article.
- One `h1` per page, `h2` for section and row titles, in order.
- Decorative arrows and rules get `aria-hidden`.
- Tailwind v4 leaves bare `border` at `currentColor`, which paints hairlines in text
  colour. The base layer defaults every border to `--color-rule`; do not rely on
  `border-<colour>` being present.

## The lesson body

`.prose-learn` styles rendered lesson HTML. It is the product's core surface, and it
outranks the marketing pages: a student is in it for forty minutes at a time.

The content build emits plain HTML, so `.prose-learn` targets real elements rather than
utility classes. Headings get more space above than below. Lists use an en dash rather
than a bullet, which is what a typesetter would set and keeps the left edge quiet. Inline
code takes a tint but no border, because a boxed span mid-sentence breaks the line's
rhythm. Code blocks are the one place the page goes darker: a listing is a plate set into
the page, and the contrast is what makes it read as a specimen rather than as more prose.

`.prose-compact` is the same at a smaller size, for the desktop app's narrower pane.

Highlighting is Shiki with `github-light`, applied at content-build time. Do not pass a
light/dark theme pair: it emits both palettes plus a `prefers-color-scheme` block on every
token, and this product has one theme.

## Adding a page

1. `apps/web/app/<name>/page.tsx`, exporting `metadata` with a title and description. The
   title template appends the product name, so pass `"Curriculum"`, not `"Curriculum · Atlas"`.
2. Open with `<main id="main" className="pt-20 pb-28 sm:pt-24">` and a `Wrap`.
3. Build the page from the components above. If it needs a shape that does not exist,
   add it to `layout.tsx` and document it here in the same commit, so the next page
   inherits it instead of reinventing it.
