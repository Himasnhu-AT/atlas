/**
 * Laying a course out as a chart.
 *
 * The prerequisite graph is a real DAG and the catalogue list has been hiding
 * its shape. In the AI course the chain runs straight until `ai-agent-frameworks`
 * and then forks: memory and multi-agent on one side, the two framework rebuilds
 * on the other, and **nothing depends on the framework branch**. The projects
 * gate on multi-agent alone. So that branch is structurally optional, and no
 * screen in the product has ever been able to say so.
 *
 * Pure, so it can be tested without rendering anything, and so both apps lay a
 * course out identically.
 */

export interface MapModule {
  id: string
  slug: string
  name: string
  order: number
  prerequisites: string[]
}

export interface MapNode extends MapModule {
  /** Depth from the start of the course. Rows run down the page. */
  row: number
  /** Which branch it sits in. Columns run across. */
  col: number
  /** Nothing in the course requires this module. */
  terminal: boolean
  /** On the chain running to the furthest point in the course. */
  onMainLine: boolean
  /**
   * A road the course does not need you to take.
   *
   * Terminal is not the same thing, and conflating them is how the last module
   * of a course ends up labelled optional: nothing depends on the final project
   * either, but it is the destination rather than a detour. A side road is
   * terminal *and* off the main line.
   */
  sideRoad: boolean
}

export interface MapEdge {
  from: string
  to: string
}

export interface CourseMap {
  nodes: MapNode[]
  edges: MapEdge[]
  rows: number
  cols: number
}

/**
 * Longest path from a root, so a module always sits below everything it needs.
 *
 * Longest rather than shortest: a module with two prerequisites at different
 * depths has to be drawn below the deeper one, or its edge runs upward.
 */
function byIdOf(modules: MapModule[]): Map<string, MapModule> {
  return new Map(modules.map((m) => [m.id, m]))
}

function depths(modules: MapModule[]): Map<string, number> {
  const byId = byIdOf(modules)
  const depth = new Map<string, number>()

  const visit = (id: string, seen: Set<string>): number => {
    const cached = depth.get(id)
    if (cached !== undefined) return cached
    // The content build rejects cycles, but a bad manifest must not hang a
    // render, so a repeat visit resolves to 0 rather than recursing forever.
    if (seen.has(id)) return 0

    const module = byId.get(id)
    if (!module || module.prerequisites.length === 0) {
      depth.set(id, 0)
      return 0
    }

    const next = new Set(seen).add(id)
    const value =
      1 + Math.max(...module.prerequisites.map((prereq) => visit(prereq, next)))
    depth.set(id, value)
    return value
  }

  for (const module of modules) visit(module.id, new Set())
  return depth
}

/**
 * Lay a course out.
 *
 * A module keeps its first prerequisite's column, so the main line stays
 * straight; a second module depending on the same prerequisite is pushed one
 * column across, which is what draws the fork.
 */
export function layoutCourse(modules: MapModule[]): CourseMap {
  const ordered = [...modules].sort((a, b) => a.order - b.order)
  const depth = depths(ordered)

  const required = new Set(ordered.flatMap((m) => m.prerequisites))
  const col = new Map<string, number>()
  // Columns already spoken for at a given row, so two branches never overlap.
  const takenByRow = new Map<number, Set<number>>()
  // Which columns each prerequisite has already handed down.
  const claimedFrom = new Map<string, number>()

  const claim = (row: number, wanted: number): number => {
    const taken = takenByRow.get(row) ?? new Set<number>()
    let candidate = wanted
    while (taken.has(candidate)) candidate += 1
    taken.add(candidate)
    takenByRow.set(row, taken)
    return candidate
  }

  for (const module of ordered) {
    const row = depth.get(module.id) ?? 0
    const parent = module.prerequisites[0]

    let wanted = 0
    if (parent !== undefined) {
      const parentCol = col.get(parent) ?? 0
      // The first child inherits the line; the next one branches beside it.
      const alreadyGiven = claimedFrom.get(parent)
      wanted = alreadyGiven === undefined ? parentCol : alreadyGiven + 1
      claimedFrom.set(parent, wanted)
    }

    col.set(module.id, claim(row, wanted))
  }

  // The main line runs to the furthest point in the course. Ties break on
  // `order`, so the line is the one the catalogue already presents as the spine.
  const deepest = ordered.reduce<MapModule | undefined>((best, module) => {
    if (!best) return module
    const a = depth.get(module.id) ?? 0
    const b = depth.get(best.id) ?? 0
    return a > b || (a === b && module.order < best.order) ? module : best
  }, undefined)

  const mainLine = new Set<string>()
  const walk = (id: string) => {
    if (mainLine.has(id)) return
    mainLine.add(id)
    for (const prereq of byIdOf(ordered).get(id)?.prerequisites ?? []) walk(prereq)
  }
  if (deepest) walk(deepest.id)

  const nodes: MapNode[] = ordered.map((module) => {
    const terminal = !required.has(module.id)
    const onMainLine = mainLine.has(module.id)
    return {
      ...module,
      row: depth.get(module.id) ?? 0,
      col: col.get(module.id) ?? 0,
      terminal,
      onMainLine,
      sideRoad: terminal && !onMainLine,
    }
  })

  // Symmetrically center diamonds (fork-and-merge topologies)
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  for (const node of nodes) {
    if (node.prerequisites.length > 1) {
      const parents = node.prerequisites
        .map((id) => nodeById.get(id))
        .filter((p): p is MapNode => p !== undefined)
      if (parents.length > 1) {
        const avgCol = parents.reduce((sum, p) => sum + p.col, 0) / parents.length
        const oldCol = node.col
        const delta = avgCol - oldCol

        node.col = avgCol

        // Center common fork ancestor above the branches
        const commonParentId = parents[0]?.prerequisites[0]
        if (
          commonParentId &&
          parents.every((p) => p.prerequisites[0] === commonParentId)
        ) {
          const rootNode = nodeById.get(commonParentId)
          if (rootNode) rootNode.col = avgCol
        }

        // Adjust downstream nodes on the same spine
        for (const child of nodes) {
          if (
            child.row > node.row &&
            child.onMainLine &&
            Math.abs(child.col - oldCol) < 0.01
          ) {
            child.col = child.col + delta
          } else if (child.row > node.row && child.sideRoad && child.col >= oldCol) {
            child.col = child.col + delta
          }
        }
      }
    }
  }

  const known = new Set(ordered.map((m) => m.id))
  const edges: MapEdge[] = ordered.flatMap((module) =>
    module.prerequisites
      .filter((prereq) => known.has(prereq))
      .map((prereq) => ({ from: prereq, to: module.id })),
  )

  return {
    nodes,
    edges,
    rows: nodes.reduce((max, n) => Math.max(max, n.row), 0) + 1,
    cols: Math.ceil(nodes.reduce((max, n) => Math.max(max, n.col), 0)) + 1,
  }
}
