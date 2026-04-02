# F1 Top-Down Racing Game

A 2D top-down racing game featuring F1-style cars, AI opponents with rubberbanding, and a custom circuit track. Built with Python and Pygame.

## Features

- **F1-style car physics**: Acceleration, braking, speed-dependent steering, and friction
- **AI opponents**: 5 AI-controlled cars that follow the track using waypoint navigation
- **Rubberbanding**: AI speeds up when behind and slows down when ahead to keep races competitive
- **Race track**: Smooth circuit with curbs, start/finish line, and grass boundaries
- **HUD**: Live speed, lap counter, race position, standings board, and mini-map
- **Car collisions**: Basic physics-based car-to-car collisions
- **Countdown start**: 3-2-1-GO countdown before the race begins

## Controls

| Key | Action |
|-----|--------|
| W / Up Arrow | Accelerate |
| S / Down Arrow | Brake / Reverse |
| A / Left Arrow | Steer Left |
| D / Right Arrow | Steer Right |
| R | Restart (after finishing) |
| ESC | Quit |

## How to Run

```bash
pip install -r requirements.txt
python main.py
```

## Gameplay

- Complete 3 laps around the circuit to finish the race
- Stay on the track! Driving on the grass slows you down significantly
- AI opponents use rubberbanding: they'll catch up if you're far ahead, and slow down if they're way in front
- Your position is shown on the HUD along with a mini-map for navigation
