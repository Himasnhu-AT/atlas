import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { browserSupportFor, topLevelImports } from './browser'

describe('topLevelImports', () => {
  it('reads both import forms', () => {
    const found = topLevelImports('import json\nfrom mockllm import text\n')
    assert.deepEqual(found.sort(), ['json', 'mockllm'])
  })

  it('takes the root of a dotted path', () => {
    assert.deepEqual(topLevelImports('from concurrent.futures import ThreadPoolExecutor'), [
      'concurrent',
    ])
  })

  it('ignores prose that happens to start with the word', () => {
    // Docstrings are indented under whatever they document, so an anchored
    // match cannot see them. This is the case that made a looser regex report
    // five imaginary third-party packages across the catalogue.
    const source = '"""\n    import a module and the rest follows\n"""\nimport json\n'
    assert.deepEqual(topLevelImports(source), ['json'])
  })
})

describe('browserSupportFor', () => {
  it('passes an ordinary stdlib exercise', () => {
    const support = browserSupportFor({
      'test.py': 'import unittest\nimport json\n',
      'scaffold.py': 'from mockllm import text\n',
    })
    assert.equal(support.runnable, true)
  })

  it('allows sqlite3, which the runtime does provide', () => {
    // The whole data engineering course rests on this being true, and it was
    // checked against the runtime rather than assumed.
    assert.equal(browserSupportFor({ 'test.py': 'import sqlite3\n' }).runnable, true)
  })

  it('refuses threads, and says why', () => {
    const support = browserSupportFor({ 'scaffold.py': 'import threading\n' })
    assert.equal(support.runnable, false)
    assert.match(support.reason ?? '', /threads/)
  })

  it('does not judge an exercise by its reference solution', () => {
    // The reference is never what runs in a browser: the student's own file is.
    const support = browserSupportFor({
      'reference.py': 'import threading\n',
      'test.py': 'import unittest\n',
    })
    assert.equal(support.runnable, true)
  })
})
