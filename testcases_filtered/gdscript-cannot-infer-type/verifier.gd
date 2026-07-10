extends Node

# Verifies res://scripts/score_tracker.gd. The baseline script contains a
# GDScript type-inference error (`var value := _scores[i]` on an untyped Array),
# so it fails to PARSE -> scenes/main.tscn can't instance the ScoreTracker node
# -> the node is missing and the very first checkpoint fails -> score 0.
# Golden gives the variable an explicit type (or drops `:=`), the script loads,
# and total_score() returns the summed value. Fail-fast: remaining checkpoints
# are emitted as failed so the denominator stays stable.

const CHECKPOINTS := [
	"script_loads_and_node_present",
	"total_score_returns_sum",
]

var checks := []

func _ready() -> void:
	call_deferred("run_validation")

func _record(name: String, condition: bool, detail: String, expected = null, actual = null) -> bool:
	checks.append({"name": name, "pass": condition, "detail": detail, "expected": expected, "actual": actual})
	return condition

func _emit() -> void:
	var seen := {}
	for c in checks:
		seen[c.name] = true
	for n in CHECKPOINTS:
		if not seen.has(n):
			checks.append({"name": n, "pass": false, "detail": "not reached (an earlier checkpoint failed)", "expected": null, "actual": null})
	print(JSON.stringify({"assertions": checks}))
	get_tree().quit()

func run_validation() -> void:
	# If the script failed to parse, the ScoreTracker node will be missing
	# (or won't expose the method), so this first checkpoint fails -> noop=0.
	var tracker := get_node_or_null("Main/ScoreTracker")
	var present := tracker != null and tracker.has_method("total_score")
	if not _record("script_loads_and_node_present", present,
			"score_tracker.gd must parse/load so Main/ScoreTracker exposes total_score()",
			"ScoreTracker with total_score()", "null or missing method" if not present else "ok"):
		return _emit()

	var total = tracker.total_score()
	if not _record("total_score_returns_sum", total == 42,
			"total_score() must sum the recorded scores (10+25+7)",
			42, total):
		return _emit()

	_emit()
