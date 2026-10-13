"""
similarity.py
Component A: SQL Analysis, Lineage Extraction, and Column Similarity Engine
"""

import sys
import re
import json
from pathlib import Path
from difflib import SequenceMatcher
from itertools import combinations
from typing import Dict, List, Tuple, Set, Any

import pandas as pd
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DIALECT = "databricks"
SIMILARITY_THRESHOLD = 0.65

# Regex to capture concepts (--concept_name)
HEADER_PATTERN = re.compile(r"^\s*--([A-Za-z0-9_]+)\s*$", re.MULTILINE)

# Placeholder regex handling $(schema.name), ${schema-name}, $var
PLACEHOLDER_PATTERN = re.compile(r"(\$[\(\{][a-zA-Z0-9_\.\-]+[\)\}]|\$[a-zA-Z0-9_]+)")

ABBREVIATIONS = {
    "num": "number", "nbr": "number", "no": "number", "id": "identifier",
    "dt": "date", "amt": "amount", "desc": "description", "cd": "code",
    "pct": "percent", "cnt": "count", "qty": "quantity", "addr": "address",
    "cust": "customer", "mbr": "member", "ben": "beneficiary", "clm": "claim",
    "svc": "service", "prov": "provider", "tx": "transaction", "src": "source",
    "tgt": "target"
}


class SchemaSanitizer:
    """Pre-processes $(placeholder) tokens into valid SQL identifiers."""
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

    def restore(self, sql_text: str) -> str:
        res = sql_text
        for temp_id, raw in self.temp_to_raw.items():
            res = re.sub(rf"\b{re.escape(temp_id)}\b", raw, res)
        return res


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


def parse_statements_safely(clean_sql: str) -> Tuple[List[exp.Expression], List[str]]:
    """Tolerant SQLGlot parser that prevents unexpected token crashes."""
    statements = []
    errors = []
    try:
        parsed = sqlglot.parse(clean_sql, read=DIALECT, error_level=sqlglot.ErrorLevel.IGNORE)
        statements = [s for s in parsed if s is not None]
    except Exception:
        # Fallback: split by semicolon
        for chunk in clean_sql.split(";"):
            chunk_clean = chunk.strip()
            if not chunk_clean:
                continue
            try:
                stmt = sqlglot.parse_one(chunk_clean, read=DIALECT, error_level=sqlglot.ErrorLevel.IGNORE)
                if stmt:
                    statements.append(stmt)
            except Exception as e:
                errors.append(f"Statement warning: {str(e)[:80]}")
    return statements, errors


