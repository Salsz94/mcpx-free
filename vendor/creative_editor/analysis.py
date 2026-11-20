# Extracted from Creative Editor, commit 1a5879173c59b736ddd9279b65e77e28037fa671.
def analyze(items, limit=10, tc=str):
    """Pure timeline analysis: gaps, overlaps, transitions, reused source clips."""
    tracks, gaps, overlaps, used, transitions = {}, [], [], {}, 0
    for it in items:
        if it.get("type") == "transition":
            transitions += 1
            continue
        tracks.setdefault((it["track_type"], it["track"]), []).append(it)
        if it["track_type"] == "video" and it.get("type") != "generator":
            used.setdefault(it["name"], []).append(it["start"])
    for (kind, track), row in sorted(tracks.items()):
        row.sort(key=lambda x: x["start"])
        for a, b in zip(row, row[1:]):
            where = f"{'V' if kind == 'video' else 'A'}{track}"
            if b["start"] > a["end"]:
                gaps.append({"track": where, "at": tc(a["end"]), "frames": b["start"] - a["end"]})
            elif b["start"] < a["end"]:
                overlaps.append({"track": where, "at": tc(b["start"]), "frames": a["end"] - b["start"],
                                 "items": [a["id"], b["id"]]})
    reused = {n: [tc(s) for s in starts] for n, starts in sorted(used.items()) if len(starts) > 1}
    return {"items": len(items) - transitions, "transitions": transitions,
            "tracks": {f"{'V' if k == 'video' else 'A'}{t}": len(r) for (k, t), r in sorted(tracks.items())},
            "gaps": {"count": len(gaps), "first": gaps[:limit]},
            "overlaps": {"count": len(overlaps), "first": overlaps[:limit],
                         "note": "Same-track audio overlaps are usually crossfades." if overlaps else None},
            "reused_clips": reused}
