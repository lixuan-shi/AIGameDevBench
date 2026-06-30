extends SceneTree

# visual_static (--script mode): load the menu scene and check the MainMenu
# children match the template: vertical order Start, Options, Quit (top to
# bottom), and all three visible. The baseline has the wrong order (Quit first)
# AND a hidden Options, so the first scored checkpoint (order) fails -> noop=0.
# Fail-fast stable denominator.

const CHECKPOINTS := [
	"buttons_in_template_order",
	"all_three_buttons_present",
	"all_buttons_visible",
]

const EXPECTED_ORDER := ["StartButton", "OptionsButton", "QuitButton"]

var checks := []

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
	quit()

func _init() -> void:
	run_validation()

func run_validation() -> void:
	var packed = load("res://scenes/menu.tscn")
	if packed == null:
		_record("buttons_in_template_order", false, "could not load res://scenes/menu.tscn", "PackedScene", "null")
		return _emit()
	var menu = packed.instantiate()

	var order: Array = []
	for child in menu.get_children():
		if child is Button:
			order.append(String(child.name))

	# Order check first so the wrong-order baseline fails the first scored check.
	if not _record("buttons_in_template_order", order == EXPECTED_ORDER,
			"the menu buttons must be in the template order Start, Options, Quit",
			EXPECTED_ORDER, order):
		return _emit()

	var names := {}
	for n in order:
		names[n] = true
	if not _record("all_three_buttons_present",
			names.has("StartButton") and names.has("OptionsButton") and names.has("QuitButton"),
			"MainMenu must contain StartButton, OptionsButton and QuitButton",
			EXPECTED_ORDER, order):
		return _emit()

	var all_visible := true
	var hidden := []
	for child in menu.get_children():
		if child is Button and not child.visible:
			all_visible = false
			hidden.append(child.name)
	if not _record("all_buttons_visible", all_visible,
			"every menu button must be visible",
			"all visible", ("all visible" if all_visible else "hidden: %s" % str(hidden))):
		return _emit()

	_emit()
