extends Node
class_name Ability


@export var cooldown: float = 1.0

var _time_remaining: float = 0.0

func can_use() -> bool:
	return true

func use() -> bool:
	return true

func tick(delta: float) -> void:
	pass