def analyze_concept(concept: Dict[str, str]) -> Dict[str, Any]:
    statements, errors = parse_statements_safely(concept["sql"])

    created_tables: Set[str] = set()
    ctes: Set[str] = set()
    external_tables: Set[str] = set()
    table_columns: Dict[str, Set[str]] = {}
    joins: List[str] = []
    operations: Set[str] = set()
    fingerprints: List[str] = []

    for stmt in statements:
        # Identify table creations (DDL)
        if isinstance(stmt, exp.Create):
            t_node = stmt.this
            if isinstance(t_node, exp.Schema):
                t_node = t_node.this
            if isinstance(t_node, exp.Table):
                created_tables.add(t_node.name.lower())
                operations.add("CREATE")

        # Track CTEs
        stmt_ctes = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE) if c.alias_or_name}
        ctes.update(stmt_ctes)

        # Build alias -> table scope
        alias_to_table: Dict[str, str] = {}
        for tbl in stmt.find_all(exp.Table):
            t_name = tbl.name.lower()
            alias = tbl.alias.lower() if tbl.alias else t_name
            alias_to_table[alias] = t_name

            # Exclude CTEs and internally created tables
            if t_name not in stmt_ctes and t_name not in created_tables:
                full_name = ".".join(x for x in [tbl.catalog, tbl.db, tbl.name] if x).lower()
                external_tables.add(full_name if full_name else t_name)
                if t_name not in table_columns:
                    table_columns[t_name] = set()

        # Track joins
        for j in stmt.find_all(exp.Join):
            side = j.args.get("side") or "INNER"
            joins.append(f"{side}_JOIN".upper())

        # Track operations
        for node_type, label in [
            (exp.Select, "SELECT"), (exp.Insert, "INSERT"),
            (exp.Update, "UPDATE"), (exp.Delete, "DELETE"),
            (exp.Drop, "DROP"), (exp.Where, "WHERE"),
            (exp.Group, "GROUP_BY"), (exp.Order, "ORDER_BY"),
            (exp.Having, "HAVING"), (exp.Union, "UNION")
        ]:
            if any(True for _ in stmt.find_all(node_type)):
                operations.add(label)

        # Resolve column lineage
        for col in stmt.find_all(exp.Column):
            col_name = col.name.lower()
            t_qualifier = col.table.lower() if col.table else None

            if t_qualifier:
                real_table = alias_to_table.get(t_qualifier, t_qualifier)
                if real_table not in stmt_ctes and real_table not in created_tables:
                    table_columns.setdefault(real_table, set()).add(col_name)
            else:
                # Single external table in scope
                ext_in_scope = [t for t in alias_to_table.values() if t not in stmt_ctes and t not in created_tables]
                if len(ext_in_scope) == 1:
                    table_columns.setdefault(ext_in_scope[0], set()).add(col_name)

        # Safe AST anonymization (avoids invalid expression crash on literals)
        try:
            anonymized = stmt.copy()

            def _anon(node):
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

            anonymized = anonymized.transform(_anon)
            fingerprints.append(anonymized.sql(dialect=DIALECT).lower())
        except Exception:
            fingerprints.append(" ".join(operations).lower())

    return {
        "name": concept["name"],
        "statement_count": len(statements),
        "external_tables": sorted(list(external_tables)),
        "created_tables": sorted(list(created_tables)),
        "ctes": sorted(list(ctes)),
        "table_columns": {k: sorted(list(v)) for k, v in table_columns.items() if v},
        "joins": sorted(list(set(joins))),
        "operations": sorted(list(operations)),
        "fingerprint": " ".join(fingerprints) or "empty",
        "parse_errors": errors
    }


def normalize_token(name: str) -> str:
    tokens = re.split(r"[_\s]+", name.lower())
    expanded = [ABBREVIATIONS.get(t, t) for t in tokens if t]
    return "".join(expanded)


def match_columns_heuristic(src_col: str, tgt_col: str) -> Tuple[float, str]:
    s = src_col.lower().strip()
    t = tgt_col.lower().strip()
    if s == t:
        return 1.0, "exact_match"
    ns = normalize_token(s)
    nt = normalize_token(t)
    if ns == nt:
        return 0.98, "normalized_expansion"
    if ns in nt or nt in ns:
        ratio = len(min(ns, nt, key=len)) / len(max(ns, nt, key=len))
        if ratio >= 0.7:
            return round(0.85 * ratio, 2), "token_containment"
    score = SequenceMatcher(None, ns, nt).ratio()
    if score >= 0.75:
        return round(score, 2), "fuzzy_similarity"
    return round(score, 2), "low_confidence"


