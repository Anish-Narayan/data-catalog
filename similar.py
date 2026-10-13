"""
similarity.py
Component A: SQL Analysis, Lineage Extraction, and Multi-Table Column Similarity Engine
"""

import sys
import re
import json
from pathlib import Path
from difflib import SequenceMatcher
from itertools import combinations
from typing import Dict, List, Tuple, Set, Any, Optional

import pandas as pd
import sqlglot
from sqlglot import exp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DIALECT = "databricks"
HEADER_PATTERN = re.compile(r"^\s*--([A-Za-z0-9_]+)\s*$", re.MULTILINE)
PLACEHOLDER_PATTERN = re.compile(r"(\$[\(\{][a-zA-Z0-9_\.\-]+[\)\}]|\$[a-zA-Z0-9_]+)")

# Healthcare and standard data warehouse semantic synonyms
SYNONYM_GROUPS = {
    "member": "member", "beneficiary": "member", "ben": "member", "mbr": "member",
    "patient": "member", "subscriber": "member", "insured": "member",
    "service": "service", "svc": "service", "treatment": "service", "dos": "service",
    "amount": "amount", "amt": "amount", "paid": "amount", "allowed": "amount",
    "charge": "amount", "cost": "amount", "claim": "claim", "clm": "claim",
    "provider": "provider", "prov": "provider", "doctor": "provider", "npi": "provider",
    "date": "date", "dt": "date", "id": "id", "num": "id", "nbr": "id", "no": "id",
    "identifier": "id", "code": "code", "cd": "code"
}


class SchemaSanitizer:
    """Safely sanitizes $(schema) placeholders before AST parsing."""
    def __init__(self):
        self.raw_to_temp: Dict[str, str] = {}
        self.temp_to_raw: Dict[str, str] = {}
        self._counter = 0

    def replace(self, sql_text: str) -> str:
        def _sub(match: re.Match) -> str:
            raw = match.group(0)
            if raw not in self.raw_to_temp:
                self._counter += 1
                temp_id = f"temp_sch_{self._counter}"
                self.raw_to_temp[raw] = temp_id
                self.temp_to_raw[temp_id] = raw
            return self.raw_to_temp[raw]
        return PLACEHOLDER_PATTERN.sub(_sub, sql_text)


def split_concepts(text: str) -> List[Dict[str, str]]:
    matches = list(HEADER_PATTERN.finditer(text))
    if not matches:
        return [{"name": "root_concept", "sql": text.strip()}]
    concepts = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        concepts.append({
            "name": match.group(1),
            "sql": text[match.end():end].strip()
        })
    return concepts


def parse_safely(clean_sql: str) -> List[exp.Expression]:
    """Lenient parser tolerant of missing commas in projection lists."""
    statements = []
    # Quick fix for missing commas before aggregate functions like COUNT(*)
    normalized_sql = re.sub(r"([a-zA-Z0-9_]+)\s+(COUNT\s*\()", r"\1, \2", clean_sql, flags=re.IGNORECASE)
    try:
        parsed = sqlglot.parse(normalized_sql, read=DIALECT, error_level=sqlglot.ErrorLevel.IGNORE)
        statements = [s for s in parsed if s is not None]
    except Exception:
        for chunk in normalized_sql.split(";"):
            chunk_s = chunk.strip()
            if chunk_s:
                try:
                    stmt = sqlglot.parse_one(chunk_s, read=DIALECT, error_level=sqlglot.ErrorLevel.IGNORE)
                    if stmt:
                        statements.append(stmt)
                except Exception:
                    pass
    return statements


