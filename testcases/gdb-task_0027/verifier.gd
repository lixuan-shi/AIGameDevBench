# Converted from GameDevBench task_0027 test.gd.
# Emits one assertion per checkpoint ({"assertions":[...]}) with expected/actual
# so the report explains WHAT failed. Fail-fast: on the first failed checkpoint,
# the remaining (unreached) checkpoints are emitted as failed so the denominator
# stays the full checkpoint count and scores remain comparable across runs.
extends Node

const CHECKPOINTS := [
    "player_and_weapon_present",
    "weapon_has_impulse_signal",
    "weapon_has_fire_weapon",
    "player_has_apply_impulse",
    "signal_connected",
    "shake_power_export_present",
    "shake_power_default",
    "barrel_raycast_present",
    "fire_forwards_recoil",
    "impulse_pushes_backwards",
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
    var scene: PackedScene = load("res://scenes/main.tscn")
    var root = scene.instantiate()
    add_child(root)
    await get_tree().process_frame

    var player = root.get_node_or_null("PlayerBody")
    var weapon = root.get_node_or_null("WeaponEffects")
    if not _record("player_and_weapon_present", player != null and weapon != null,
            "PlayerBody or WeaponEffects missing from Main scene",
            "both present", "player=%s weapon=%s" % [player != null, weapon != null]):
        return _emit()

    if not _record("weapon_has_impulse_signal", weapon.has_signal("on_shot_camera_impulse"),
            "WeaponEffects must declare on_shot_camera_impulse signal",
            true, weapon.has_signal("on_shot_camera_impulse")):
        return _emit()

    if not _record("weapon_has_fire_weapon", weapon.has_method("fire_weapon"),
            "WeaponEffects must expose fire_weapon()",
            true, weapon.has_method("fire_weapon")):
        return _emit()

    if not _record("player_has_apply_impulse", player.has_method("apply_weapon_impulse"),
            "PlayerBody needs apply_weapon_impulse() handler",
            true, player.has_method("apply_weapon_impulse")):
        return _emit()

    var connection := Callable(player, "apply_weapon_impulse")
    if not _record("signal_connected", weapon.is_connected("on_shot_camera_impulse", connection),
            "Connect WeaponEffects.on_shot_camera_impulse to PlayerBody.apply_weapon_impulse",
            "connected", "not connected"):
        return _emit()

    var power_property := weapon.get_property_list().filter(func(info): return info.name == "camera_shake_power")
    if not _record("shake_power_export_present", not power_property.is_empty(),
            "camera_shake_power export missing on WeaponEffects",
            "camera_shake_power export", "absent"):
        return _emit()

    if not _record("shake_power_default", is_equal_approx(float(weapon.get("camera_shake_power")), 0.3),
            "camera_shake_power default must be 0.3", 0.3,
            float(weapon.get("camera_shake_power"))):
        return _emit()

    var ray_cast = weapon.get_node_or_null("BarrelEnd/BarrelRayCast")
    if not _record("barrel_raycast_present", ray_cast != null,
            "BarrelRayCast missing under WeaponEffects", "BarrelRayCast node", "null"):
        return _emit()

    player.camera_shake_position = Vector3.ZERO
    weapon.fire_weapon()
    await get_tree().process_frame

    if not _record("fire_forwards_recoil", player.camera_shake_position.length() > 0.0,
            "apply_weapon_impulse should forward weapon recoil to PlayerBody",
            "non-zero shake", player.camera_shake_position.length()):
        return _emit()

    if not _record("impulse_pushes_backwards", player.camera_shake_position.z < 0.0,
            "Impulse direction should push camera backwards along -Z",
            "z < 0", player.camera_shake_position.z):
        return _emit()

    _emit()
