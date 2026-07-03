extends Node

const CHECKPOINTS := [
	"north_bridge_crossed",
	"right_platform_south_target_reached",
	"south_bridge_crossed",
]
const SAMPLE_FRAMES := 240
const VERIFIER_MOVEMENT_SPEED := 10.0
const VERIFIER_WAIT_AT_TARGET := 0.05

var checks := []

func _ready() -> void:
	call_deferred("run_validation")


func _record(name: String, condition: bool, detail: String, expected = null, actual = null) -> bool:
	checks.append({"name": name, "pass": condition, "detail": detail, "expected": expected, "actual": actual})
	return condition


func _emit() -> void:
	var seen := {}
	for check in checks:
		seen[check.name] = true
	for checkpoint in CHECKPOINTS:
		if not seen.has(checkpoint):
			checks.append({"name": checkpoint, "pass": false, "detail": "not reached (an earlier checkpoint failed)", "expected": null, "actual": null})
	print(JSON.stringify({"assertions": checks}))
	get_tree().quit()


func run_validation() -> void:
	var main_node := get_node_or_null("Main")
	if main_node == null:
		_record("north_bridge_crossed", false, "Main scene did not load", "Main node", "null")
		return _emit()
	var npc := main_node.get_node_or_null("BridgePathfindingNPC")
	if npc == null or not npc is Node3D:
		_record("north_bridge_crossed", false, "BridgePathfindingNPC missing", "Node3D", "null/wrong type")
		return _emit()

	npc.set("movement_speed", VERIFIER_MOVEMENT_SPEED)
	npc.set("wait_at_target", VERIFIER_WAIT_AT_TARGET)

	var positions: Array[Vector3] = []
	for frame in range(SAMPLE_FRAMES):
		await get_tree().physics_frame
		positions.append(npc.global_position)

	var north_crossed := _has_position(positions, 3.0, INF, -1.45, -0.95)
	if not _record("north_bridge_crossed", north_crossed,
			"NPC must reach the right side of the north bridge (x >= 3 at z ~= -1.2)",
			"some sampled position with x >= 3 and -1.45 <= z <= -0.95",
			_summarize_positions(positions)):
		return _emit()

	var right_south_reached := _has_position(positions, 5.0, INF, 0.75, 1.45)
	if not _record("right_platform_south_target_reached", right_south_reached,
			"NPC must move along the right platform from the north bridge target toward the south bridge target",
			"some sampled position with x >= 5 and 0.75 <= z <= 1.45",
			_summarize_positions(positions)):
		return _emit()

	var south_crossed := _has_position_after_right_south(positions, -INF, -2.8, 0.95, 1.45)
	if not _record("south_bridge_crossed", south_crossed,
			"After reaching the right south target, NPC must cross the south bridge back toward the left platform",
			"later sampled position with x <= -2.8 and 0.95 <= z <= 1.45",
			_summarize_positions(positions)):
		return _emit()

	_emit()


func _has_position(positions: Array[Vector3], min_x: float, max_x: float, min_z: float, max_z: float) -> bool:
	for position in positions:
		if position.x >= min_x and position.x <= max_x and position.z >= min_z and position.z <= max_z:
			return true
	return false


func _has_position_after_right_south(positions: Array[Vector3], min_x: float, max_x: float, min_z: float, max_z: float) -> bool:
	var gate_passed := false
	for position in positions:
		if position.x >= 5.0 and position.z >= 0.75:
			gate_passed = true
		if gate_passed and position.x >= min_x and position.x <= max_x and position.z >= min_z and position.z <= max_z:
			return true
	return false


func _summarize_positions(positions: Array[Vector3]) -> Dictionary:
	if positions.is_empty():
		return {"samples": 0}
	var min_x := INF
	var max_x := -INF
	var min_z := INF
	var max_z := -INF
	for position in positions:
		min_x = min(min_x, position.x)
		max_x = max(max_x, position.x)
		min_z = min(min_z, position.z)
		max_z = max(max_z, position.z)
	return {
		"samples": positions.size(),
		"min_x": min_x,
		"max_x": max_x,
		"min_z": min_z,
		"max_z": max_z,
		"final": str(positions[positions.size() - 1]),
	}
