# Implementation Plan - Ogamex Galaxy Bot

The goal is to create a bot to automate pagination of the Galaxy view in the Ogamex web game. We will use Python and Playwright for robust browser automation.

## User Review Required

> [!IMPORTANT]
> **Target URL**: The bot is currently designed to test against the local `galaxy_view.html` file or the live game URL. Please confirm if you want to run this against the live server immediately or test locally first.
> **Credentials**: If running against the live game, you will need to provide login logic or manually log in. The current plan assumes we start with the galaxy page already accessible or handle login simply.

## Proposed Changes

### Project Structure
We will create a simple Python project structure.

#### [NEW] [bot.py](file:///c:/Users/weriksonsr/Desktop/ogamex_developer/bot.py)
- Main script to run the bot.
- Uses `playwright` to control the browser.
- **Functions**:
    - `run_bot()`: Main entry point.
    - `login()`: Placeholder for login logic.
    - `paginate_galaxy()`: Logic to cycle through solar systems.

### Bot Logic (`bot.py`)
1.  **Initialization**: Start Playwright, launch browser (Chromium), create context.
2.  **Navigation**: Go to the target URL (local file or game URL).
3.  **Pagination Loop**:
    - Locate the System input field (`#systemInput`).
    - Locate the "Next System" button (`#btnSystemRight`) or use the "Go" button (`.x-btn-go`).
    - Iterate through a range of systems (e.g., 1 to 499 as seen in the HTML `max-value="499"`).
    - For each system:
        - Update the input or click "Next".
        - Click "Go" if necessary.
        - Wait for the `#galaxyContent` to update (detect network idle or specific element appearance).
        - (Optional) Print current system to console.

### Asteroid Finder Logic
1.  **Detection**: In each system visited, check if `.btn-asteroid-find` exists in Slot 17.
2.  **Activation**: If found, click the button and wait for `#ajax-asteroid-modal-container`.
3.  **Parsing**: Extract the system range from the links in `#playerAsteroidTable`.
    - Example: `[3:74:17]` and `[3:94:17]` -> Range: Galaxy 3, Systems 74-94.
4.  **Search Loop**:
    - Pause current pagination.
    - Iterate through the extracted system range.
    - In each system, check Slot 17.
    - If "Asteroid found" (timer visible), stop search.
    - Resume original pagination.

### Fleet Dispatch Logic
1. **Trigger**: When asteroid is clicked, bot waits for navigation to `/fleet`.
2. **Step 1**: Select fleet group "300 MM" in `#fleetGroupSelect`.
3. **Step 2**: Click Next (`#btn-next-fleet2`).
4. **Step 3**: Click Next (`#btn-next-fleet3`).
5. **Step 4**: Click Send Fleet (`#btn-submit-fleet`).
6. **Return**: Navigate back to Galaxy view to continue search/pagination.

## Verification Plan

### Automated Tests
- We will run the `bot.py` script.
- **Command**: `python bot.py`
- **Success Criteria**: The browser opens, loads the page, and automatically changes the solar system number, updating the view.
- Mock the HTML to include the button and modal.
- Verify the bot detects the button and enters the search loop.

### Manual Verification
- Watch the browser window (running in headed mode) to ensure it moves from System X to System X+1 correctly.
- Run on live site and wait for an asteroid event (or find one manually to test).
