extends Node

# Verifies the Ability cooldown contract. Boots scenes/main.tscn (instanced as
# child "Main") and drives the Ability node. Every checkpoint requires real
# cooldown gating, so an unimplemented baseline (can_use() always true, no timer)
# fails the first scored checkpoint -> score 0. Fail-fast: on the first failure
# the remaining checkpoints are emitted as failed so the denominator is stable.

const CHECKPOINTS := [
	"blocked_immediately_after_use",
	"still_blocked_before_cooldown_elapses",
	"usable_after_full_cooldown",
	"second_use_succeeds_after_cooldown",
	"reblocked_after_second_use",
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
	var ability := get_node_or_null("Main/Ability")
	if ability == null:
		_record("blocked_immediately_after_use", false, "Main/Ability node not found", "Ability node", "null")
		return _emit()

	ability.cooldown = 1.0

	# Fire once; it should now be on cooldown.
	var first = ability.use()
	if not _record("blocked_immediately_after_use", first == true and ability.can_use() == false,
			"after use(), can_use() must be false until cooldown elapses",
			"use()=true, can_use()=false", "use()=%s, can_use()=%s" % [first, ability.can_use()]):
		return _emit()

	# Advance less than the cooldown: still blocked.
	ability.tick(0.5)
	if not _record("still_blocked_before_cooldown_elapses", ability.can_use() == false,
			"can_use() must stay false before the full cooldown elapses",
			false, ability.can_use()):
		return _emit()

	# Advance past the cooldown: usable again.
	ability.tick(0.6)
	if not _record("usable_after_full_cooldown", ability.can_use() == true,
			"can_use() must be true once the full cooldown has elapsed",
			true, ability.can_use()):
		return _emit()

	# Use again; should succeed and re-arm the cooldown.
	var second = ability.use()
	if not _record("second_use_succeeds_after_cooldown", second == true,
			"use() must succeed once the cooldown has elapsed",
			true, second):
		return _emit()

	if not _record("reblocked_after_second_use", ability.can_use() == false,
			"after the second use(), can_use() must be false again",
			false, ability.can_use()):
		return _emit()

	_emit()
