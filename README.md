# Gamma Alpha Chore System
Script for assigning chores in our house.

The flow is to get people's preferences from an [online Google Sheet](https://docs.google.com/spreadsheets/d/1hAq34ijA1pvcZZyv1So8rTvm2rzOfrDHion8INifApg/edit#gid=0), and ask the user which people and which chores should be done this week.

At the beginning of each four-week-cycle, chore assignments are rotated. Then a "full optimization" takes place to find universally agreeable loops of people who what to swap chores.

Each of the three weeks thereafter, the relevant chores are pulled from the cycle start, specific one-week chores only are rotated, and then a "partial optimization" takes place in which people who are displaced by the one-week chore adjustments have a chance to execute agreeable pairwise swaps.

"Swaps" are only ever executed when all parties to the swap improved their misery ranking.  So this system is a guaranteed enhancement to a pure chore rotation, but is NOT a global optimizer.  It is, however, deterministic.

After execution, an email is drafted as an HTML page which (if you're configured correctly), can open in a webpage for you to copy into your email software of choice, a history file is recorded, and a bar chart of the optimization results is produced.

Note: if someone has never done a particular chore before, that chore will have misery level zero, regardless of what the Google sheet says, which makes it likely that new people will quickly rotate through all the chores.
