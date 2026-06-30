extends Node
class_name Combat

# compute_damage must implement this EXACT formula (the rules interact, so the
# order matters):
#   1. raw = attack - defense
#   2. if is_crit: the POST-defense raw is doubled (crit multiplies what gets
#      through armor, not the base attack)
#   3. the result is floored to a MINIMUM of 1 (an attack always chips at least
#      1, even when defense >= attack)
#   4. the returned value is an int
#
# Worked examples (use these to verify):
#   compute_damage(10, 3, false) -> 7
#   compute_damage(10, 3, true)  -> 14      (7 doubled)
#   compute_damage(5, 9, false)  -> 1       (raw -4, floored to 1)
#   compute_damage(5, 9, true)   -> 1       (crit on a blocked hit still min 1,
#                                            NOT (-4*2) and NOT 2)
#   compute_damage(8, 8, false)  -> 1       (raw 0, floored to 1)
#
# BASELINE: unimplemented stub (returns 0).

func compute_damage(attack: int, defense: int, is_crit: bool) -> int:
	# TODO: implement the formula above.
	return 0
