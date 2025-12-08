import sys
from unittest.mock import MagicMock

# Mock dependencies before importing src
sys.modules["numpy"] = MagicMock()
sys.modules["pydub"] = MagicMock()
sys.modules["ffmpeg"] = MagicMock()
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.extras"] = MagicMock()
sys.modules["jinja2"] = MagicMock()

import unittest
from unittest.mock import patch
import uuid
from datetime import datetime

# Import src after mocking
from src.services import cards as card_service

class TestPagination(unittest.TestCase):
    @patch('src.services.cards.get_connection')
    def test_pagination(self, mock_get_conn):
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock data
        owner_id = uuid.uuid4()
        deck_id = uuid.uuid4()
        deck = {
            "id": str(deck_id),
            "target_language": "Spanish",
            "pk": 1,
            "field_schema": [],
            "prompt_templates": {}
        }
        
        # Scenario: 10 groups total, requesting page 1, lim 2
        
        # 1. Count query
        mock_cursor.fetchone.side_effect = [
            {"total": 10}, # First call: count
        ]
        
        # 2. Groups query
        group1 = uuid.uuid4()
        group2 = uuid.uuid4()
        
        mock_cursor.fetchall.side_effect = [
            # Groups result
            [
                {"card_group_id": str(group1), "max_updated": datetime.now()},
                {"card_group_id": str(group2), "max_updated": datetime.now()}
            ],
            # Card details result
            [
                {
                    "card_group_id": str(group1),
                    "id": str(uuid.uuid4()),
                    "direction": "forward",
                    "payload": {"front": "hola", "back": "hello"},
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "has_front_audio": False,
                    "has_back_audio": False,
                    "deck_id": str(deck_id)
                },
                 {
                    "card_group_id": str(group2),
                    "id": str(uuid.uuid4()),
                    "direction": "backward",
                    "payload": {"front": "mundo", "back": "world"},
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "has_front_audio": False,
                    "has_back_audio": False,
                    "deck_id": str(deck_id)
                }
            ]
        ]
        
        # Execute
        # We need to ensure _render_card doesn't crash since jinja2 is mocked
        # Mock template render
        sys.modules["jinja2"].Template.return_value.render.return_value = "Mocked Render"
        
        result = card_service.list_cards_for_deck_paginated(
            owner_id, deck, "English", page=1, limit=2
        )
        
        # Verify
        self.assertEqual(result["total"], 10)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["limit"], 2)
        self.assertEqual(result["pages"], 5)
        self.assertEqual(len(result["cards"]), 2)
        self.assertEqual(result["cards"][0]["group_id"], str(group1))
        
        print("Verification Successful!")

if __name__ == '__main__':
    unittest.main()
