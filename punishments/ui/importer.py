from __future__ import annotations

import re
import csv
import io

import discord
from discord.ui import Modal, TextInput
from typing import List, Tuple

from ..constants import MODAL_TIMEOUT, WEIGHT_MIN, WEIGHT_MAX


#Must be: [123] - then at least 1 non-whitespace char after
#This way we discard any of the "Their Punishment List - Page 5/5" lines,
#Or timestamps, or any of the other nonsense that Discord throws at us

LINE_RE = re.compile(r"^\s*\[(\d+)\]\s*-\s*(\S.*)\s*$")

def _clamp_weight(weight: int, default: int = 3) -> int:
    return weight if WEIGHT_MIN <= weight <= WEIGHT_MAX else default

def _looks_like_csv_header(line: str) -> bool:
    return line.strip().lower().replace(" ", "") == "id,desc,weight"

class ImportPunishmentsModal(Modal, title="Import Punishments"):
    def __init__(self, *, cog, target: discord.Member):
        super().__init__(timeout=MODAL_TIMEOUT)
        self.cog = cog
        self.target = target

        self.raw = TextInput(label="Paste your old list, or id,desc,weight csv", style=discord.TextStyle.paragraph, max_length=4000, required=True, placeholder="[1234] - Old Punishment\nOr id,desc,weight\n1,Pie,3")

        self.add_item(self.raw)

    def _parse_csv(self, text: str) -> Tuple[List[Tuple[str, int]], int]:
        skipped = 0
        items: List[Tuple[str, int]] = []

        file = io.StringIO(text)
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            return [], 1

        fields = [x.strip().lower() for x in reader.fieldnames]
        if fields != ["id", "desc", "weight"]:
            return [], 1

        for row in reader:
            desc = (row.get("desc") or "").strip()
            if not desc:
                skipped += 1
                continue

            try:
                weight = int((row.get("weight") or "").strip())
            except ValueError:
                weight = 3

            items.append((desc, _clamp_weight(weight)))

        return items, skipped
    
    def _parse_legacy(self, text: str) -> Tuple[List[Tuple[str, int]], int]:
        skipped = 0
        items: List[Tuple[str, int]] = []

        for raw_line in text.splitlines():
            line = (raw_line or "").strip()
            if not line:
                skipped += 1
                continue

            match = LINE_RE.match(line)
            if not match:
                skipped += 1
                continue

            desc = match.group(2).strip()
            if not desc:
                skipped += 1
                continue

            items.append((desc, 3))

        return items, skipped

    async def on_submit(self, interaction: discord.Interaction):

        raw_text = self.raw.value or ""
        first_nonempty = ""

        for line in raw_text.splitlines():
            if line.strip():
                first_nonempty = line
                break

        if not first_nonempty:
            return await interaction.response.send_message("No valid input was provided.", ephemeral=True)

        if _looks_like_csv_header(first_nonempty):
            items, skipped = self._parse_csv(raw_text)
            mode = "CSV"
        else:
            items, skipped = self._parse_legacy(raw_text)
            mode = "legacy list"

        if not items:
            return await interaction.response.send_message(f"No valid punishments were found using the **{mode}** format.", ephemeral=True)

        imported_ids = await self.cog._bulk_add_punishments_with_weights(self.target, items=items)

        used_weights = sorted({weight for _, weight in items})

        weight_note = (
            f"Weight used: **{used_weights[0]}**"
            if len(used_weights) == 1
            else f"Weights used: **{', '.join(map(str, used_weights))}**"
        )

        await interaction.response.send_message(f"Imported **{len(imported_ids)}** punishments ({mode}).\n"
            f"Skipped **{skipped}** invalid lines.\n"
            f"{weight_note}\n"
            f"New IDs: **#{imported_ids[0]} → #{imported_ids[-1]}**", ephemeral=True)
