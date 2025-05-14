from datetime import datetime
from typing import Optional, Dict, List
from firebase_admin import firestore
from dataclasses import dataclass

@dataclass
class MoodEntry:
    user_id: str
    date: str  # YYYY-MM-DD format
    mood: str
    note: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict) -> 'MoodEntry':
        return MoodEntry(
            user_id=data.get('user_id'),
            date=data.get('date'),
            mood=data.get('mood'),
            note=data.get('note')
        )

    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'date': self.date,
            'mood': self.mood,
            'note': self.note
        }

class MoodTracker:
    def __init__(self, db: Optional[firestore.Client] = None):
        self.db = db
        self.in_memory_storage = {}  # Fallback storage when db is None
        if db is not None:
            self.collection = self.db.collection('mood_entries')
        else:
            print("Using in-memory storage for mood tracking")

    def add_mood_entry(self, entry: MoodEntry) -> str:
        """
        Add a new mood entry to Firestore.
        Returns the document ID of the created entry.
        """
        if self.db is not None:
            doc_ref = self.collection.document()
            doc_ref.set(entry.to_dict())
            return doc_ref.id
        else:
            # Use in-memory storage
            entry_id = str(len(self.in_memory_storage) + 1)
            self.in_memory_storage[entry_id] = entry.to_dict()
            return entry_id

    def get_mood_entry(self, entry_id: str) -> Optional[MoodEntry]:
        """
        Retrieve a specific mood entry by its ID.
        Returns None if not found.
        """
        if self.db is not None:
            doc = self.collection.document(entry_id).get()
            if doc.exists:
                return MoodEntry.from_dict(doc.to_dict())
        else:
            # Use in-memory storage
            if entry_id in self.in_memory_storage:
                return MoodEntry.from_dict(self.in_memory_storage[entry_id])
        return None

    def get_user_mood_entries(self, user_id: str, start_date: str = None, end_date: str = None) -> List[MoodEntry]:
        """
        Get all mood entries for a specific user within an optional date range.
        """
        if self.db is not None:
            query = self.collection.where('user_id', '==', user_id)
            
            if start_date:
                query = query.where('date', '>=', start_date)
            if end_date:
                query = query.where('date', '<=', end_date)
            
            query = query.order_by('date', direction=firestore.Query.DESCENDING)
            
            return [MoodEntry.from_dict(doc.to_dict()) for doc in query.stream()]
        else:
            # Use in-memory storage
            entries = []
            for entry_data in self.in_memory_storage.values():
                if entry_data['user_id'] == user_id:
                    if start_date and entry_data['date'] < start_date:
                        continue
                    if end_date and entry_data['date'] > end_date:
                        continue
                    entries.append(MoodEntry.from_dict(entry_data))
            return sorted(entries, key=lambda x: x.date, reverse=True)

    def update_mood_entry(self, entry_id: str, mood: str = None, note: str = None) -> bool:
        """
        Update an existing mood entry.
        Returns True if successful, False if entry not found.
        """
        if self.db is not None:
            doc_ref = self.collection.document(entry_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            update_data = {}
            if mood is not None:
                update_data['mood'] = mood
            if note is not None:
                update_data['note'] = note
            
            if update_data:
                doc_ref.update(update_data)
        else:
            # Use in-memory storage
            if entry_id not in self.in_memory_storage:
                return False
            if mood is not None:
                self.in_memory_storage[entry_id]['mood'] = mood
            if note is not None:
                self.in_memory_storage[entry_id]['note'] = note
        return True

    def delete_mood_entry(self, entry_id: str) -> bool:
        """
        Delete a mood entry.
        Returns True if successful, False if entry not found.
        """
        if self.db is not None:
            doc_ref = self.collection.document(entry_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            doc_ref.delete()
        else:
            # Use in-memory storage
            if entry_id not in self.in_memory_storage:
                return False
            del self.in_memory_storage[entry_id]
        return True 