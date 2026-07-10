extends Node
class_name Equipment


var total_bonus: int = 0
var _slots: Dictionary = {}  # slot -> bonus

func equip(slot: String, bonus: int) -> void:
	pass

func unequip(slot: String) -> void:
	pass
