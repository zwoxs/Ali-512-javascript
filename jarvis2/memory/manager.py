"""JSON tabanlı kalıcı bellek yöneticisi.

Kişiler, etkileşim geçmişi ve hatırlatıcıları basit JSON dosyalarında saklar.
Harici veritabanı gerektirmez.
"""
import json
import os
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class MemoryManager:
    def __init__(self, base_dir: str = _BASE_DIR):
        self.base_dir = base_dir
        self.contacts_path = os.path.join(base_dir, "contacts.json")
        self.history_path = os.path.join(base_dir, "history.json")
        self.reminders_path = os.path.join(base_dir, "reminders.json")
        self.notes_path = os.path.join(base_dir, "notes.json")
        self.todos_path = os.path.join(base_dir, "todos.json")

    # ---------- düşük seviye yardımcılar ----------
    @staticmethod
    def _read(path: str, default):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    @staticmethod
    def _write(path: str, data) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- kişiler ----------
    def list_contacts(self) -> dict:
        """{"isim": "telefon"} sözlüğü döndürür."""
        return self._read(self.contacts_path, {})

    def add_contact(self, name: str, phone: str) -> bool:
        contacts = self.list_contacts()
        contacts[name.strip().lower()] = phone.strip()
        self._write(self.contacts_path, contacts)
        return True

    def get_contact(self, name: str):
        return self.list_contacts().get(name.strip().lower())

    def remove_contact(self, name: str) -> bool:
        contacts = self.list_contacts()
        key = name.strip().lower()
        if key in contacts:
            del contacts[key]
            self._write(self.contacts_path, contacts)
            return True
        return False

    # ---------- etkileşim geçmişi ----------
    def log_interaction(self, user_text: str, response: str) -> None:
        history = self._read(self.history_path, [])
        history.append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "user": user_text,
            "jarvis": response,
        })
        # son 500 kaydı tut
        self._write(self.history_path, history[-500:])

    def get_history(self, limit: int = 20) -> list:
        return self._read(self.history_path, [])[-limit:]

    # ---------- hatırlatıcılar ----------
    def add_reminder(self, text: str, remind_at_iso: str) -> None:
        reminders = self._read(self.reminders_path, [])
        reminders.append({"text": text, "at": remind_at_iso, "done": False})
        self._write(self.reminders_path, reminders)

    def list_reminders(self, include_done: bool = False) -> list:
        reminders = self._read(self.reminders_path, [])
        if include_done:
            return reminders
        return [r for r in reminders if not r.get("done")]

    def clear_reminders(self) -> None:
        self._write(self.reminders_path, [])

    def mark_reminder_done(self, index: int) -> bool:
        reminders = self._read(self.reminders_path, [])
        if 0 <= index < len(reminders):
            reminders[index]["done"] = True
            self._write(self.reminders_path, reminders)
            return True
        return False

    # ---------- notlar ----------
    def list_notes(self) -> list:
        return self._read(self.notes_path, [])

    def add_note(self, text: str) -> None:
        notes = self.list_notes()
        notes.append({
            "text": text,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
        self._write(self.notes_path, notes)

    def delete_note(self, index: int) -> bool:
        notes = self.list_notes()
        if 0 <= index < len(notes):
            notes.pop(index)
            self._write(self.notes_path, notes)
            return True
        return False

    # ---------- yapılacaklar (todo) ----------
    def list_todos(self) -> list:
        return self._read(self.todos_path, [])

    def add_todo(self, text: str, priority: str = "normal") -> None:
        todos = self.list_todos()
        todos.append({
            "text": text,
            "priority": priority,   # yüksek / orta / normal
            "done": False,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
        self._write(self.todos_path, todos)

    def toggle_todo(self, index: int) -> bool:
        todos = self.list_todos()
        if 0 <= index < len(todos):
            todos[index]["done"] = not todos[index].get("done", False)
            self._write(self.todos_path, todos)
            return True
        return False

    def delete_todo(self, index: int) -> bool:
        todos = self.list_todos()
        if 0 <= index < len(todos):
            todos.pop(index)
            self._write(self.todos_path, todos)
            return True
        return False
