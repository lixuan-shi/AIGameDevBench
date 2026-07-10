# Converted from GameDevBench task_0012 test.gd.
# Emits one assertion per checkpoint ({"assertions":[...]}) with expected/actual
# so the report explains WHAT failed. Fail-fast: on the first failed checkpoint,
# the remaining (unreached) checkpoints are emitted as failed so the denominator
# stays the full checkpoint count and scores remain comparable across runs.
extends Node

const CHECKPOINTS := [
    "bullet_scene_loads",
    "bullet_uses_gdscript",
    "has_const_speed",
    "exposes_direction",
    "exposes_tank",
    "has_physics_process",
    "has_on_area_entered",
    "has_on_body_entered",
    "physics_moves_by_speed",
    "area_handler_frees",
    "body_handler_frees_bullet",
    "body_handler_frees_crate",
]

var checks := []

func _ready():
    await run_validation()

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

func load_bullet_scene() -> PackedScene:
    return load("res://scenes/entities/tank/weapon/bullet.tscn")

func instantiate_bullet(main: Node) -> Area2D:
    var scene = load_bullet_scene()
    if scene == null:
        return null
    var bullet: Area2D = scene.instantiate()
    main.add_child(bullet)
    return bullet

func run_validation() -> void:
    var main: Node = get_node("Main")
    var scene = load_bullet_scene()
    if not _record("bullet_scene_loads", scene != null,
            "Bullet scene missing at res://scenes/entities/tank/weapon/bullet.tscn",
            "a loadable PackedScene", "null" if scene == null else "loaded"):
        return _emit()

    var bullet: Area2D = scene.instantiate()
    main.add_child(bullet)
    var script_ref: Script = bullet.get_script()
    if not _record("bullet_uses_gdscript", script_ref is GDScript,
            "Bullet must use a GDScript script", "GDScript",
            "null" if script_ref == null else "non-GDScript"):
        return _emit()

    if not _record("has_const_speed", has_constant_speed(bullet),
            "Define const SPEED = 500 in bullet.gd", 500,
            _speed_value(bullet)):
        return _emit()
    if not _record("exposes_direction", has_script_property(script_ref, "direction"),
            "Expose a direction property on Bullet", "direction property", "absent"):
        return _emit()
    if not _record("exposes_tank", has_script_property(script_ref, "tank"),
            "Expose a tank property on Bullet", "tank property", "absent"):
        return _emit()
    if not _record("has_physics_process", bullet.has_method("_physics_process"),
            "Implement _physics_process for bullet movement",
            true, bullet.has_method("_physics_process")):
        return _emit()
    if not _record("has_on_area_entered", bullet.has_method("_on_area_entered"),
            "Implement _on_area_entered handler",
            true, bullet.has_method("_on_area_entered")):
        return _emit()
    if not _record("has_on_body_entered", bullet.has_method("_on_body_entered"),
            "Implement _on_body_entered handler",
            true, bullet.has_method("_on_body_entered")):
        return _emit()

    bullet.position = Vector2.ZERO
    bullet.direction = Vector2(0, 10)
    bullet._physics_process(0.1)
    if not _record("physics_moves_by_speed", is_equal_approx(bullet.position.length(), 50.0),
            "_physics_process must move by direction.normalized() * SPEED * delta",
            50.0, bullet.position.length()):
        return _emit()

    # area handler frees the bullet
    var temp_a: Area2D = instantiate_bullet(main)
    temp_a._on_area_entered(null)
    await get_tree().process_frame
    if not _record("area_handler_frees", not is_instance_valid(temp_a),
            "_on_area_entered must queue_free the bullet",
            "freed", "still valid" if is_instance_valid(temp_a) else "freed"):
        return _emit()

    # body handler frees bullet and crate
    var temp_b: Area2D = instantiate_bullet(main)
    var crate_scene: PackedScene = load("res://scenes/entities/world/crate.tscn")
    var crate: Node = crate_scene.instantiate()
    main.add_child(crate)
    temp_b._on_body_entered(crate)
    await get_tree().process_frame
    if not _record("body_handler_frees_bullet", not is_instance_valid(temp_b),
            "_on_body_entered must queue_free the bullet",
            "freed", "still valid" if is_instance_valid(temp_b) else "freed"):
        return _emit()
    if not _record("body_handler_frees_crate", not is_instance_valid(crate),
            "Crate must be destroyed after bullet hit",
            "freed", "still valid" if is_instance_valid(crate) else "freed"):
        return _emit()

    _emit()

func has_constant_speed(bullet: Area2D) -> bool:
    var script: Script = bullet.get_script()
    if script == null or not (script is GDScript):
        return false
    var constants: Dictionary = (script as GDScript).get_script_constant_map()
    return constants.has("SPEED") and constants["SPEED"] == 500

func _speed_value(bullet: Area2D):
    var script: Script = bullet.get_script()
    if script == null or not (script is GDScript):
        return "no script"
    var constants: Dictionary = (script as GDScript).get_script_constant_map()
    return constants.get("SPEED", "unset")

func has_script_property(script: GDScript, property_name: String) -> bool:
    for prop in script.get_script_property_list():
        if prop.has("name") and prop["name"] == property_name:
            return true
    return false
