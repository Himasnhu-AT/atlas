import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { layoutCourse, type MapModule } from './map'

/** The AI course's real prerequisite graph, which is what this exists to draw. */
const AI_COURSE: MapModule[] = [
  { id: 'ai-foundations', slug: 'foundations', name: 'Foundations', order: 0, prerequisites: [] },
  { id: 'ai-llm-fundamentals', slug: 'llm', name: 'LLM fundamentals', order: 1, prerequisites: ['ai-foundations'] },
  { id: 'ai-prompt-engineering', slug: 'prompt', name: 'Prompt engineering', order: 2, prerequisites: ['ai-llm-fundamentals'] },
  { id: 'ai-tool-use', slug: 'tools', name: 'Tool use', order: 3, prerequisites: ['ai-prompt-engineering'] },
  { id: 'ai-agent-frameworks', slug: 'frameworks', name: 'Agent frameworks', order: 4, prerequisites: ['ai-tool-use'] },
  { id: 'ai-memory-and-rag', slug: 'rag', name: 'Memory and RAG', order: 5, prerequisites: ['ai-agent-frameworks'] },
  { id: 'ai-multi-agent-and-production', slug: 'multi', name: 'Multi-agent', order: 6, prerequisites: ['ai-memory-and-rag'] },
  { id: 'ai-state-graphs', slug: 'graphs', name: 'State graphs', order: 7, prerequisites: ['ai-agent-frameworks'] },
  { id: 'ai-handoffs-and-typed-output', slug: 'handoffs', name: 'Handoffs', order: 8, prerequisites: ['ai-state-graphs'] },
  { id: 'ai-support-triage', slug: 'triage', name: 'Support triage', order: 9, prerequisites: ['ai-multi-agent-and-production'] },
  { id: 'ai-research-briefing', slug: 'briefing', name: 'Research briefing', order: 10, prerequisites: ['ai-support-triage'] },
]

const nodeOf = (map: ReturnType<typeof layoutCourse>, id: string) =>
  map.nodes.find((n) => n.id === id)!

describe('layoutCourse on the real AI course', () => {
  const map = layoutCourse(AI_COURSE)

  it('places every module below everything it needs', () => {
    for (const edge of map.edges) {
      assert.ok(
        nodeOf(map, edge.to).row > nodeOf(map, edge.from).row,
        `${edge.to} must sit below ${edge.from}`,
      )
    }
  })

  it('keeps the opening chain straight', () => {
    const spine = ['ai-foundations', 'ai-llm-fundamentals', 'ai-prompt-engineering', 'ai-tool-use', 'ai-agent-frameworks']
    for (const id of spine) assert.equal(nodeOf(map, id).col, 0, id)
    spine.forEach((id, i) => assert.equal(nodeOf(map, id).row, i, id))
  })

  it('forks at agent frameworks, which is the shape the list hides', () => {
    const rag = nodeOf(map, 'ai-memory-and-rag')
    const graphs = nodeOf(map, 'ai-state-graphs')
    assert.equal(rag.row, graphs.row, 'both branches start at the same depth')
    assert.notEqual(rag.col, graphs.col, 'and in different columns')
  })

  it('never overlaps two modules in one place', () => {
    const seen = new Set<string>()
    for (const node of map.nodes) {
      const cell = `${node.row}:${node.col}`
      assert.ok(!seen.has(cell), `${node.id} collides at ${cell}`)
      seen.add(cell)
    }
  })

  it('knows the framework branch is terminal and the projects are not on it', () => {
    // The whole reason the map earns its place. Nothing in the course requires
    // the framework rebuilds, and the projects gate on multi-agent alone.
    assert.equal(nodeOf(map, 'ai-handoffs-and-typed-output').terminal, true)
    assert.equal(nodeOf(map, 'ai-research-briefing').terminal, true)
    assert.equal(nodeOf(map, 'ai-state-graphs').terminal, false, 'handoffs needs it')
    assert.equal(nodeOf(map, 'ai-agent-frameworks').terminal, false)
    assert.deepEqual(nodeOf(map, 'ai-support-triage').prerequisites, [
      'ai-multi-agent-and-production',
    ])
  })

  it('does not call the final project optional just because nothing follows it', () => {
    // Terminal and optional are different things. Nothing depends on the last
    // project either, and labelling it "optional" tells a learner the
    // destination is a detour.
    const briefing = nodeOf(map, 'ai-research-briefing')
    assert.equal(briefing.terminal, true, 'nothing depends on it')
    assert.equal(briefing.onMainLine, true, 'but it is where the course goes')
    assert.equal(briefing.sideRoad, false)
  })

  it('calls the framework branch a side road, because that is what it is', () => {
    assert.equal(nodeOf(map, 'ai-handoffs-and-typed-output').sideRoad, true)
    assert.equal(nodeOf(map, 'ai-state-graphs').onMainLine, false)
    assert.equal(nodeOf(map, 'ai-state-graphs').sideRoad, false, 'handoffs still needs it')
  })

  it('puts the whole spine on the main line', () => {
    for (const id of [
      'ai-foundations', 'ai-llm-fundamentals', 'ai-prompt-engineering', 'ai-tool-use',
      'ai-agent-frameworks', 'ai-memory-and-rag', 'ai-multi-agent-and-production',
      'ai-support-triage', 'ai-research-briefing',
    ]) {
      assert.equal(nodeOf(map, id).onMainLine, true, id)
    }
  })

  it('reports its own extent', () => {
    assert.equal(map.rows, 9)
    assert.equal(map.cols, 2)
    assert.equal(map.nodes.length, AI_COURSE.length)
    assert.equal(map.edges.length, 10)
  })
})

