"""
Cooldown Manager Module
Manages asteroid mining cooldowns to prevent re-mining the same asteroid
Stores SPECIFIC asteroid coordinates (galaxy:system:position) instead of ranges
"""

import json
import time
from typing import Dict


class CooldownManager:
    def __init__(self, cooldown_file: str, cooldown_hours: float):
        self.cooldown_file = cooldown_file
        self.cooldown_hours = cooldown_hours
        self.cooldowns = self.load()
    
    def load(self) -> Dict[str, float]:
        """Load cooldown data from file"""
        try:
            with open(self.cooldown_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def save(self):
        """Save cooldown data to file"""
        with open(self.cooldown_file, 'w') as f:
            json.dump(self.cooldowns, f, indent=2)
    
    def is_in_cooldown(self, galaxy: int, system: int, position: int) -> bool:
        """
        Check if a specific asteroid is in cooldown
        
        Args:
            galaxy: Galaxy number (e.g., 3)
            system: System number (e.g., 20)
            position: Position number (e.g., 17)
        
        Returns:
            True if asteroid is in cooldown, False otherwise
        """
        asteroid_key = f"{galaxy}:{system}:{position}"
        
        if asteroid_key in self.cooldowns:
            sent_time = self.cooldowns[asteroid_key]
            elapsed_hours = (time.time() - sent_time) / 3600
            
            if elapsed_hours < self.cooldown_hours:
                remaining = self.cooldown_hours - elapsed_hours
                print(f"  → Asteroid {asteroid_key} is in cooldown. {remaining:.1f}h remaining.")
                return True
            else:
                # Cooldown expired, remove it
                del self.cooldowns[asteroid_key]
                self.save()
        
        return False
    
    def add_to_cooldown(self, galaxy: int, system: int, position: int):
        """
        Add an asteroid to cooldown after fleet dispatch
        
        Args:
            galaxy: Galaxy number
            system: System number
            position: Position number
        """
        asteroid_key = f"{galaxy}:{system}:{position}"
        self.cooldowns[asteroid_key] = time.time()
        self.save()
        print(f"✓ Added {asteroid_key} to cooldown for {self.cooldown_hours}h")
    
    def cleanup_expired(self):
        """Remove all expired cooldowns"""
        current_time = time.time()
        expired_keys = []
        
        for asteroid_key, sent_time in self.cooldowns.items():
            elapsed_hours = (current_time - sent_time) / 3600
            if elapsed_hours >= self.cooldown_hours:
                expired_keys.append(asteroid_key)
        
        for key in expired_keys:
            del self.cooldowns[key]
        
        if expired_keys:
            self.save()
            print(f"✓ Cleaned up {len(expired_keys)} expired cooldown(s)")
    
    def get_active_count(self) -> int:
        """Get count of active cooldowns"""
        return len(self.cooldowns)
