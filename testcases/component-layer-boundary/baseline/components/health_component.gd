extends Control

const HealthBar := preload("res://ui/health_bar.gd")

var max_health: int = 100
var health: int = 100
var _bar = null

func take_damage(amount: int) -> void:
	health = clampi(health - amount, 0, max_health)
	if _bar == null:
		_bar = HealthBar.new()
	_bar.set_ratio(float(health) / float(max_health))
