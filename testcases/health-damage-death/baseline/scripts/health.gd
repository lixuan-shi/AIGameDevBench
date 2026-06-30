extends Node
class_name Health

# Tracks hit points. take_damage() reduces health; when health reaches 0 the
# entity is dead and the `died` signal must fire exactly once.
#
# BASELINE (buggy): health is not clamped at 0 (it can go negative) and `died`
# is not emitted at all.

signal died

@export var max_health: int = 30

var health: int = 30
var is_dead: bool = false

func take_damage(amount: int) -> void:
	# TODO: clamp health at 0, set is_dead, and emit `died` exactly once.
	health -= amount
