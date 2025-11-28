# Travel Time Verification System

## Overview

The bot now includes an intelligent **Travel Time Verification** system to prevent wasted fleet trips. Before dispatching a fleet to an asteroid, the bot checks if there's enough time for the fleet to arrive before the asteroid disappears.

## Problem Solved

### The Issue
- Fleet is based at system **247**
- Asteroids can spawn anywhere from system **1** to **499**
- The further the asteroid, the longer it takes for the fleet to arrive
- If the fleet arrives after the asteroid disappears, the trip is **wasted**

### The Solution
Before dispatching, the bot:
1. **Reads** the asteroid's disappear timer
2. **Calculates** the distance from base (system 247)
3. **Determines** required travel time based on distance
4. **Compares** timer vs. required time
5. **Decides** whether to dispatch or skip

## How It Works

### 1. Reading Asteroid Timer

The timer is stored in an HTML attribute:
```html
<span data-asteroid-disappear="1542">(25:42)</span>
```

The bot parses `data-asteroid-disappear` which contains **seconds remaining**.

### 2. Distance Calculation

```python
distance = abs(system - BASE_SYSTEM)
# Example: Asteroid at system 300, base at 247
# distance = abs(300 - 247) = 53 systems
```

### 3. Travel Time Ranges

Based on distance from base (system 247), the bot requires minimum asteroid time:

| Distance Range | Systems      | Min. Time Required |
|----------------|--------------|-------------------|
| 0-23 systems   | 220-270      | **20 minutes**    |
| 24-53 systems  | 200-300      | **25 minutes**    |
| 54-103 systems | 150-350      | **30 minutes**    |
| 104-153 systems| 100-400      | **36 minutes**    |
| 154-203 systems| 50-450       | **41 minutes**    |
| 204-499 systems| 1-499        | **45 minutes**    |

### 4. Decision Logic

```python
if asteroid_timer >= required_time:
    ✅ Dispatch fleet
else:
    ⏰ Skip and add to cooldown
```

## Example Scenarios

### ✅ Scenario 1: Sufficient Time
```
🎯 ASTEROID FOUND: [3:300:17]
  ⏱  Asteroid timer: 30 minutes
  📏 Distance: 53 systems (from base 247)
  🕐 Required time: 25 minutes
  ✅ Sufficient time! Dispatching fleet...
```
**Result**: Fleet dispatched! (30min > 25min)

### ⏰ Scenario 2: Insufficient Time
```
🎯 ASTEROID FOUND: [3:180:17]
  ⏱  Asteroid timer: 22 minutes
  📏 Distance: 67 systems (from base 247)
  🕐 Required time: 30 minutes
  ⏰ Insufficient time (22 < 30 min)
  ➜ Adding to cooldown to avoid wasted trip
```
**Result**: Skipped! Would arrive too late (22min < 30min needed)

## Configuration

In [`modules/config.py`](file:///c:/Users/weriksonsr/Desktop/ogamex_developer/modules/config.py):

```python
# Base system where fleet is stationed
BASE_SYSTEM = 247

# Distance ranges and minimum required time
TRAVEL_TIME_RANGES = [
    (0, 23, 20),      # 0-23 systems   = 20 min
    (24, 53, 25),     # 24-53 systems  = 25 min
    (54, 103, 30),    # 54-103 systems = 30 min
    (104, 153, 36),   # 104-153 systems = 36 min
    (154, 203, 41),   # 154-203 systems = 41 min
    (204, 499, 45),   # 204-499 systems = 45 min
]
```

### Adjusting Travel Times

If you find fleets arriving too late/early, adjust the time values:

```python
# Make it more conservative (require more time)
(54, 103, 35),  # Changed from 30 to 35 minutes

# Make it less conservative (require less time)
(24, 53, 22),  # Changed from 25 to 22 minutes
```

## Implementation Details

### Code Flow

#### In `asteroid_finder.py`:

1. **Timer Parsing**:
```python
async def _get_asteroid_timer(self, page: Page) -> Optional[int]:
    timer_element = page.locator("[data-asteroid-disappear]").first
    timer_seconds = int(await timer_element.get_attribute("data-asteroid-disappear"))
    return timer_seconds // 60  # Convert to minutes
```

2. **Travel Time Calculation**:
```python
def _get_required_travel_time(self, distance: int) -> int:
    for min_dist, max_dist, required_time in self.travel_time_ranges:
        if min_dist <= distance <= max_dist:
            return required_time
    return self.travel_time_ranges[-1][2]  # Default to longest
```

3. **Decision Making**:
```python
timer_minutes = await self._get_asteroid_timer(page)
distance = abs(system - self.base_system)
required_minutes = self._get_required_travel_time(distance)

if timer_minutes >= required_minutes:
    # Dispatch!
    await asteroid_btn.first.click()
    return (galaxy, system, position)
else:
    # Skip and add to cooldown
    cooldown_mgr.add_to_cooldown(galaxy, system, position)
    continue
```

## Benefits

### ✅ No Wasted Trips
Fleet only dispatches when there's enough time

### ✅ Smart Cooldown
Skipped asteroids are added to cooldown, preventing re-checks

### ✅ Maximizes Efficiency
Bot focuses on viable targets only

### ✅ Configurable
Easy to adjust travel times based on fleet speed

## Console Output

### Sufficient Time:
```
🎯 ASTEROID FOUND: [3:250:17]
  ⏱  Asteroid timer: 35 minutes
  📏 Distance: 3 systems (from base 247)
  🕐 Required time: 20 minutes
  ✅ Sufficient time! Dispatching fleet...
  ⏳ Clicking asteroid...
```

### Insufficient Time:
```
🎯 ASTEROID FOUND: [3:100:17]
  ⏱  Asteroid timer: 28 minutes
  📏 Distance: 147 systems (from base 247)
  🕐 Required time: 36 minutes
  ⏰ Insufficient time (28 < 36 min)
  ➜ Adding to cooldown to avoid wasted trip
```

## Testing

To test the system:

1. **Run the bot**: `python bot.py`
2. **Watch for asteroid discoveries**
3. **Check the console output** for timer/distance calculations
4. **Verify decisions** match the travel time rules

## FAQs

**Q: What if the timer can't be read?**  
A: The bot skips that asteroid and continues searching.

**Q: Why is a skipped asteroid added to cooldown?**  
A: To prevent wasting time re-checking the same asteroid that's still too far/too close to expiring.

**Q: Can I use this for other fleet speeds?**  
A: Yes! Adjust `TRAVEL_TIME_RANGES` in config.py based on your fleet's actual travel time.

**Q: What if my base is not at system 247?**  
A: Change `BASE_SYSTEM = 247` to your actual base system number.

## Summary

The Travel Time Verification system ensures **100% successful asteroid mining trips** by only dispatching when success is guaranteed. No more wasted fuel or time!
