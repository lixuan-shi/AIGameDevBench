# Converted from GameDevBench task_0051 test.gd.
# Emits one assertion per checkpoint ({"assertions":[...]}) with expected/actual
# so the report explains WHAT failed. Fail-fast: on the first failed checkpoint,
# the remaining (unreached) checkpoints are emitted as failed so the denominator
# stays the full checkpoint count and scores remain comparable across runs.
extends Node

const CHECKPOINTS := [
	"main_present",
	"player_present",
	"player_is_characterbody2d",
	"player_has_script",
	"sprite_present",
	"sprite_has_texture",
	"sprite_texture_source",
	"collider_present",
	"collider_is_rectangle",
	"collider_size",
	"script_readable",
	"exports_speed",
	"exports_jump_speed",
	"exports_gravity",
	"export_defaults",
	"applies_gravity",
	"reads_move_axis",
	"calls_move_and_slide",
	"jump_on_action",
	"jump_checks_floor",
]

var checks := []

func _ready() -> void:
	run_validation()

func _record(name: String, condition: bool, detail: String,
		expected = null, actual = null) -> bool:
	checks.append({"name": name, "pass": condition, "detail": detail,
		"expected": expected, "actual": actual})
	return condition

func _emit() -> void:
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

func run_validation() -> void:
	var main = get_node_or_null("Main")
	if not _record("main_present", main != null, "Main scene is missing",
			"Main node", "null"):
		return _emit()

	var player = main.get_node_or_null("Player")
	if not _record("player_present", player != null, "Player node not found under Main",
			"Player node", "null"):
		return _emit()
	if not _record("player_is_characterbody2d", player is CharacterBody2D,
			"Player must be a CharacterBody2D", "CharacterBody2D", player.get_class()):
		return _emit()

	var script = player.get_script()
	if not _record("player_has_script", script != null, "Player script is missing",
			"a script", "null"):
		return _emit()

	var sprite = player.get_node_or_null("Sprite2D")
	if not _record("sprite_present", sprite != null, "Sprite2D child missing on Player",
			"Sprite2D node", "null"):
		return _emit()
	if not _record("sprite_has_texture", sprite.texture != null,
			"Sprite2D must use the provided texture", "a texture", "null"):
		return _emit()
	if not _record("sprite_texture_source",
			sprite.texture.resource_path.find("tileYellow_02.png") != -1,
			"Sprite2D texture should come from tileYellow_02.png",
			"tileYellow_02.png", sprite.texture.resource_path):
		return _emit()

	var collider = player.get_node_or_null("CollisionShape2D")
	if not _record("collider_present", collider != null,
			"CollisionShape2D child missing on Player", "CollisionShape2D node", "null"):
		return _emit()
	var shape = collider.shape
	if not _record("collider_is_rectangle", shape != null and shape is RectangleShape2D,
			"Player collision must be a RectangleShape2D", "RectangleShape2D",
			"null" if shape == null else shape.get_class()):
		return _emit()
	var expected_size = Vector2(32, 68)
	if not _record("collider_size", shape.size.is_equal_approx(expected_size),
			"Collision rectangle size should be (32, 68)", expected_size, shape.size):
		return _emit()

	var script_path = script.resource_path
	var script_file = FileAccess.open(script_path, FileAccess.READ)
	if not _record("script_readable", script_file != null, "Unable to read player.gd",
			"readable player.gd", "could not open"):
		return _emit()
	var script_text = script_file.get_as_text()
	if not _record("exports_speed", script_text.find("@export var speed") != -1,
			"Player script must export a speed property", "@export var speed", "absent"):
		return _emit()
	if not _record("exports_jump_speed", script_text.find("@export var jump_speed") != -1,
			"Player script must export a jump_speed property", "@export var jump_speed", "absent"):
		return _emit()
	if not _record("exports_gravity", script_text.find("@export var gravity") != -1,
			"Player script must export a gravity property", "@export var gravity", "absent"):
		return _emit()
	if not _record("export_defaults",
			script_text.find("= 1200") != -1 and script_text.find("-1800") != -1 and script_text.find("= 4000") != -1,
			"Exported defaults should match 1200/-1800/4000", "1200/-1800/4000", "missing one or more"):
		return _emit()
	if not _record("applies_gravity", script_text.find("velocity.y += gravity * delta") != -1,
			"gravity must increment velocity.y each frame", "velocity.y += gravity * delta", "absent"):
		return _emit()
	var axis_a = script_text.find("Input.get_axis(\"move_left\"")
	var axis_b = script_text.find("Input.get_axis('move_left'")
	if not _record("reads_move_axis", axis_a != -1 or axis_b != -1,
			"Player must read move_left/move_right via Input.get_axis",
			"Input.get_axis(\"move_left\", ...)", "absent"):
		return _emit()
	if not _record("calls_move_and_slide", script_text.find("move_and_slide()") != -1,
			"move_and_slide must be called", "move_and_slide()", "absent"):
		return _emit()
	if not _record("jump_on_action",
			script_text.find("Input.is_action_just_pressed(\"jump\"") != -1 or script_text.find("Input.is_action_just_pressed('jump'") != -1,
			"Jump should be triggered via Input.is_action_just_pressed(\"jump\")",
			"Input.is_action_just_pressed(\"jump\")", "absent"):
		return _emit()
	if not _record("jump_checks_floor", script_text.find("is_on_floor()") != -1,
			"Jump logic must check is_on_floor()", "is_on_floor()", "absent"):
		return _emit()

	_emit()
