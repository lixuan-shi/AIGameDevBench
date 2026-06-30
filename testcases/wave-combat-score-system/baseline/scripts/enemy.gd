extends Node
class_name Enemy

# A minimal enemy with a 3-state lifecycle: "alive" -> "dying" -> "dead".
# Contract:
#   - starts "alive" with hp = max_hp.
#   - take_damage(n): reduce hp (clamped at 0). When hp hits 0, transition to
#     "dying", emit died ONCE, then settle to "dead". Damage after death does
#     nothing and never re-emits died.
#   - state returns the current state string.
#
# BASELINE: unimplemented.

signal died(enemy)

@export var max_hp: int = 10

var hp: int = 10
var state: String = "alive"

func take_damage(n: int) -> void:
	# TODO: implement the alive->dying->dead lifecycle with a single died emit.
	pass
