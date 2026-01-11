#!/usr/bin/env python3
"""
History Manager Module
Handles saving and loading prompt history
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class PromptHistoryEntry:
    """Represents a single prompt history entry"""
    
    def __init__(self, user_input: str, generated_prompt: str, 
                 template_id: str = 'context_aware', timestamp: str = None):
        self.user_input = user_input
        self.generated_prompt = generated_prompt
        self.template_id = template_id
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'user_input': self.user_input,
            'generated_prompt': self.generated_prompt,
            'template_id': self.template_id,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PromptHistoryEntry':
        """Create from dictionary"""
        return cls(
            user_input=data.get('user_input', ''),
            generated_prompt=data.get('generated_prompt', ''),
            template_id=data.get('template_id', 'context_aware'),
            timestamp=data.get('timestamp')
        )
    
    def get_display_text(self, max_length: int = 60) -> str:
        """Get shortened text for display in list"""
        text = self.user_input.replace('\n', ' ').strip()
        if len(text) > max_length:
            text = text[:max_length] + '...'
        
        # Add timestamp
        try:
            dt = datetime.fromisoformat(self.timestamp)
            time_str = dt.strftime('%m/%d %H:%M')
        except:
            time_str = 'Unknown'
        
        return f"[{time_str}] {text}"


class HistoryManager:
    """Manages prompt history persistence"""
    
    def __init__(self, history_file: str = None):
        if history_file is None:
            # Default to user's home directory
            home = os.path.expanduser('~')
            history_dir = os.path.join(home, '.promptcraft_studio')
            os.makedirs(history_dir, exist_ok=True)
            self.history_file = os.path.join(history_dir, 'history.json')
        else:
            self.history_file = history_file
        
        self.history: List[PromptHistoryEntry] = []
        self.max_history = 100  # Keep last 100 entries
        self.load_history()
    
    def add_entry(self, user_input: str, generated_prompt: str, 
                  template_id: str = 'context_aware'):
        """Add a new history entry"""
        entry = PromptHistoryEntry(user_input, generated_prompt, template_id)
        self.history.insert(0, entry)  # Add to beginning (most recent first)
        
        # Trim history if too long
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]
        
        self.save_history()
    
    def get_history(self, limit: int = None) -> List[PromptHistoryEntry]:
        """Get history entries (most recent first)"""
        if limit:
            return self.history[:limit]
        return self.history
    
    def get_entry(self, index: int) -> Optional[PromptHistoryEntry]:
        """Get a specific history entry by index"""
        if 0 <= index < len(self.history):
            return self.history[index]
        return None
    
    def clear_history(self):
        """Clear all history"""
        self.history = []
        self.save_history()
    
    def delete_entry(self, index: int):
        """Delete a specific entry"""
        if 0 <= index < len(self.history):
            del self.history[index]
            self.save_history()
    
    def save_history(self):
        """Save history to file"""
        try:
            data = {
                'version': '1.0',
                'history': [entry.to_dict() for entry in self.history]
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def load_history(self):
        """Load history from file"""
        if not os.path.exists(self.history_file):
            return
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            history_data = data.get('history', [])
            self.history = [PromptHistoryEntry.from_dict(entry) 
                          for entry in history_data]
        except Exception as e:
            print(f"Error loading history: {e}")
            self.history = []
    
    def export_history(self, export_file: str):
        """Export history to a file"""
        try:
            data = {
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'history': [entry.to_dict() for entry in self.history]
            }
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error exporting history: {e}")
            return False
    
    def import_history(self, import_file: str, merge: bool = True):
        """Import history from a file"""
        try:
            with open(import_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            imported_entries = [PromptHistoryEntry.from_dict(entry) 
                              for entry in data.get('history', [])]
            
            if merge:
                # Merge with existing history
                self.history.extend(imported_entries)
                # Sort by timestamp (most recent first)
                self.history.sort(key=lambda x: x.timestamp, reverse=True)
                # Trim if needed
                if len(self.history) > self.max_history:
                    self.history = self.history[:self.max_history]
            else:
                # Replace existing history
                self.history = imported_entries
            
            self.save_history()
            return True
        except Exception as e:
            print(f"Error importing history: {e}")
            return False
    
    def search_history(self, query: str) -> List[PromptHistoryEntry]:
        """Search history by query string"""
        query_lower = query.lower()
        return [
            entry for entry in self.history
            if query_lower in entry.user_input.lower() or 
               query_lower in entry.generated_prompt.lower()
        ]
