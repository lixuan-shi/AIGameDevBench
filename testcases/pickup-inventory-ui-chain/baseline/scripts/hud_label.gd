extends Label
class_name HudLabel

# Displays the inventory count. Must connect to the Inventory's
# inventory_changed signal and update its text to str(new_count).
#
# BASELINE (buggy): bind() does nothing, so the label never updates.

func bind(inventory: Inventory) -> void:
	# TODO: connect inventory.inventory_changed to _on_inventory_changed.
	pass

func _on_inventory_changed(new_count: int) -> void:
	text = str(new_count)
