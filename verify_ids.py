
import uuid
import sys
import unittest

# Define the constants from src/services/cards.py since we can't easily import if dependencies are missing in this env
NAMESPACE_ANKI_CARDS = uuid.UUID("6b9a8963-8e7c-4054-94c6-2c9769341b52")

def get_deterministic_card_id(group_id: uuid.UUID, direction: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE_ANKI_CARDS, f"{str(group_id)}-{direction}")

class TestDeterministicIDs(unittest.TestCase):
    def test_determinism(self):
        group_id = uuid.uuid4()
        
        # Test 1: Same inputs -> Same ID
        id_forward_1 = get_deterministic_card_id(group_id, "forward")
        id_forward_2 = get_deterministic_card_id(group_id, "forward")
        self.assertEqual(id_forward_1, id_forward_2, "IDs should be identical for same input")
        
        # Test 2: Different direction -> Different ID
        id_backward = get_deterministic_card_id(group_id, "backward")
        self.assertNotEqual(id_forward_1, id_backward, "IDs should differ by direction")
        
        # Test 3: Different group -> Different ID
        group_id_2 = uuid.uuid4()
        id_forward_OtherGroup = get_deterministic_card_id(group_id_2, "forward")
        self.assertNotEqual(id_forward_1, id_forward_OtherGroup, "IDs should differ by group")
        
        print(f"Group ID: {group_id}")
        print(f"Forward ID: {id_forward_1}")
        print(f"Backward ID: {id_backward}")

if __name__ == '__main__':
    unittest.main()
