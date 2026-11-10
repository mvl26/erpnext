"""Permission-cell parser — turns a matrix cell such as "CRWS PE R1" into per-permlevel ptype sets."""

import re


class MatrixError(Exception):
	pass


PTYPE_BY_LETTER = {
	"R": "read",
	"W": "write",
	"C": "create",
	"D": "delete",
	"S": "submit",
	"X": "cancel",
	"A": "amend",
	"P": "print",
	"E": "email",
	"B": "report",
	"O": "export",
	"I": "import",
	"H": "share",
	"L": "select",
}

_LEVEL_TOKEN = re.compile(r"^([RW])([12])$")


def parse_cell(cell: str) -> dict[int, frozenset[str]]:
	"""Parse a cell. Loose letters are level 0; ``R1``/``W1``/``R2``/``W2`` target that permlevel.

	``W`` implies ``read`` at the same level. Whitespace and commas are separators.
	"""
	levels: dict[int, set[str]] = {}
	for token in re.split(r"[\s,]+", cell or ""):
		if not token:
			continue
		match = _LEVEL_TOKEN.match(token)
		if match:
			letter, level = match.group(1), int(match.group(2))
			ptypes = levels.setdefault(level, set())
			ptypes.add(PTYPE_BY_LETTER[letter])
			if letter == "W":
				ptypes.add("read")
			continue
		ptypes = levels.setdefault(0, set())
		for letter in token:
			if letter not in PTYPE_BY_LETTER:
				raise MatrixError(f"Unknown permission letter {letter!r} in cell {cell!r}")
			ptypes.add(PTYPE_BY_LETTER[letter])
			if letter == "W":
				ptypes.add("read")
	return {level: frozenset(p) for level, p in levels.items()}