def analyze_concept(concept: Dict[str, str]) -> Dict[str, Any]:
    statements = parse_safely(concept["sql"])
    created_tables: Set[str] = set()
    ctes: Set[str] = set()
    external_tables: Set[str] = set()
    table_columns: Dict[str, Set[str]] = {}
    joins: List[str] = []
    operations: Set[str] = set()
    fingerprints: List[str] = []

    for stmt in statements:
        if isinstance(stmt, exp.Create):
            t_node = stmt.this
            if isinstance(t_node, exp.Schema):
                t_node = t_node.this
            if isinstance(t_node, exp.Table):
                created_tables.add(t_node.name.lower())
                operations.add("CREATE")

        stmt_ctes = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE) if c.alias_or_name}
        ctes.update(stmt_ctes)

        alias_to_table: Dict[str, str] = {}
        for tbl in stmt.find_all(exp.Table):
            t_name = tbl.name.lower()
            alias = tbl.alias.lower() if tbl.alias else t_name
            alias_to_table[alias] = t_name

            if t_name not in stmt_ctes and t_name not in created_tables:
                full_name = ".".join(x for x in [tbl.catalog, tbl.db, tbl.name] if x).lower()
                external_tables.add(full_name if full_name else t_name)
                if t_name not in table_columns:
                    table_columns[t_name] = set()

        for j in stmt.find_all(exp.Join):
            side = j.args.get("side") or "INNER"
            joins.append(f"{side}_JOIN".upper())

        for col in stmt.find_all(exp.Column):
            col_name = col.name.lower()
            t_qualifier = col.table.lower() if col.table else None
            if t_qualifier:
                real_table = alias_to_table.get(t_qualifier, t_qualifier)
                if real_table not in stmt_ctes and real_table not in created_tables:
                    table_columns.setdefault(real_table, set()).add(col_name)
            else:
                ext_in_scope = [t for t in alias_to_table.values() if t not in stmt_ctes and t not in created_tables]
                if len(ext_in_scope) == 1:
                    table_columns.setdefault(ext_in_scope[0], set()).add(col_name)

        # Anonymize AST for structural similarity
        try:
            anon = stmt.copy()
            def _anon_node(node):
                if isinstance(node, exp.Table):
                    node.set("this", exp.to_identifier("TBL"))
                    node.set("db", None)
                    node.set("catalog", None)
                elif isinstance(node, exp.Column):
                    node.set("this", exp.to_identifier("COL"))
                    node.set("table", None)
                elif isinstance(node, exp.Literal):
                    return exp.Literal.number(1) if node.is_number else exp.Literal.string("X")
                return node
            anon = anon.transform(_anon_node)
            fingerprints.append(anon.sql(dialect=DIALECT).lower())
        except Exception:
            fingerprints.append("structure")

    return {
        "name": concept["name"],
        "external_tables": sorted(list(external_tables)),
        "table_columns": {k: sorted(list(v)) for k, v in table_columns.items() if v},
        "joins": sorted(list(set(joins))),
        "fingerprint": " ".join(fingerprints) or "empty"
    }


def canonical_tokens(col_name: str) -> Set[str]:
    """Converts a column name to canonical semantic tokens."""
    tokens = [t for t in re.split(r"[_\s]+", col_name.lower()) if t and t != "of"]
    return {SYNONYM_GROUPS.get(t, t) for t in tokens}


def match_columns_semantic(src_col: str, tgt_col: str) -> Tuple[float, str]:
    s = src_col.lower().strip()
    t = tgt_col.lower().strip()
    if s == t:
        return 1.0, "exact_match"

    s_canon = canonical_tokens(s)
    t_canon = canonical_tokens(t)

    # Full semantic set equivalence (e.g. member_id == beneficiary_id -> {member, id})
    if s_canon == t_canon and len(s_canon) > 0:
        return 0.98, "semantic_synonym_match"

    # Token overlap (Jaccard)
    intersection = len(s_canon & t_canon)
    union = len(s_canon | t_canon)
    jaccard = intersection / union if union > 0 else 0.0

    if jaccard >= 0.65:
        return round(0.85 * jaccard, 2), "semantic_overlap"

    seq_score = SequenceMatcher(None, "".join(sorted(s_canon)), "".join(sorted(t_canon))).ratio()
    if seq_score >= 0.70:
        return round(seq_score, 2), "fuzzy_token_similarity"

    return 0.0, "unmapped"


