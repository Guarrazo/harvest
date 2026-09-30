NCIG v0.21.5 CET bounds-harvester hotfix.

Replace ONLY:
cet/NCIGBoundsHarvester/init.lua

Fixes CET's:
bad argument #2 to 'insert' (number expected, got string)

The harvester now uses explicit array append semantics instead of the
2-argument table.insert form that fails in this CET Lua environment.
