from src.api.generate import _build_constraint_cells


cells = _build_constraint_cells(
    ["C1", "C2"],
    {"Topic": ["politics", "work"]},
    {
        "politics": {"name": "politics", "category": "Topic"},
        "work": {"name": "work", "category": "Topic"},
    },
)
assert [(difficulty, tags[0]["name"]) for difficulty, tags in cells] == [
    ("C1", "politics"), ("C1", "work"), ("C2", "politics"), ("C2", "work")
]
print("Generation grid verification successful!")
