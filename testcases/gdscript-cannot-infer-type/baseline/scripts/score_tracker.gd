extends Node
class_name ScoreTracker

# Raw per-round scores. The array is untyped, so its elements are Variant.
var _scores := [10, 25, 7]


# Sum all recorded scores and return the total.
func total_score() -> int:
	var total := 0
	for i in range(_scores.size()):
		# BUG: `_scores[i]` indexes an untyped Array, so the element type is
		# Variant. Using `:=` here makes the parser fail with
		# "Cannot infer the type of "value" variable because the value
		# doesn't have a set type." The whole script then fails to load.
		var value := _scores[i]
		total += value
	return total
