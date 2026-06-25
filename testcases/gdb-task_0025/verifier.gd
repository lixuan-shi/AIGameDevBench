# Converted from GameDevBench task_0025 test.gd.
# Emits one assertion per checkpoint ({"assertions":[...]}) with expected/actual
# so the report explains WHAT failed. Fail-fast: on the first failed checkpoint,
# the remaining (unreached) checkpoints are emitted as failed so the denominator
# stays the full checkpoint count and scores remain comparable across runs.
extends Node

const CHECKPOINTS := [
	"interact_action_defined",
	"interact_bound_to_f",
	"main_instanced",
	"interaction_area_present",
	"collision_filtering",
	"body_entered_connected",
	"body_exited_connected",
	"item_types_two_templates",
	"item_data_assigned",
	"pickups_instanced",
	"enter_shows_highlight",
	"pickup_removes_from_nearby",
	"picked_item_freed",
	"pickup_emits_first_item",
	"exit_removes_body",
	"exit_hides_highlight",
]

var checks := []

func _ready() -> void:
	await get_tree().process_frame
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
	if not _record("interact_action_defined", InputMap.has_action("interact"),
			"Project must define an 'interact' input action", true,
			InputMap.has_action("interact")):
		return _emit()
	var events := InputMap.action_get_events("interact")
	var has_f_key := false
	for event in events:
		if event is InputEventKey and event.physical_keycode == KEY_F:
			has_f_key = true
			break
	if not _record("interact_bound_to_f", has_f_key,
			"'interact' action must be bound to the F key", "F key", has_f_key):
		return _emit()
	var main_node = get_node_or_null("Main")
	if not _record("main_instanced", main_node != null,
			"Main scene was not instanced", "Main node", "null"):
		return _emit()
	var interaction_area: PlayerInteractionHandler = main_node.get_node_or_null("PlayerBody/InteractionArea")
	if not _record("interaction_area_present", interaction_area != null,
			"InteractionArea node missing from PlayerBody", "InteractionArea node", "null"):
		return _emit()
	if not _record("collision_filtering",
			interaction_area.collision_layer == 0 and interaction_area.collision_mask == 2,
			"InteractionArea collision filtering must be layer 0 / mask 2",
			"layer 0 / mask 2",
			"layer %d / mask %d" % [interaction_area.collision_layer, interaction_area.collision_mask]):
		return _emit()
	var entered_callable := Callable(interaction_area, "_on_body_entered")
	var exited_callable := Callable(interaction_area, "_on_body_exited")
	if not _record("body_entered_connected",
			interaction_area.is_connected("body_entered", entered_callable),
			"body_entered signal must be connected to _on_body_entered",
			"connected", "not connected"):
		return _emit()
	if not _record("body_exited_connected",
			interaction_area.is_connected("body_exited", exited_callable),
			"body_exited signal must be connected to _on_body_exited",
			"connected", "not connected"):
		return _emit()
	if not _record("item_types_two_templates", interaction_area.item_types.size() == 2,
			"InteractionArea.item_types must contain two templates", 2,
			interaction_area.item_types.size()):
		return _emit()
	var names := interaction_area.item_types.map(func(item: ItemData): return item.item_name)
	if not _record("item_data_assigned",
			names.has("Test Cube") and names.has("Test Sphere"),
			"ItemData resources must be assigned for Test Cube and Test Sphere",
			"[Test Cube, Test Sphere]", str(names)):
		return _emit()
	var cube: InteractableItem = main_node.get_node_or_null("ItemPickupCube")
	var sphere: InteractableItem = main_node.get_node_or_null("ItemPickupSphere")
	if not _record("pickups_instanced", cube != null and sphere != null,
			"Main scene must instance both pickup prefabs", "cube and sphere",
			"cube=%s sphere=%s" % [cube != null, sphere != null]):
		return _emit()
	interaction_area.nearby_bodies.clear()
	interaction_area._on_body_entered(cube)
	if not _record("enter_shows_highlight", cube.item_highlight_mesh.visible,
			"gain_focus should show the highlight when entering the area",
			true, cube.item_highlight_mesh.visible):
		return _emit()
	interaction_area._on_body_entered(sphere)
	var picked := []
	interaction_area.item_picked_up.connect(func(item_data: ItemData): picked.append(item_data.item_name))
	var event := InputEventAction.new()
	event.action = "interact"
	event.pressed = true
	interaction_area._input(event)
	if not _record("pickup_removes_from_nearby", not (cube in interaction_area.nearby_bodies),
			"Nearest item should be removed from nearby_bodies after pickup",
			"cube removed", "cube still present"):
		return _emit()
	if not _record("picked_item_freed", cube.is_queued_for_deletion(),
			"Picked item must be queued for deletion", "queued for deletion",
			cube.is_queued_for_deletion()):
		return _emit()
	if not _record("pickup_emits_first_item",
			picked.size() > 0 and picked[0] == "Test Cube",
			"Picking up the first item must emit Test Cube", "Test Cube",
			str(picked)):
		return _emit()
	interaction_area._on_body_exited(sphere)
	if not _record("exit_removes_body", not (sphere in interaction_area.nearby_bodies),
			"_on_body_exited must remove the body from nearby_bodies",
			"sphere removed", "sphere still present"):
		return _emit()
	if not _record("exit_hides_highlight", not sphere.item_highlight_mesh.visible,
			"lose_focus must hide the highlight on exit", false,
			sphere.item_highlight_mesh.visible):
		return _emit()
	_emit()
