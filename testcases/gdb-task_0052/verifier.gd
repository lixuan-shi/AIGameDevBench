# Converted from GameDevBench task_0052 test.gd.
# Emits one assertion per checkpoint ({"assertions":[...]}) with expected/actual
# so the report explains WHAT failed. Fail-fast: on the first failed checkpoint,
# the remaining (unreached) checkpoints are emitted as failed so the denominator
# stays the full checkpoint count and scores remain comparable across runs.
extends Node

const PLAYER_SCENE := "res://scenes/player.tscn"
const SPEED := 1200.0
const JUMP_SPEED := -1800.0

const CHECKPOINTS := [
	"player_scene_loads",
	"player_instances",
	"has_physics_process",
	"friction_accel_exported",
	"friction_default",
	"acceleration_default",
	"accelerates_right",
	"acceleration_is_gradual",
	"has_velocity_before_friction",
	"decelerates",
	"comes_to_stop",
	"reaches_floor",
	"jump_velocity",
]

var checks := []
var _done := false

func _ready() -> void:
	var player_scene: PackedScene = load(PLAYER_SCENE)
	if not _record("player_scene_loads", player_scene != null,
			"Failed to load Player scene.", "a loadable PackedScene", "null"):
		return _emit()

	var player: CharacterBody2D = player_scene.instantiate()
	if not _record("player_instances", player != null,
			"Failed to instance Player scene.", "a CharacterBody2D instance", "null"):
		return _emit()

	# Create a floor
	var floor := StaticBody2D.new()
	var floor_shape = RectangleShape2D.new()
	floor_shape.extents = Vector2(1000, 10)
	var floor_collider = CollisionShape2D.new()
	floor_collider.shape = floor_shape
	floor.add_child(floor_collider)
	floor.position = Vector2(0, 600)

	add_child(player)
	add_child(floor)
	player.position = Vector2(0, 550)

	await test_suite(player)

func _record(name: String, condition: bool, detail: String,
		expected = null, actual = null) -> bool:
	checks.append({"name": name, "pass": condition, "detail": detail,
		"expected": expected, "actual": actual})
	return condition

func _emit() -> void:
	if _done:
		return
	_done = true
	var seen := {}
	for c in checks:
		seen[c.name] = true
	for n in CHECKPOINTS:
		if not seen.has(n):
			checks.append({"name": n, "pass": false,
				"detail": "not reached (an earlier checkpoint failed)",
				"expected": null, "actual": null})
	print(JSON.stringify({"assertions": checks}))
	get_tree().quit()

func test_suite(player: CharacterBody2D) -> void:
	if not _record("has_physics_process", player.has_method("_physics_process"),
			"Player script is missing _physics_process(delta).", true,
			player.has_method("_physics_process")):
		return _emit()

	if not _record("friction_accel_exported",
			player.get("friction") is float and player.get("acceleration") is float,
			"Friction and acceleration must be exported float variables.",
			"both float", "friction=%s acceleration=%s" % [typeof(player.get("friction")), typeof(player.get("acceleration"))]):
		return _emit()

	if not _record("friction_default", is_equal_approx(player.get("friction"), 0.1),
			"Default friction should be 0.1.", 0.1, player.get("friction")):
		return _emit()

	if not _record("acceleration_default", is_equal_approx(player.get("acceleration"), 0.25),
			"Default acceleration should be 0.25.", 0.25, player.get("acceleration")):
		return _emit()

	await test_acceleration(player)
	if _done:
		return
	await test_friction(player)
	if _done:
		return
	await test_jump(player)
	if _done:
		return

	await get_tree().process_frame
	_emit()

func test_acceleration(player: CharacterBody2D) -> void:
	Input.action_press("move_right")
	var initial_velocity_x = player.velocity.x

	await get_tree().physics_frame
	await get_tree().physics_frame

	var velocity_after_2_frames = player.velocity.x
	if not _record("accelerates_right", velocity_after_2_frames > initial_velocity_x,
			"Player is not accelerating to the right. Velocity did not increase.",
			"velocity increases", "%.3f -> %.3f" % [initial_velocity_x, velocity_after_2_frames]):
		Input.action_release("move_right")
		return _emit()

	if not _record("acceleration_is_gradual", velocity_after_2_frames < SPEED,
			"Player accelerated too fast. Should be a gradual lerp.",
			"< %.0f after 2 frames" % SPEED, velocity_after_2_frames):
		Input.action_release("move_right")
		return _emit()

	Input.action_release("move_right")

func test_friction(player: CharacterBody2D) -> void:
	Input.action_press("move_right")
	await get_tree().physics_frame
	await get_tree().physics_frame
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("move_right")

	var initial_velocity_x = player.velocity.x
	if not _record("has_velocity_before_friction", initial_velocity_x > 0,
			"Player should have positive velocity before friction test.",
			"> 0", initial_velocity_x):
		return _emit()

	await get_tree().physics_frame
	await get_tree().physics_frame

	var velocity_after_2_frames = player.velocity.x
	if not _record("decelerates", velocity_after_2_frames < initial_velocity_x,
			"Player is not decelerating. Check friction implementation.",
			"velocity decreases", "%.3f -> %.3f" % [initial_velocity_x, velocity_after_2_frames]):
		return _emit()

	var is_stopping = false
	for i in range(200):
		await get_tree().physics_frame
		if abs(player.velocity.x) < 1.0:
			is_stopping = true
			break

	if not _record("comes_to_stop", is_stopping,
			"Player did not come to a stop. Check friction lerp.",
			"|velocity.x| < 1.0", player.velocity.x):
		return _emit()

func test_jump(player: CharacterBody2D) -> void:
	player.position = Vector2(0, 550)
	for i in range(10):
		await get_tree().physics_frame

	if not _record("reaches_floor", player.is_on_floor(),
			"Could not get player to be on the floor to test jump.",
			"on floor", player.is_on_floor()):
		return _emit()

	Input.action_press("jump")
	await get_tree().physics_frame
	await get_tree().physics_frame

	if not _record("jump_velocity", player.velocity.y < JUMP_SPEED / 2.0,
			"Player jump velocity is not correct.",
			"< %.0f" % (JUMP_SPEED / 2.0), player.velocity.y):
		Input.action_release("jump")
		return _emit()

	Input.action_release("jump")