def evaluate_table_columns(source_columns: List[str], target_columns: List[str]) -> List[Dict[str, Any]]:
    results = []
    for s_col in source_columns:
        candidates = []
        for t_col in target_columns:
            score, method = match_columns_heuristic(s_col, t_col)
            candidates.append({"target": t_col, "score": score, "method": method})
        candidates.sort(key=lambda x: x["score"], reverse=True)

        if not candidates or candidates[0]["score"] < 0.60:
            results.append({
                "source_col": s_col, "target_col": None,
                "score": 0.0, "method": "unmapped", "status": "unmapped"
            })
        else:
            top = candidates[0]
            is_ambiguous = len(candidates) > 1 and (top["score"] - candidates[1]["score"] < 0.08) and (candidates[1]["score"] >= 0.65)
            status = "ambiguous" if is_ambiguous else ("confirmed" if top["score"] >= 0.95 else "suggested")
            results.append({
                "source_col": s_col, "target_col": top["target"],
                "score": top["score"], "method": top["method"], "status": status
            })
    return results


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

    # Concept Structural Similarity (TF-IDF)
    all_concepts = src_concepts + tgt_concepts
    docs = [f"{c['fingerprint']} {' '.join(c['joins'])} {' '.join(c['operations'])}" for c in all_concepts]
    matrix = TfidfVectorizer(ngram_range=(1, 3)).fit_transform(docs)
    sim_matrix = cosine_similarity(matrix)

    print(f"\nConcepts Analyzed: Source={len(src_concepts)}, Target={len(tgt_concepts)}")
    for i, j in combinations(range(len(all_concepts)), 2):
        score = round(float(sim_matrix[i, j]) * 100, 2)
        if score >= 40.0:
            print(f"  Similarity: {all_concepts[i]['name']} <-> {all_concepts[j]['name']} = {score}%")

    # Consolidate external tables & columns
    src_tables_cols: Dict[str, Set[str]] = {}
    for c in src_concepts:
        for t, cols in c["table_columns"].items():
            src_tables_cols.setdefault(t.split(".")[-1], set()).update(cols)

    tgt_tables_cols: Dict[str, Set[str]] = {}
    for c in tgt_concepts:
        for t, cols in c["table_columns"].items():
            tgt_tables_cols.setdefault(t.split(".")[-1], set()).update(cols)

    # Read Known Table Mappings from Excel
    df_tables = pd.read_excel(tbl_map_path)
    col_src_header = df_tables.columns[0]
    col_tgt_header = df_tables.columns[1]

    confirmed_pairs: List[Tuple[str, str]] = []
    for _, row in df_tables.iterrows():
        s = str(row[col_src_header]).strip().lower()
        t = str(row[col_tgt_header]).strip().lower()
        if s and t and s != "nan" and t != "nan":
            confirmed_pairs.append((s.split(".")[-1], t.split(".")[-1]))

    # Generate Column Mappings
    column_eval_records = []
    mapping_dictionary = []

    for s_tbl, t_tbl in confirmed_pairs:
        s_cols = sorted(list(src_tables_cols.get(s_tbl, [])))
        t_cols = sorted(list(tgt_tables_cols.get(t_tbl, [])))
        evals = evaluate_table_columns(s_cols, t_cols)

        for ev in evals:
            column_eval_records.append({
                "Source_Table": s_tbl,
                "Target_Table": t_tbl,
                "Source_Column": ev["source_col"],
                "Target_Column": ev["target_col"],
                "Score": ev["score"],
                "Method": ev["method"],
                "Status": ev["status"]
            })
            if ev["status"] in ["confirmed", "suggested"] and ev["target_col"]:
                mapping_dictionary.append({
                    "Source_Table": s_tbl,
                    "Source_Column": ev["source_col"],
                    "Target_Table": t_tbl,
                    "Target_Column": ev["target_col"],
                    "Confidence": ev["score"]
                })

    # Save Multi-sheet Excel Mapping File
    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df_tables.to_excel(writer, sheet_name="Table_Mappings", index=False)
        pd.DataFrame(column_eval_records).to_excel(writer, sheet_name="Column_Evaluation", index=False)
        pd.DataFrame(mapping_dictionary).to_excel(writer, sheet_name="Mapping_Dictionary", index=False)

    print(f"\nCreated mapping file: {out_excel.resolve()}")
    print(f"Total tables mapped: {len(confirmed_pairs)}")
    print(f"Total columns matched for dictionary: {len(mapping_dictionary)}")


if __name__ == "__main__":
    main()