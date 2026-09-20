# Celestial Heavens forum / Heroes Community
# Longer and more formal than Reddit; this crowd reads properly.

## Subject
Save editor fork with tavern hero and resource editing

## Body

I have been using suurjaak's h3sed to edit savegames, and kept wanting two
things it does not do: setting resources, and choosing who turns up in the
tavern. As far as I can tell no Heroes 3 savegame editor does either — they all
work at the hero level. So I added a Player tab that does.

What it edits:

- gold, wood, ore, mercury, sulfur, crystal and gems, per player
- the heroes offered in the tavern, picking only from heroes still available,
  so you cannot accidentally pick someone already placed on the map

The tavern part is the one I actually wanted. Rerolling a save until the tavern
offers a hero with the specialty you want gets old quickly.

The editor also works out which player is the human one from the savefile and
opens on that player, and can narrow the hero list to that player's heroes,
which helps on maps with a couple of hundred heroes.

This is a fork rather than a pull request. The Player tab would probably be
welcome upstream, but the fork also changes some UI behaviour — one savegame
open at a time rather than a tab per file — and that is a matter of taste I did
not want to argue about. All credit to suurjaak for the editor and for working
out the savefile format, which is the genuinely hard part.

Incidental improvements: savegames open faster, because heroes are parsed when
needed rather than all at once, and the program no longer runs out of Windows
window handles and dies when a lot of savegames get opened in one sitting.

Windows build, no installation needed:
https://github.com/kvit-s/h3sed/releases
Source: https://github.com/kvit-s/h3sed
