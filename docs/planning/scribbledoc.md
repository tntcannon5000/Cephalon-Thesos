# Thesos Scribbledoc

A living collection of product, design, data, architecture, operations, and other ideas for Thesos. Entries are exploratory unless explicitly promoted into a specification or implementation task.

## Idea 001: Suggested Prompts With Reset-Aware Caching

**Added:** 2026-08-13  
**Areas:** Landing experience, response speed, caching, live Warframe data  
**Status:** Idea

Present a small selection of useful prompts on the landing page that people can click to receive an immediate answer, similar to the initial prompts shown by Google AI Studio.

Good candidates are frequently asked questions whose answers change on a predictable Warframe schedule, such as:

- Which Incarnon Genesis rewards are available in the current Steel Path Circuit rotation?
- What special events are currently active?
- What time-limited activities or rewards should I consider today?

These answers can be generated or assembled ahead of demand and cached. For daily state, the cache TTL should expire at Warframe's daily reset rather than an arbitrary duration after the first request. Where applicable, weekly questions should expire at their corresponding weekly rotation boundary.

### Why It Matters

- Gives new visitors an immediate understanding of what Thesos can answer.
- Produces near-instant responses for common, recurring questions.
- Reduces repeated retrieval, tool, and model work.
- Makes operating a free service more affordable.
- Encourages useful discovery without requiring users to know what to ask first.

### Implementation Notes

- Verify the authoritative UTC time for Warframe's daily reset and each relevant weekly rotation.
- Calculate expiration as the next reset timestamp, not as a fixed 24-hour TTL.
- Include platform, language, source version, and relevant rotation identifiers in cache keys where needed.
- Allow event-driven invalidation when live state changes before the expected reset.
- Prefer deterministic assembly from live and structured data when an LLM is unnecessary.
- Show the answer's effective time or next refresh time when freshness matters.
- Treat the prompt cards and their cached answers as a fast path into the same full conversation experience, so users can ask follow-up questions naturally.

