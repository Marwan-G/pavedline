---
name: seo-foundation
description: The SEO baseline across Pavedline's steps, read by steps 1, 3, 4, 7, 9 and 12 and by the Grow loop. States what each step must produce for search (research, site map and URLs, stack row, Core Web Vitals templates, the step 9 SEO gate, production-only indexing), keeps staging noindex, and lists sitemap submission to Google Search Console and Bing Webmaster Tools as founder steps under ask-before-adding. Use when a step touches the website, the blog or search, or when content-ops needs the baseline.
---

# seo-foundation

Classic SEO is the foundation; Core Web Vitals "good" is LCP at most 2.5 s, INP at most 200 ms, CLS at most 0.1 at the 75th percentile (facts and dates: `references/sources.md`). `llms.txt` has no ranking effect and is optional. This skill is a baseline other skills read, not a step of its own: it never moves `STATE.md`.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md` when a step uses it.

## 1. What each step produces for search

| Step | Must produce |
|---|---|
| Step 1 | SEO research in `SEO-STRATEGY.md`: target queries, intent, competitors, the content gaps |
| Step 3 | the site map with short, stable URLs (blog under `/blog`), each page's search intent and conversion goal |
| Step 4 | the SEO row of the stack decision: rendering, sitemap and robots generation, metadata API, image handling |
| Step 7 | templates built for Core Web Vitals: space reserved for images, one clear LCP element, a font loading plan, readable articles, an author box (real author and credentials), an Open Graph image template |
| Step 9 | the SEO gate on `apps/site` (section 2) |
| Step 12 | only production is indexable; sitemaps submitted (section 4) |

## 2. The step 9 SEO gate: point to it, never duplicate it

The gate already ships with the stack: Lighthouse CI budgets in `apps/site/lighthouserc.json`, run by `.github/workflows/ci-site.yml` against the production build, plus the site's generated `sitemap.xml` and `robots.txt`, canonical URLs, Open Graph tags and JSON-LD. The default thresholds, the lab LCP and CLS limits and the link check are written in the spec (§6.6) and in those files. This skill never duplicates the numbers or the checks: to change a budget, edit `lighthouserc.json`; to add a check, add it to `ci-site.yml`. The gate runs on the local production build, never on staging.

## 3. Indexing: staging and every non-public origin stay `noindex`

Only production is indexable. The site's `proxy.ts` reads the environment at runtime and sends `X-Robots-Tag: noindex, nofollow` from any origin that is not the public one; its boot check and a test prove it, and the web app is disallow-all in `robots.ts`. On staging both are deliberate: robots.txt blocks crawling on staging and the noindex header covers direct hits. Before launch and after any change to hosts or environment variables, check that staging answers `noindex` and that production answers none. A staging origin that becomes indexable is a defect, not a setting. The step 9 SEO gate scores a `noindex` origin as not crawlable on purpose, so it runs on the local production build with indexing enabled.

## 4. Search consoles are founder steps

Verifying the domain and submitting `sitemap.xml` to **Google Search Console** and **Bing Webmaster Tools** need the founder's accounts. The agent never creates one. Under ask-before-adding (spec §12.6) it says what the service is, what it will do, why nothing already running does it and its cost (both are free), and lists each step in `WAITING.md` until the founder says it is done:

- verify the production domain in Google Search Console, then submit `https://<production host>/sitemap.xml`;
- the same in Bing Webmaster Tools;
- request indexing of new pages there (the `content-ops` loop, last step).

Record "submitted" only on the founder's word.

## 5. Used by

`content-ops` runs the Grow loop on this baseline. Vendor facts, with URL and date, are in `references/sources.md`.
