# Populate Current Building Levels in Brain Page

## Goal
Update the Brain page to automatically populate the "Current Level" column in the buildings table when a planet is selected from the dropdown.

## User Review Required
> [!NOTE]
> This change relies on the `empire_data.json` structure. If the keys in `facilities` differ from the `BUILDINGS` keys (case-sensitivity), I will need to map them.

## Proposed Changes

### Templates

#### [MODIFY] [brain.html](file:///c:/Users/etton/Desktop/GitHub/raidex-ninjabot/templates/brain.html)
-   Update `loadPlanets` to store the fetched planets in a global variable `window.empirePlanets`.
-   Add an event listener to `#planetSelect` that triggers `updateBuildingLevels()`.
-   Implement `updateBuildingLevels()`:
    -   Get the selected planet ID/coords.
    -   Find the planet object in `window.empirePlanets`.
    -   Iterate through `BUILDINGS`.
    -   Match the building ID (e.g., `METAL_MINE`) to the key in `planet.facilities` (e.g., `metal_mine`).
    -   Update the text content of the corresponding `#current-{id}` cell.

## Verification Plan

### Manual Verification
1.  Refresh the Brain page.
2.  Select a planet from the dropdown.
3.  Verify that the "Current Level" column updates with values matching `empire_data.json`.
4.  Select a different planet and verify updates.
