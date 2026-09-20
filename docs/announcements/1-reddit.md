# r/heroesofmightandmagic  (also works for r/HoMM3)

## Title
I added tavern hero and resource editing to a Heroes 3 save editor — you can pick
exactly who shows up in your tavern

## Body

Every Heroes 3 savegame editor I could find edits heroes: skills, spells, army,
artifacts. None of them touch player-level data. So I added it.

**What's new:**

- **Tavern heroes** — choose exactly which heroes are offered in your tavern,
  instead of reloading the save over and over until the one you want appears.
  Only heroes actually still available are offered, so you can't pick someone
  already on the map.
- **Resources** — set gold, wood, ore, mercury, sulfur, crystal and gems to
  whatever you like.

It also figures out which player is yours from the savefile, so it opens on your
own data rather than making you guess which of the eight colours you are, and it
can filter the hero list down to just your heroes.

This is a fork of [h3sed by suurjaak](https://github.com/suurjaak/h3sed), which
is an excellent editor and did all the hard work of decoding the save format. My
fork adds the Player tab and changes some UI behaviour that is a matter of taste,
which is why it's a fork rather than a pull request.

Two other things that came out of it: savegames open a good deal faster, because
heroes are now parsed on demand rather than all upfront, and it no longer dies if
you open a lot of savegames in a sitting.

Download (Windows, no install, just unzip and run):
https://github.com/kvit-s/h3sed/releases

Source: https://github.com/kvit-s/h3sed

[attach img/screen.png]

---
NOTE ON CHEAT CODES — someone will say "just use a cheat code for gold".
Reply along these lines: cheats give a fixed amount to everyone and do nothing
for taverns. This sets exact values for a specific player, and tavern hero
selection isn't possible any other way.
