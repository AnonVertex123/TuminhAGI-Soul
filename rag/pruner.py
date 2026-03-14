class MemoryPruner:
    def decay_all(self, rag) -> dict:
        stats_before = rag.stats()
        rag.prune(dry_run=False)
        stats_after = rag.stats()
        return {"before": stats_before, "after": stats_after}

    def prune_faint(self, rag, dry_run: bool = True) -> list:
        faint_mems = [m for m in rag.memories if m.get("score", 0) <= 0]
        if not dry_run:
            rag.prune(dry_run=False)
        return faint_mems

    def consolidate_duplicates(self, rag) -> int:
        return 0
