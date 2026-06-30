extends Node

# Verifies a Timer node was added AND its timeout signal was wired to the
# spawner's on_respawn(). Boots scenes/main.tscn (instanced as child "Main").
# The first scored checkpoint requires the RespawnTimer node, which the baseline
# scene lacks, so noop=0. Fail-fast stable denominator.

const CHECKPOINTS := [
	"respawn_timer_node_exists",
	"timeout_connected_to_on_respawn",
	"timeout_signal_invokes_handler",
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
	var spawner = get_node_or_null("Main/Spawner")
	if spawner == null:
		_record("respawn_timer_node_exists", false, "Main/Spawner not found", "Spawner", "null")
		return _emit()

	var timer = spawner.get_node_or_null("RespawnTimer")
	if not _record("respawn_timer_node_exists", timer != null and timer is Timer,
			"Spawner must have a Timer child named RespawnTimer",
			"a Timer node", ("none" if timer == null else timer.get_class())):
		return _emit()

	if not _record("timeout_connected_to_on_respawn",
			timer.timeout.is_connected(spawner.on_respawn),
			"RespawnTimer.timeout must be connected to Spawner.on_respawn",
			true, timer.timeout.is_connected(spawner.on_respawn)):
		return _emit()

	var before = spawner.respawn_count
	timer.timeout.emit()
	if not _record("timeout_signal_invokes_handler", spawner.respawn_count == before + 1,
			"emitting timeout must invoke on_respawn (respawn_count increments)",
			before + 1, spawner.respawn_count):
		return _emit()

	_emit()
