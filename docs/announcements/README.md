Announcement drafts
===================

Draft posts for introducing this fork, one file per venue. They all lead with
the Player tab — resources and tavern heroes — because that is the reason the
fork exists and no other Heroes 3 savegame editor appears to offer it. The
faster loading and the handle-exhaustion crash fix are closing notes, not the
pitch.

- `1-reddit.md` — r/heroesofmightandmagic
- `2-wiki.md` — the Tools page at heroes.thelazy.net, added beside the existing
  h3sed entry rather than replacing it
- `3-forum.md` — Celestial Heavens or Heroes Community
- `4-gog-thread.md` — reply to the long-running GOG save editor thread

Before posting widely: the tavern feature is only verified against Shadow of
Death savegames. Resource detection scans for the player record array and
validates it, so it fails safe on an unknown layout, but the tavern slot
offsets are relative and would read the wrong bytes if a layout differs.
