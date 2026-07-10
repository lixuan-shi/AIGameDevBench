extends Label
class_name HudLabel



func bind(inventory: Inventory) -> void:
	pass

func _on_inventory_changed(new_count: int) -> void:
	text = str(new_count)
