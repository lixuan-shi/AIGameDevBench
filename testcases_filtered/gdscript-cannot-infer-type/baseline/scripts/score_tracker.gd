extends Node
class_name ScoreTracker

# Raw per-round scores.
var _scores := [10, 25, 7]


# Sum all recorded scores and return the total.
func total_score() -> int:
	var total := 0
	for i in range(_scores.size()):
		var value := _scores[i]
		total += value
	return total
