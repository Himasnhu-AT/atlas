// Moved into @atlas/ui so the desktop app can use the same entrance.
//
// The CSS behind it (`[data-reveal]`, `[data-shown]`, `[data-rule]`) has always
// lived in `packages/ui/src/styles.css`, which both apps import; only the
// component was stranded here. Re-exported rather than rewritten at eleven call
// sites, and `@/components/reveal` stays a valid import.
export { Reveal } from '@atlas/ui'
