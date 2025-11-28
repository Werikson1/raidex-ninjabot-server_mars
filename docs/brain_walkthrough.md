# Brain - Auto Builder Feature

I have added the "Brain" page to the web interface, which allows you to automate building upgrades on your planets.

## Changes Implemented

### 1. New Module: `modules/brain.py`
- **BrainManager**: Handles the logic for fetching planets, checking buildings, and performing upgrades.
- **Logic**:
    - Fetches planets from the game overview.
    - Navigates to the building page for the selected planet.
    - Checks current building levels against your targets.
    - Upgrades buildings if resources are available.
    - Waits if resources are missing (basic implementation).

### 2. New Template: `templates/brain.html`
- **UI**:
    - Planet Selector: Populated dynamically from the game.
    - Building List: Set target levels for each building.
    - Start/Stop Buttons: Control the brain task.

### 3. Web App Updates: `web_app.py`
- Added `/brain` route to serve the new page.
- Added API endpoints:
    - `/api/brain/planets`: Fetches planet list.
    - `/api/brain/start`: Starts the auto-builder.
    - `/api/brain/stop`: Stops the auto-builder.

### 4. Bot Integration: `bot.py`
- Added `run_brain_action` and `start_brain_task` to `OgameBot` class to handle brain operations within the bot's event loop.

## How to Use

1.  **Restart the Bot and Web App**:
    - Since I modified `web_app.py` and `bot.py`, you need to restart the running processes.
    - Stop the current `python web_app.py` and `python bot.py` (or main script).
    - Start them again.

2.  **Access the Brain Page**:
    - Go to `http://localhost:5000/brain` (or your configured host/port).

3.  **Select a Planet**:
    - The dropdown should populate with your planets (it might take a few seconds to fetch from the game).

4.  **Set Targets**:
    - Enter the desired **Max Level** for the buildings you want to upgrade.
    - Leave as 0 to ignore.

5.  **Start Brain**:
    - Click "Start Brain".
    - The bot will navigate to the planet and start checking buildings.
    - Check the console logs for progress.

## Notes
- The bot will try to upgrade buildings in the order they appear or are processed.
- If resources are missing, it will log the status and wait before retrying.
- Ensure the bot is logged in and running for the Brain to work.
