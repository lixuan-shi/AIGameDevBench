extends Node
class_name Health


signal died

@export var max_health: int = 30

var health: int = 30
var is_dead: bool = false

func take_damage(amount: int) -> void:
	health -= amount
