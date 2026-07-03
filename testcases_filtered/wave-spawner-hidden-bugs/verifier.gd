extends Node

# Drives the WaveSpawner through every wave and checks the full contract. The
# baseline has three hidden bugs (off-by-one spawn, wrong clear-boundary, wrong
# final-wave condition); each scored checkpoint targets correct behavior, so the
# buggy baseline fails the first one -> noop=0. Fail-fast stable denominator.

const CHECKPOINTS := [
	"first_wave_spawns_full_size",
	"wave_advances_on_clear",
	"second_wave_full_size",
	"final_wave_spawns_full_size",
	"all_waves_cleared_emitted_once",
	"finished_flag_and_total_spawned",
]

var checks := []
var _cleared_count := 0

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

func _on_cleared() -> void:
	_cleared_count += 1

func _kill(spawner, n: int) -> void:
	for i in range(n):
		spawner.notify_enemy_killed()

func run_validation() -> void:
	var s = get_node_or_null("Main/WaveSpawner")
	if s == null:
		_record("first_wave_spawns_full_size", false, "Main/WaveSpawner not found", "WaveSpawner", "null")
		return _emit()

	var sizes: Array[int] = [3, 5, 4]
	s.wave_sizes = sizes
	if s.has_signal("all_waves_cleared"):
		s.all_waves_cleared.connect(_on_cleared)

	s.start()
	if not _record("first_wave_spawns_full_size", s.live == 3,
			"wave 0 must spawn its full size (3)", 3, s.live):
		return _emit()

	# Clear wave 0 (3 enemies) -> should advance to wave 1 and spawn 5.
	_kill(s, 3)
	if not _record("wave_advances_on_clear", s.current_wave == 1,
			"clearing a wave must advance to the next wave", 1, s.current_wave):
		return _emit()

	if not _record("second_wave_full_size", s.live == 5,
			"wave 1 must spawn its full size (5)", 5, s.live):
		return _emit()

	# Clear wave 1 (5) -> advance to final wave 2, spawn 4.
	_kill(s, 5)
	if not _record("final_wave_spawns_full_size", s.current_wave == 2 and s.live == 4,
			"final wave must spawn its full size (4)",
			"wave=2, live=4", "wave=%d, live=%d" % [s.current_wave, s.live]):
		return _emit()

	# Clear final wave -> all_waves_cleared fires exactly once.
	_kill(s, 4)
	if not _record("all_waves_cleared_emitted_once", _cleared_count == 1,
			"all_waves_cleared must fire exactly once after the last wave", 1, _cleared_count):
		return _emit()

	if not _record("finished_flag_and_total_spawned",
			s.finished == true and s.spawned_total == 12,
			"finished must be true and total spawned must be 3+5+4=12",
			"finished=true, total=12",
			"finished=%s, total=%d" % [s.finished, s.spawned_total]):
		return _emit()

	_emit()
