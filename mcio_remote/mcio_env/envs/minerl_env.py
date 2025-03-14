"""
This provides an environment compatible with the minerl 1.0 action and observation spaces.

Minerl Observation Space:
Dict(pov:Box(low=0, high=255, shape=(360, 640, 3)))
obs['pov'].shape
(360, 640, 3)
obs['pov'].dtype
dtype('uint8')

{'pov': array([[[17, 17, 17],
        [17, 17, 17],
        [17, 17, 17],
        ...,
        [16, 15, 14],
        [21, 19, 17],
        [21, 19, 16]],



Minerl Action Space:
Dict({
    "ESC": "Discrete(2)",
    "attack": "Discrete(2)",
    "back": "Discrete(2)",
    "camera": "Box(low=-180.0, high=180.0, shape=(2,))",
    "drop": "Discrete(2)",
    "forward": "Discrete(2)",
    "hotbar.1": "Discrete(2)",
    "hotbar.2": "Discrete(2)",
    "hotbar.3": "Discrete(2)",
    "hotbar.4": "Discrete(2)",
    "hotbar.5": "Discrete(2)",
    "hotbar.6": "Discrete(2)",
    "hotbar.7": "Discrete(2)",
    "hotbar.8": "Discrete(2)",
    "hotbar.9": "Discrete(2)",
    "inventory": "Discrete(2)",
    "jump": "Discrete(2)",
    "left": "Discrete(2)",
    "pickItem": "Discrete(2)",
    "right": "Discrete(2)",
    "sneak": "Discrete(2)",
    "sprint": "Discrete(2)",
    "swapHands": "Discrete(2)",
    "use": "Discrete(2)"
})

OrderedDict([('ESC', array(0)), ('attack', array(1)), ('back', array(0)), ('camera', array([-21.149803,  41.296047], dtype=float32)), ('drop', array(1)), ('forward', array(1)), ('hotbar.1', array(0)), ('hotbar.2', array(1)), ('hotbar.3', array(0)), ('hotbar.4', array(1)), ('hotbar.5', array(1)), ('hotbar.6', array(1)), ('hotbar.7', array(0)), ('hotbar.8', array(1)), ('hotbar.9', array(0)), ('inventory', array(1)), ('jump', array(1)), ('left', array(0)), ('pickItem', array(1)), ('right', array(0)), ('sneak', array(0)), ('sprint', array(0)), ('swapHands', array(1)), ('use', array(1))])

for k, v in action.items(): print(k, v, v.dtype, v.shape)
ESC 0 int64 ()
attack 1 int64 ()
back 0 int64 ()
camera [-21.149803  41.296047] float32 (2,)
drop 1 int64 ()
forward 1 int64 ()
hotbar.1 0 int64 ()
hotbar.2 1 int64 ()
hotbar.3 0 int64 ()
hotbar.4 1 int64 ()
hotbar.5 1 int64 ()
hotbar.6 1 int64 ()
hotbar.7 0 int64 ()
hotbar.8 1 int64 ()
hotbar.9 0 int64 ()
inventory 1 int64 ()
jump 1 int64 ()
left 0 int64 ()
pickItem 1 int64 ()
right 0 int64 ()
sneak 0 int64 ()
sprint 0 int64 ()
swapHands 1 int64 ()
use 1 int64 ()

"""
