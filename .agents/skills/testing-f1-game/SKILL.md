# Testing the F1 Racing Game

## Overview
This is a Pygame-based desktop game. Testing requires a display server (DISPLAY=:0).

## Running the Game
```bash
export DISPLAY=:0
pip install -r requirements.txt
python main.py
```

## Testing Approach

### Keyboard Input Limitation
Pygame uses `pygame.key.get_pressed()` which checks the real-time held state of keys. xdotool `key` events (press+release) are too brief to register. Use `xdotool keydown`/`keyup` with a sleep in between, or better yet, use the auto-pilot approach below.

### Auto-Pilot Testing
For automated testing, create a test harness that subclasses `PlayerCar` with AI-like waypoint following. This bypasses keyboard input issues and allows a full race to run automatically. See `/tmp/test_game.py` pattern:
1. Import the game classes
2. Create an `AutoPlayerCar` that follows track waypoints like the AI does
3. Replace `game.player` with the auto-pilot car
4. Run the game loop and log status (state, lap, position, speed, on_track)

### Key Things to Verify
- **HUD elements**: Lap counter, position, speed, standings board, mini-map, timer all render
- **Car physics**: Speed reaches ~270 km/h (max_speed * 30), stays on track
- **AI opponents**: All 5 navigate the track without getting stuck
- **Rubberbanding**: Player position improves over the race (e.g., P6 → P3) as AI adjusts speed
- **Lap counting**: Correctly increments through 3 laps using threshold-based wrap-around detection
- **Finish screen**: Shows position, time, and restart instructions after 3 laps
- **Off-track penalty**: Speed drops when driving on grass (off_max_speed = 3.0 → ~90 km/h)

### Recording
This is a GUI app — always record when testing. Maximize the game window before recording.

## Devin Secrets Needed
None — this is a standalone game with no external dependencies.