describe('layoutCourse edge cases', () => {
  it('handles a course with one module', () => {
    const map = layoutCourse([{ id: 'a', slug: 'a', name: 'A', order: 0, prerequisites: [] }])
    assert.equal(map.rows, 1)
    assert.equal(map.cols, 1)
    assert.equal(map.nodes[0]!.terminal, true)
    // A one-module course is entirely the main line, so nothing is a side road.
    assert.equal(map.nodes[0]!.sideRoad, false)
  })

  it('handles an empty course without throwing', () => {
    const map = layoutCourse([])
    assert.deepEqual(map.nodes, [])
    assert.deepEqual(map.edges, [])
  })

  it('places several roots side by side', () => {
    const map = layoutCourse([
      { id: 'a', slug: 'a', name: 'A', order: 0, prerequisites: [] },
      { id: 'b', slug: 'b', name: 'B', order: 1, prerequisites: [] },
    ])
    assert.equal(nodeOf(map, 'a').row, 0)
    assert.equal(nodeOf(map, 'b').row, 0)
    assert.notEqual(nodeOf(map, 'a').col, nodeOf(map, 'b').col)
  })

  it('drops an edge to a module that is not in the course', () => {
    const map = layoutCourse([
      { id: 'a', slug: 'a', name: 'A', order: 0, prerequisites: ['not-here'] },
    ])
    assert.deepEqual(map.edges, [])
  })

  it('puts a module below its deepest prerequisite, not its first', () => {
    // Drawn below the shallower one, its edge would run upward.
    const map = layoutCourse([
      { id: 'a', slug: 'a', name: 'A', order: 0, prerequisites: [] },
      { id: 'b', slug: 'b', name: 'B', order: 1, prerequisites: ['a'] },
      { id: 'c', slug: 'c', name: 'C', order: 2, prerequisites: ['a', 'b'] },
    ])
    assert.equal(nodeOf(map, 'c').row, 2)
  })

  it('does not hang on a cycle a bad manifest might contain', () => {
    const map = layoutCourse([
      { id: 'a', slug: 'a', name: 'A', order: 0, prerequisites: ['b'] },
      { id: 'b', slug: 'b', name: 'B', order: 1, prerequisites: ['a'] },
    ])
    assert.equal(map.nodes.length, 2)
  })
})