def main():
    if len(sys.argv) < 4:
        print("Usage: python similarity.py <source.sql> <target.sql> <table_mappings.xlsx> [output_mappings.xlsx]")
        return

    src_path = Path(sys.argv[1])
    tgt_path = Path(sys.argv[2])
    tbl_map_path = Path(sys.argv[3])
    out_excel = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("pod_mappings.xlsx")

    sanitizer = SchemaSanitizer()
    src_text = sanitizer.replace(src_path.read_text(encoding="utf-8-sig"))
    tgt_text = sanitizer.replace(tgt_path.read_text(encoding="utf-8-sig"))

    src_concepts = [analyze_concept(c) for c in split_concepts(src_text)]
    tgt_concepts = [analyze_concept(c) for c in split_concepts(tgt_text)]

    # Collect distinct columns per table
    src_tables_cols: Dict[str, Set[str]] = {}
    for c in src_concepts:
        for t, cols in c["table_columns"].items():
            src_tables_cols.setdefault(t.split(".")[-1], set()).update(cols)

    tgt_tables_cols: Dict[str, Set[str]] = {}
    for c in tgt_concepts:
        for t, cols in c["table_columns"].items():
            tgt_tables_cols.setdefault(t.split(".")[-1], set()).update(cols)

    df_tables = pd.read_excel(tbl_map_path)
    col_src_header = df_tables.columns[0]
    col_tgt_header = df_tables.columns[1]

    # Supports 1-to-many table relationships
    table_pairs: List[Tuple[str, str]] = []
    for _, row in df_tables.iterrows():
        s = str(row[col_src_header]).strip().lower()
        t = str(row[col_tgt_header]).strip().lower()
        if s and t and s != "nan" and t != "nan":
            table_pairs.append((s.split(".")[-1], t.split(".")[-1]))

    column_eval_records = []
    mapping_dictionary = []

    # Map columns in the context of each paired table
    for s_tbl, t_tbl in table_pairs:
        s_cols = sorted(list(src_tables_cols.get(s_tbl, [])))
        t_cols = sorted(list(tgt_tables_cols.get(t_tbl, [])))

        for s_col in s_cols:
            candidates = []
            for t_col in t_cols:
                score, method = match_columns_semantic(s_col, t_col)
                if score >= 0.60:
                    candidates.append({"target": t_col, "score": score, "method": method})

            candidates.sort(key=lambda x: x["score"], reverse=True)

            if not candidates:
                column_eval_records.append({
                    "Source_Table": s_tbl, "Target_Table": t_tbl,
                    "Source_Column": s_col, "Target_Column": None,
                    "Score": 0.0, "Method": "unmapped", "Status": "unmapped"
                })
            else:
                top = candidates[0]
                is_ambiguous = len(candidates) > 1 and (top["score"] - candidates[1]["score"] < 0.08)
                status = "ambiguous" if is_ambiguous else ("confirmed" if top["score"] >= 0.90 else "suggested")
                
                column_eval_records.append({
                    "Source_Table": s_tbl, "Target_Table": t_tbl,
                    "Source_Column": s_col, "Target_Column": top["target"],
                    "Score": top["score"], "Method": top["method"], "Status": status
                })

                if status in ["confirmed", "suggested"]:
                    mapping_dictionary.append({
                        "Source_Table": s_tbl,
                        "Source_Column": s_col,
                        "Target_Table": t_tbl,
                        "Target_Column": top["target"],
                        "Confidence": top["score"]
                    })

    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df_tables.to_excel(writer, sheet_name="Table_Mappings", index=False)
        pd.DataFrame(column_eval_records).to_excel(writer, sheet_name="Column_Evaluation", index=False)
        pd.DataFrame(mapping_dictionary).to_excel(writer, sheet_name="Mapping_Dictionary", index=False)

    print(f"Generated multi-table mapping file: {out_excel.resolve()}")
    print(f"Total contextual column mappings generated: {len(mapping_dictionary)}")


if __name__ == "__main__":
    main()