# Robot Skill Recording Guide

This guide explains how to record robot skills using both GUI-based and continuous recording modes.

## Recording Modes

### 1. GUI-Based Recording

GUI-based recording allows you to manually control the robot and record specific keyframes with precise timing.

```bash
# For real robot
python run.py --real --robot alum1 --record_skill my_skill_name

# For simulation
python run.py --sim --record_skill my_skill_name
```

#### Features:
- **Joint Control Tab**: Adjust individual joint positions
- **Recording Tab**: Record keyframes and set delays between frames
- **Manual Positioning**: Check the "Manual Positioning" box to disable torque and physically move the robot
- **Frame-by-Frame**: Record only the specific poses you want

#### Workflow:
1. Position the robot using the Joint Control tab or by enabling Manual Positioning
2. Set the delay time (how long to wait before the next frame during playback)
3. Click "Record Keyframe" to save the current position
4. Repeat steps 1-3 for each keyframe
5. Click "Save and Exit" when done

### 2. Continuous Recording

Continuous recording automatically captures the robot's movements as you physically guide it.

```bash
# For real robot
python run.py --real --robot alum1 --record_skill continuous_my_skill_name

# For simulation (not recommended, as you can't manually position a simulated robot)
python run.py --sim --record_skill continuous_my_skill_name
```

#### Features:
- **No GUI**: Recording happens automatically in the background
- **High-Frequency Sampling**: Records at 50Hz by default to capture smooth, natural movements
- **Smart Filtering**: Only records when positions change significantly
- **Automatic Post-Processing**: Optimizes recorded frames for smooth playback
- **Keyboard Controls**: Save or stop recording with keyboard shortcuts

#### Workflow:
1. Start continuous recording
2. Physically move the robot (torque is automatically disabled)
3. The system will record positions at high frequency (50Hz)
4. Use keyboard controls to save or stop recording:
   - **Press Ctrl+C**: Stop recording and save the skill
   - **Press 's' key**: Save current frames without stopping (on Windows)
   - **Press 's' key + Enter**: Save current frames without stopping (on macOS/Linux)
   - **Press 'c' key**: Enter command mode to execute commands (on Windows)
   - **Press 'c' key + Enter**: Enter command mode to execute commands (on macOS/Linux)

#### Improved Recording Quality:
The continuous recording system has been enhanced with several features:
1. **High-Frequency Sampling**: Records at 50Hz to capture smooth, natural movements
2. **Sensitive Motion Detection**: More responsive to subtle movements in important joints
3. **Automatic Frame Optimization**: Post-processes recorded frames for optimal playback
4. **Smart Downsampling**: Intelligently reduces frame count while preserving motion quality
5. **Consistent Timing**: Ensures playback timing matches the original recording

These improvements result in much more natural and fluid playback of recorded movements.

### Command Mode

When in command mode, you can execute various commands:

1. **Save with custom filename**:
   ```
   save my_custom_filename
   ```
   This saves the current recording to `planners/recorded_skills/my_custom_filename.json`

2. **Toggle manual mode**:
   ```
   manual_mode
   ```
   This toggles the manual positioning mode on/off (enables/disables torque)

> **Note**: When you press 'c' to enter command mode, the robot will pause recording until you complete your command. This allows you to type your command without the robot continuing to record or move. After you press Enter to execute your command, the robot will resume normal operation.

## Playing Back Recorded Skills

To play back a recorded skill:

```bash
# For real robot with default settings (20Hz)
python run.py --real --robot alum1 --play_skill my_skill_name

# For simulation
python run.py --sim --play_skill my_skill_name

# For both real robot and simulation
python run.py --real --sim --robot alum1 --play_skill my_skill_name

# For smoother playback with lower frequency (recommended)
python run.py --real --robot alum1 --play_skill my_skill_name --HZ 10
```

The playback works the same way regardless of which recording method was used.

### Playback Improvements

The playback system has been enhanced with several features to make movements smoother and safer:

1. **Gradual Zeroing**: The robot now moves to the zero position gradually in multiple steps rather than all at once
2. **Gentle Torque Settings**: Lower gains and torque limits are used during playback for smoother movements
3. **Velocity Limiting**: Joint velocities are capped to prevent abrupt movements
4. **Smooth Interpolation**: An ease-in/ease-out function is applied to make transitions between frames more natural
5. **Startup Delay**: A delay is added before playback begins to ensure the robot is stable

For the best results, use a lower frequency (10-20 Hz) with the `--HZ` parameter.

## Adjusting Recording Parameters

For continuous recording, the system now automatically uses a high frequency (50Hz) internally to capture smooth movements, regardless of the `--HZ` parameter. The `--HZ` parameter still affects playback frequency:

```bash
# Record with default settings (internal 50Hz recording, 20Hz playback)
python run.py --real --robot alum1 --record_skill continuous_my_skill_name

# Play back at 10Hz for smoother movement (recommended)
python run.py --real --robot alum1 --HZ 10 --play_skill my_skill_name

# Play back at 30Hz for faster movement
python run.py --real --robot alum1 --HZ 30 --play_skill my_skill_name
```

For GUI-based recording, the `--HZ` parameter affects the default delay between frames:

```bash
# Record with GUI at 10Hz (default delay of 0.1s between frames)
python run.py --real --robot alum1 --HZ 10 --record_skill my_skill_name
```

## Tips

- For precise, choreographed movements, use GUI-based recording
- For natural, fluid movements, use continuous recording
- Adjust the `--HZ` parameter to control recording/playback frequency
- Skills are saved in the `planners/recorded_skills/` directory
- You don't need to specify `--planner record_skill` or `--planner play_skill` - the system automatically sets the planner based on the `--record_skill` or `--play_skill` argument 