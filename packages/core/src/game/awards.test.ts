import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  type ExerciseLike,
  type ModuleLike,
  difficultyMultiplier,
  exerciseAwards,
  lessonAward,
  moduleAward,
  questAward,
  sealAward,
  weekMetAward,
  weekMilestoneAward,
} from './awards'

const beginner: ModuleLike = { id: 'ai-foundations', courseId: 'ai-agents', difficulty: 'beginner' }
const advanced: ModuleLike = { id: 'ai-support-triage', courseId: 'ai-agents', difficulty: 'advanced' }
const exercise: ExerciseLike = { id: 'react-loop', timeboxMinutes: 30 }

const unaidedFirstTry = { peeked: false, priorFailures: 0 }
const peekedAfterStruggle = { peeked: true, priorFailures: 4 }

describe('award keys', () => {
  it('do not vary with anything mutable', () => {
    // The trap this exists to catch: `lesson:<id>:<completedAt>` looks right,
    // passes every test where the learner completes once, and double-pays on
    // the third toggle, because un-completing clears `completedAt` and the next
    // complete mints a fresh timestamp.
    const first = lessonAward({ id: 'ai-tool-use.the-react-loop', estimatedMinutes: 60 }, beginner)
    const second = lessonAward({ id: 'ai-tool-use.the-react-loop', estimatedMinutes: 60 }, beginner)
    assert.equal(first.awardKey, second.awardKey)
    assert.match(first.awardKey, /^lesson:ai-tool-use\.the-react-loop$/)
    assert.ok(!/\d{4}-\d{2}-\d{2}T/.test(first.awardKey), 'no timestamp in the key')
  })

  it('is the same for a re-run of a passing exercise', () => {
    const first = exerciseAwards(exercise, beginner, unaidedFirstTry)
    const again = exerciseAwards(exercise, beginner, { peeked: false, priorFailures: 0 })
    assert.deepEqual(
      first.map((a) => a.awardKey),
      again.map((a) => a.awardKey),
    )
  })

  it('qualifies an exercise by course and module', () => {
    // Exercise ids are unique across the catalogue by rule now, but the key says
    // so without needing the rule to hold.
    const [pass] = exerciseAwards(exercise, beginner, unaidedFirstTry)
    assert.equal(pass!.awardKey, 'exercise:pass:ai-agents/ai-foundations/react-loop')
  })

  it('gives each bonus its own key so each pays once on its own terms', () => {
    const keys = exerciseAwards(exercise, beginner, unaidedFirstTry).map((a) => a.awardKey)
    assert.equal(new Set(keys).size, keys.length, 'keys are distinct')
    assert.equal(keys.length, 3)
  })

  it('keys a quest by the server day, never a client one', () => {
    assert.equal(questAward('pass-two', '2026-08-23', false).awardKey, 'quest:pass-two:2026-08-23')
  })
})

describe('what things are worth', () => {
  it('pays a lesson a flat, small amount regardless of length', () => {
    // Paying by length put a third of the economy behind a self-reported button
    // that verifies nothing, and made a sixty-minute lesson worth sixty XP to
    // anyone willing to click through it.
    assert.equal(lessonAward({ id: 'x.y', estimatedMinutes: 12 }, beginner).points, 5)
    assert.equal(lessonAward({ id: 'x.y', estimatedMinutes: 60 }, beginner).points, 5)
  })

  it('keeps reading worth far less than demonstrated work', () => {
    const reading = lessonAward({ id: 'x.y', estimatedMinutes: 60 }, beginner).points
    const doing = exerciseAwards(exercise, beginner, unaidedFirstTry).reduce((n, a) => n + a.points, 0)
    assert.ok(doing > reading * 10, `${doing} vs ${reading}`)
  })

  it('scales an exercise by timebox and difficulty', () => {
    assert.equal(exerciseAwards(exercise, beginner, peekedAfterStruggle)[0]!.points, 60)
    assert.equal(exerciseAwards(exercise, advanced, peekedAfterStruggle)[0]!.points, 90)
  })

  it('pays the bonuses only when they are earned', () => {
    const earned = exerciseAwards(exercise, beginner, unaidedFirstTry)
    assert.deepEqual(earned.map((a) => a.points), [60, 15, 9])

    const neither = exerciseAwards(exercise, beginner, peekedAfterStruggle)
    assert.equal(neither.length, 1, 'a peeked, hard-won pass earns the base only')
  })

  it('pays a repeated struggle no more than a single clean pass', () => {
    // Nothing pays per run, so grinding the button cannot out-earn getting it
    // right. The hard-won pass is worth strictly less than the clean one, and
    // the difference is the two bonuses rather than a count of attempts.
    const clean = exerciseAwards(exercise, beginner, unaidedFirstTry)
    const ground = exerciseAwards(exercise, beginner, { peeked: false, priorFailures: 40 })
    const total = (list: { points: number }[]) => list.reduce((n, a) => n + a.points, 0)
    assert.ok(total(ground) < total(clean))
    assert.equal(total(ground), 75)
  })

  it('scales a module by difficulty', () => {
    assert.equal(moduleAward(beginner).points, 100)
    assert.equal(moduleAward(advanced).points, 150)
  })

  it('treats an unknown difficulty as the cheapest rather than throwing', () => {
    assert.equal(difficultyMultiplier('unheard-of'), 1)
    assert.equal(moduleAward({ ...beginner, difficulty: 'unheard-of' }).points, 100)
  })
})

describe('the weekly target', () => {
  it('pays once for a week that met its target, keyed by that week', () => {
    assert.equal(weekMetAward('2026-08-17').awardKey, 'week:2026-08-17')
    assert.equal(weekMetAward('2026-08-17').points, 60)
    // Keyed by the week worked rather than by a running count, so nothing is
    // lost by missing the next one.
    assert.notEqual(weekMetAward('2026-08-17').awardKey, weekMetAward('2026-08-24').awardKey)
  })

  it('marks a run of weeks only at sparse milestones', () => {
    assert.equal(weekMilestoneAward(1), null)
    assert.equal(weekMilestoneAward(3), null)
    assert.equal(weekMilestoneAward(5), null)
    assert.equal(weekMilestoneAward(4)?.points, 50)
    assert.equal(weekMilestoneAward(12)?.points, 100)
    assert.equal(weekMilestoneAward(52)?.points, 200)
  })

  it('keys a milestone by the run so it cannot be re-earned', () => {
    assert.equal(weekMilestoneAward(4)?.awardKey, 'weeks:4')
  })
})

describe('carrying the course', () => {
  it('tags awards with the course that produced them', () => {
    assert.equal(lessonAward({ id: 'x.y', estimatedMinutes: 10 }, beginner).courseId, 'ai-agents')
    assert.equal(exerciseAwards(exercise, advanced, unaidedFirstTry)[0]!.courseId, 'ai-agents')
    assert.equal(sealAward('first-light', 25, 'ai-agents').courseId, 'ai-agents')
  })

  it('leaves a global award without a course', () => {
    assert.equal(weekMetAward('2026-08-17').courseId, undefined)
    assert.equal(questAward('pass-one', '2026-08-23', false).courseId, undefined)
  })
})
