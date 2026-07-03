extends Node

# Verifies res://scenes/main.tscn. The baseline scene references a Texture2D via
# [ext_resource path="res://assets/player.svg"] that DOES NOT EXIST, so headless
# Godot reports "No loader found for resource: res://assets/player.svg
# (expected type: Texture2D)" and the scene fails to load -> the whole verifier
# scene can't instance "Main" -> first checkpoint fails -> noop=0.
# Golden replaces the missing external texture with an in-scene resource (e.g. a
# PlaceholderTexture2D sub_resource) so the scene loads and the Player sprite has
# a real texture. Fail-fast keeps the checkpoint denominator stable.

const CHECKPOINTS := [
	"player_sprite_has_texture",
	"texture_has_expected_size",
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
	# If main.tscn failed to load (missing resource), "Main/Player" won't exist
	# or its texture will be null -> this first checkpoint fails -> noop=0.
	var player := get_node_or_null("Main/Player")
	var tex = null
	if player != null and "texture" in player:
		tex = player.texture
	if not _record("player_sprite_has_texture", player != null and tex != null,
			"main.tscn must load and Main/Player must have a non-null texture",
			"Sprite2D with texture", "null" if player == null else ("no texture" if tex == null else "ok")):
		return _emit()

	var size = tex.get_size()
	if not _record("texture_has_expected_size", size == Vector2(64, 64),
			"the player texture must be 64x64",
			Vector2(64, 64), size):
		return _emit()

	_emit()
