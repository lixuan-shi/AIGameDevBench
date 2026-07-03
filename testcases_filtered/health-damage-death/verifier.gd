extends Node

# Verifies the Health damage/death contract. Boots scenes/main.tscn (instanced
# as child "Main"). Every scored checkpoint requires correct clamping + a
# single death signal, so the buggy baseline (no clamp, no signal) fails the
# first scored checkpoint -> score 0. Fail-fast stable denominator.

const CHECKPOINTS := [
	"health_clamped_at_zero",
	"died_emitted_on_lethal_hit",
	"is_dead_flag_set",
	"died_emitted_exactly_once",
	"no_damage_after_death",
]

var checks := []
var _died_count := 0

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

func _on_died() -> void:
	_died_count += 1

func run_validation() -> void:
	var health := get_node_or_null("Main/Health")
	if health == null:
		_record("health_clamped_at_zero", false, "Main/Health node not found", "Health node", "null")
		return _emit()

	health.max_health = 30
	health.health = 30
	health.is_dead = false
	if health.has_signal("died"):
		health.died.connect(_on_died)

	# Deal a lethal overkill hit: 50 damage to 30 HP.
	health.take_damage(50)

	if not _record("health_clamped_at_zero", health.health == 0,
			"health must clamp at 0, never go negative",
			0, health.health):
		return _emit()

	if not _record("died_emitted_on_lethal_hit", _died_count >= 1,
			"died must be emitted when health reaches 0",
			">= 1", _died_count):
		return _emit()

	if not _record("is_dead_flag_set", health.is_dead == true,
			"is_dead must be true after death",
			true, health.is_dead):
		return _emit()

	# A second lethal hit must NOT re-emit died.
	health.take_damage(50)
	if not _record("died_emitted_exactly_once", _died_count == 1,
			"died must fire exactly once even on repeated lethal hits",
			1, _died_count):
		return _emit()

	if not _record("no_damage_after_death", health.health == 0,
			"health must stay at 0 after death (no underflow on further hits)",
			0, health.health):
		return _emit()

	_emit()
