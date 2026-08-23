/**
 * The game's marks, exported on their own subpath.
 *
 * Deliberately not re-exported from the package barrel. That barrel reaches
 * `LessonSidebar` and the other components that use hooks, so importing it from
 * a React Server Component drags `useState` in behind these and the page fails
 * to render. These are pure SVG with no state, and the whole point of them is
 * that a server component can use them.
 */

export * from './level-up'
export * from './marks'
