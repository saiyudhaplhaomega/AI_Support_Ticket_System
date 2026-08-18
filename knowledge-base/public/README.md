# knowledge-base/public/

Corpus for the public-facing chat workflow, indexed into the separate Qdrant collection
`noavia_public_chat_kb_v1`.

| Document | Topic |
|---|---|
| `about-noavia.md` | Company overview |
| `public-support-faq.md` | Public FAQ |

**Not used by the ticket pipeline.** The ticket pipeline reads only
`knowledge-base/noavia/`. This exists for the public chat workflow, which was
exploration beyond the task scope.

Kept in a separate collection deliberately: public-facing answers must not be able to
retrieve internal support documentation.
