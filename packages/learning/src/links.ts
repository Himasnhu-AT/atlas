/**
 * Outbound links that are not content.
 *
 * The provider offer is referenced from project lessons, where the optional
 * "Ship it for real" section points the student's own code at a live model.
 * Nothing in the platform requires it: every graded exercise runs against
 * `mockllm`, offline and free.
 *
 * A human swaps these values once, here. Lessons never write the URL or the
 * amount directly; they write a token and the content build substitutes it
 * while it renders the lesson body. That is what keeps the promise this comment
 * makes: change the offer here and every lesson that mentions it is correct on
 * the next build, with nothing left to grep for.
 */
export const PROVIDER_SIGNUP = {
  url: 'PLACEHOLDER_REFERRAL_URL',
  credit: '$175',
  note: 'Sign up with GitHub',
}

/** False until a human has replaced the placeholder URL with a real one. */
export const PROVIDER_OFFER_IS_LIVE = !PROVIDER_SIGNUP.url.startsWith('PLACEHOLDER')

/**
 * The offer is one token expanding to a whole sentence, not a URL token the
 * lesson wraps in its own anchor.
 *
 * A lesson that wrote its own anchor around a URL token would ship
 * `href="PLACEHOLDER_REFERRAL_URL"` in the default state, which is a dead
 * relative link sitting under a promise of credit. The unit that has to be
 * present or absent is the offer, not the URL, so the offer is what the token
 * carries. Below, the sentence either makes the promise and links to it, or
 * makes no promise at all.
 */
const offerSentence = PROVIDER_OFFER_IS_LIVE
  ? `${PROVIDER_SIGNUP.note} and <a href="${PROVIDER_SIGNUP.url}">receive ` +
    `${PROVIDER_SIGNUP.credit} of credit</a> to run against a live model what you built here.`
  : 'Any provider with a free tier is enough. At the sizes you are working with a full run ' +
    'costs cents, and the suite you were graded on stays free whatever you choose.'

/**
 * The tokens a lesson writes, mapped to what they render as.
 *
 * Substitution happens on the rendered HTML rather than on the MDX source, so
 * the live sentence can carry its own anchor and a token inside a fenced code
 * block is replaced too. The build fails on any `PLACEHOLDER_` token still
 * standing in a rendered lesson, which is what stops a typo or a retired token
 * reaching a student as literal text.
 */
export const CONTENT_TOKENS: Record<string, string> = {
  PLACEHOLDER_REFERRAL_OFFER: offerSentence,
}
