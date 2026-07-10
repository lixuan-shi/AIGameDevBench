extends Node

# Checks compute_damage against the documented formula. Each scored checkpoint
# isolates one interacting rule (subtraction, crit-after-defense, min-1 floor,
# crit-on-blocked-hit). The baseline stub returns 0 -> fails the first -> noop=0.
# A naive implementation that crits before defense, or forgets the floor, lands
# partial. Fail-fast stable denominator.

const CHECKPOINTS := [
	"basic_subtraction",
	"crit_doubles_after_defense",
	"floor_at_one_when_blocked",
	"crit_on_blocked_hit_still_min_one",
	"zero_raw_floored_to_one",
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
	var c = get_node_or_null("Main/Combat")
	if c == null:
		_record("basic_subtraction", false, "Main/Combat not found", "Combat", "null")
		return _emit()

	var d1 = c.compute_damage(10, 3, false)
	if not _record("basic_subtraction", d1 == 7,
			"compute_damage(10,3,false) must be 7", 7, d1):
		return _emit()

	var d2 = c.compute_damage(10, 3, true)
	if not _record("crit_doubles_after_defense", d2 == 14,
			"crit doubles the post-defense value: (10-3)*2 = 14, not (10*2-3)=17", 14, d2):
		return _emit()

	var d3 = c.compute_damage(5, 9, false)
	if not _record("floor_at_one_when_blocked", d3 == 1,
			"compute_damage(5,9,false) must floor to 1 (raw -4)", 1, d3):
		return _emit()

	var d4 = c.compute_damage(5, 9, true)
	if not _record("crit_on_blocked_hit_still_min_one", d4 == 1,
			"a crit on a fully-blocked hit still floors to 1", 1, d4):
		return _emit()

	var d5 = c.compute_damage(8, 8, false)
	if not _record("zero_raw_floored_to_one", d5 == 1,
			"compute_damage(8,8,false) raw 0 must floor to 1", 1, d5):
		return _emit()

	_emit()
