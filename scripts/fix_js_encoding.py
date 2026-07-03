from pathlib import Path

p = Path(__file__).resolve().parents[1] / "static" / "js" / "app.js"
t = p.read_text(encoding="utf-8")
pairs = {
    "Â·": "·",
    "â€¦": "…",
    "â€”": "—",
    "â€œ": '"',
    "â€\x9d": '"',
    "â†’": "→",
    "â†\x90": "←",
    "â€“": "–",
}
for old, new in pairs.items():
    t = t.replace(old, new)
p.write_text(t, encoding="utf-8")
print("fixed", sum(t.count(x) for x in pairs))
