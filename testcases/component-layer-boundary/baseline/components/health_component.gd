extends Control

# Reusable health component. It is meant to be a pure gameplay component (a
# plain Node) and must NOT depend on the ui/ layer, but right now it both
# extends a UI type and reaches into the ui/ layer directly.

const HealthBar := preload("res://ui/health_bar.gd")

var max_health: int = 100
var health: int = 100
var _bar = null

func take_damage(amount: int) -> void:
	health = clampi(health - amount, 0, max_health)
	if _bar == null:
		_bar = HealthBar.new()
	_bar.set_ratio(float(health) / float(max_health))
