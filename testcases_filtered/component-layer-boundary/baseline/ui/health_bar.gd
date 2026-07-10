extends Control

# A UI widget that displays a health value. Lives in the ui/ layer.

func set_ratio(ratio: float) -> void:
	if has_node("Fill"):
		get_node("Fill").scale.x = clampf(ratio, 0.0, 1.0)
