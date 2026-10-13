"""
sql_analysis_engine.py
Component A: SQL Analysis and Mapping Engine
"""

import re
import json
import logging
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple, Optional, Any

import pandas as pd
import sqlglot
from sqlglot import exp

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Common abbreviations used in database modeling
ABBREVIATIONS = {
    "num": "number",
    "nbr": "number",
    "no": "number",
    "id": "identifier",
    "dt": "date",
    "amt": "amount",
    "desc": "description",
    "cd": "code",
    "pct": "percent",
    "cnt": "count",
    "qty": "quantity",
    "addr": "address",
    "cust": "customer",
    "mbr": "member",
    "ben": "beneficiary",
    "clm": "claim",
    "svc": "service",
    "prov": "provider",
    "tx": "transaction",
    "src": "source",
    "tgt": "target",
}


class SchemaPlaceholderHandler:
    """Detects and temporarily replaces $(schema_name) placeholders."""

    PATTERN = re.compile(r"\$\(([a-zA-Z0-9_\.]+)\)")

    def __init__(self):
        self.placeholder_to_temp: Dict[str, str] = {}
        self.temp_to_placeholder: Dict[str, str] = {}
        self._counter = 0

    def register_and_replace(self, sql_text: str) -> str:
        def _replace_match(match: re.Match) -> str:
            raw_placeholder = match.group(0)  # e.g., "$(gold.schema)"
            if raw_placeholder not in self.placeholder_to_temp:
                self._counter += 1
                temp_id = f"temp_sch_{self._counter}"
                self.placeholder_to_temp[raw_placeholder] = temp_id
                self.temp_to_placeholder[temp_id] = raw_placeholder
            return self.placeholder_to_temp[raw_placeholder]

        return self.PATTERN.sub(_replace_match, sql_text)

    def restore(self, sql_text: str) -> str:
        restored = sql_text
        for temp_id, raw_placeholder in self.temp_to_placeholder.items():
            restored = re.sub(rf"\b{re.escape(temp_id)}\b", raw_placeholder, restored)
        return restored


class ConceptSplitter:
    """Splits SQL scripts by concept headers (e.g., --wrong_medication or --concept_name)."""

    HEADER_PATTERN = re.compile(r"^\s*--([A-Za-z0-9_]+)\s*$", re.MULTILINE)

    @classmethod
    def split(cls, text: str) -> List[Dict[str, str]]:
        matches = list(cls.HEADER_PATTERN.finditer(text))
        if not matches:
            return [{"name": "default_concept", "sql": text.strip()}]

        concepts = []
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            concepts.append({
                "name": match.group(1),
                "sql": text[match.end():end].strip()
            })
        return concepts


class SQLMetadataExtractor:
    """Parses statements using SQLGlot and tracks table, CTE, and column lineages."""

    def __init__(self, dialect: str = "databricks"):
        self.dialect = dialect

    def extract(self, concept_name: str, sql_text: str) -> Dict[str, Any]:
        statements = []
        errors = []
        try:
            statements = [s for s in sqlglot.parse(sql_text, read=self.dialect) if s is not None]
        except Exception as exc:
            errors.append(f"Parsing error: {str(exc)}")

        created_tables: Set[str] = set()
        ctes: Set[str] = set()
        external_tables: Set[str] = set()
        table_columns: Dict[str, Set[str]] = {}
        column_aliases: Dict[str, str] = {}
        joins: List[Dict[str, str]] = []
        dependencies: List[Dict[str, str]] = []
        operations: Set[str] = set()

        for stmt in statements:
            # Detect Table Creation (DDL)
            if isinstance(stmt, exp.Create):
                tbl = stmt.this
                if isinstance(tbl, exp.Schema):
                    tbl = tbl.this
                if isinstance(tbl, exp.Table):
                    t_name = tbl.name.lower()
                    created_tables.add(t_name)
                    operations.add("CREATE")

            # Collect CTEs defined within this statement
            stmt_ctes = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE) if cte.alias_or_name}
            ctes.update(stmt_ctes)

            # Map alias -> canonical table name for current scope
            alias_to_table: Dict[str, str] = {}
            for tbl in stmt.find_all(exp.Table):
                t_name = tbl.name.lower()
                alias = tbl.alias.lower() if tbl.alias else t_name
                alias_to_table[alias] = t_name

                # Filter out CTEs and internally created tables
                if t_name not in stmt_ctes and t_name not in created_tables:
                    full_name = ".".join(x for x in [tbl.catalog, tbl.db, tbl.name] if x).lower()
                    external_tables.add(full_name if full_name else t_name)
                    if t_name not in table_columns:
                        table_columns[t_name] = set()

            # Record join details
            for join_node in stmt.find_all(exp.Join):
                join_tbl = join_node.this
                join_tbl_name = join_tbl.name.lower() if isinstance(join_tbl, exp.Table) else "subquery"
                join_type = f"{join_node.args.get('side') or 'INNER'}_{join_node.kind or 'JOIN'}".upper()
                on_clause = join_node.args.get("on")
                joins.append({
                    "type": join_type,
                    "target": join_tbl_name,
                    "condition": on_clause.sql(dialect=self.dialect) if on_clause else "NONE"
                })

            # Record operations
            for node_type, label in [
                (exp.Select, "SELECT"), (exp.Insert, "INSERT"),
                (exp.Update, "UPDATE"), (exp.Delete, "DELETE"),
                (exp.Drop, "DROP"), (exp.Where, "WHERE"),
                (exp.Group, "GROUP_BY"), (exp.Order, "ORDER_BY"),
                (exp.Having, "HAVING"), (exp.Union, "UNION")
            ]:
                if any(True for _ in stmt.find_all(node_type)):
                    operations.add(label)

            # Resolve column lineages
            for col in stmt.find_all(exp.Column):
                col_name = col.name.lower()
                table_qualifier = col.table.lower() if col.table else None

                if table_qualifier:
                    target_table = alias_to_table.get(table_qualifier, table_qualifier)
                    if target_table not in stmt_ctes and target_table not in created_tables:
                        table_columns.setdefault(target_table, set()).add(col_name)
                else:
                    # Single external table in scope -> assign directly
                    scope_external = [t for t in alias_to_table.values() if t not in stmt_ctes and t not in created_tables]
                    if len(scope_external) == 1:
                        table_columns.setdefault(scope_external[0], set()).add(col_name)

            # Track column aliases in projections
            for alias_node in stmt.find_all(exp.Alias):
                alias_name = alias_node.alias.lower()
                inner_col = alias_node.find(exp.Column)
                if inner_col:
                    column_aliases[alias_name] = inner_col.name.lower()

        # Track internal dependencies
        for c_tbl in created_tables:
            for ext in external_tables:
                dependencies.append({"created_table": c_tbl, "depends_on": ext})

        return {
            "concept_name": concept_name,
            "statement_count": len(statements),
            "external_tables": sorted(list(external_tables)),
            "created_tables": sorted(list(created_tables)),
            "ctes": sorted(list(ctes)),
            "table_columns": {k: sorted(list(v)) for k, v in table_columns.items() if v},
            "column_aliases": column_aliases,
            "joins": joins,
            "dependencies": dependencies,
            "operations": sorted(list(operations)),
            "errors": errors
        }


class ColumnMatchingEngine:
    """Matches columns between paired tables using exact, normalized, and fuzzy similarity."""

    @staticmethod
    def normalize_name(name: str) -> str:
        tokens = re.split(r"[_\s]+", name.lower())
        expanded = [ABBREVIATIONS.get(t, t) for t in tokens if t]
        return "".join(expanded)

    @classmethod
    def calculate_similarity(cls, col_src: str, col_tgt: str) -> Tuple[float, str]:
        s_clean = col_src.lower().strip()
        t_clean = col_tgt.lower().strip()

        # 1. Exact match
        if s_clean == t_clean:
            return 1.0, "exact_match"

        # 2. Normalized abbreviation match
        norm_s = cls.normalize_name(s_clean)
        norm_t = cls.normalize_name(t_clean)
        if norm_s == norm_t:
            return 0.98, "normalized_expansion_match"

        # 3. Substring match
        if norm_s in norm_t or norm_t in norm_s:
            ratio = len(min(norm_s, norm_t, key=len)) / len(max(norm_s, norm_t, key=len))
            if ratio >= 0.7:
                return round(0.85 * ratio, 3), "token_containment"

        # 4. Fuzzy SequenceMatcher similarity
        seq_score = SequenceMatcher(None, norm_s, norm_t).ratio()
        if seq_score >= 0.75:
            return round(seq_score, 3), "fuzzy_string_similarity"

        return round(seq_score, 3), "low_confidence"

    @classmethod
    def match_columns(cls, source_columns: List[str], target_columns: List[str]) -> List[Dict[str, Any]]:
        results = []
        assigned_targets = set()

        for src_col in source_columns:
            candidates = []
            for tgt_col in target_columns:
                score, method = cls.calculate_similarity(src_col, tgt_col)
                candidates.append({
                    "target_col": tgt_col,
                    "score": score,
                    "method": method
                })

            candidates.sort(key=lambda x: x["score"], reverse=True)

            if not candidates or candidates[0]["score"] < 0.60:
                results.append({
                    "source_column": src_col,
                    "target_column": None,
                    "match_method": "unmapped",
                    "similarity_score": 0.0,
                    "status": "unmapped"
                })
            else:
                top = candidates[0]
                # Ambiguity detection: check if runner-up is very close
                is_ambiguous = len(candidates) > 1 and (top["score"] - candidates[1]["score"] < 0.08) and (candidates[1]["score"] >= 0.65)
                status = "ambiguous" if is_ambiguous else ("confirmed" if top["score"] >= 0.95 else "suggested")

                results.append({
                    "source_column": src_col,
                    "target_column": top["target_col"],
                    "match_method": top["method"],
                    "similarity_score": top["score"],
                    "status": status,
                    "alternate_candidate": candidates[1]["target_col"] if is_ambiguous else None
                })
                assigned_targets.add(top["target_col"])

        return results


class AnalysisPipeline:
    """Executes the analysis, applies known table mappings, and generates Excel reports."""

    def __init__(self, source_sql_path: Path, target_sql_path: Path, table_mapping_excel: Path, dialect: str = "databricks"):
        self.source_sql_path = Path(source_sql_path)
        self.target_sql_path = Path(target_sql_path)
        self.table_mapping_excel = Path(table_mapping_excel)
        self.dialect = dialect
        self.schema_handler = SchemaPlaceholderHandler()
        self.extractor = SQLMetadataExtractor(dialect=self.dialect)

    def run(self, output_excel: Path, output_json: Path) -> Dict[str, Any]:
        logging.info("Reading source and target SQL scripts...")
        src_raw = self.source_sql_path.read_text(encoding="utf-8-sig")
        tgt_raw = self.target_sql_path.read_text(encoding="utf-8-sig")

        # Replace $(schema) placeholders consistently
        src_clean = self.schema_handler.register_and_replace(src_raw)
        tgt_clean = self.schema_handler.register_and_replace(tgt_raw)

        # Split concepts
        src_concepts = ConceptSplitter.split(src_clean)
        tgt_concepts = ConceptSplitter.split(tgt_clean)

        src_meta = [self.extractor.extract(c["name"], c["sql"]) for c in src_concepts]
        tgt_meta = [self.extractor.extract(c["name"], c["sql"]) for c in tgt_concepts]

        # Consolidate external tables and columns across all concepts per pod
        src_table_cols: Dict[str, Set[str]] = {}
        for m in src_meta:
            for tbl, cols in m["table_columns"].items():
                src_table_cols.setdefault(tbl.split(".")[-1], set()).update(cols)

        tgt_table_cols: Dict[str, Set[str]] = {}
        for m in tgt_meta:
            for tbl, cols in m["table_columns"].items():
                tgt_table_cols.setdefault(tbl.split(".")[-1], set()).update(cols)

        # Load known table mappings from Excel
        tbl_df = pd.read_excel(self.table_mapping_excel)
        source_col_header = tbl_df.columns[0]
        target_col_header = tbl_df.columns[1]

        confirmed_table_pairs: List[Tuple[str, str]] = []
        for _, row in tbl_df.iterrows():
            s_val = str(row[source_col_header]).strip().lower()
            t_val = str(row[target_col_header]).strip().lower()
            if s_val and t_val and s_val != "nan" and t_val != "nan":
                # Strip schema qualifiers for base-table matching
                clean_s = s_val.split(".")[-1]
                clean_t = t_val.split(".")[-1]
                confirmed_table_pairs.append((clean_s, clean_t))

        # Perform Column Matching for each paired table
        column_reports = []
        confirmed_mappings_for_export = []

        for s_tbl, t_tbl in confirmed_table_pairs:
            s_cols = sorted(list(src_table_cols.get(s_tbl, [])))
            t_cols = sorted(list(tgt_table_cols.get(t_tbl, [])))

            matches = ColumnMatchingEngine.match_columns(s_cols, t_cols)
            for m in matches:
                rec = {
                    "source_table": s_tbl,
                    "target_table": t_tbl,
                    "source_column": m["source_column"],
                    "target_column": m["target_column"],
                    "match_method": m["match_method"],
                    "similarity_score": m["similarity_score"],
                    "status": m["status"]
                }
                column_reports.append(rec)
                if m["status"] in ["confirmed", "suggested"] and m["target_column"]:
                    confirmed_mappings_for_export.append({
                        "Source_Pod_Table": s_tbl,
                        "Source_Pod_Column": m["source_column"],
                        "Target_Pod_Table": t_tbl,
                        "Target_Pod_Column": m["target_column"],
                        "Confidence": m["similarity_score"],
                        "Status": m["status"]
                    })

        # Generate Reusable Mapping Excel Workbook
        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            # Sheet 1: Table Mappings
            tbl_df.to_excel(writer, sheet_name="Table_Mappings", index=False)
            # Sheet 2: Column Mappings Report
            pd.DataFrame(column_reports).to_excel(writer, sheet_name="Column_Evaluation", index=False)
            # Sheet 3: Confirmed Mapping rules (Consumed by Component B Converter)
            pd.DataFrame(confirmed_mappings_for_export).to_excel(writer, sheet_name="Mapping_Dictionary", index=False)

        summary_json = {
            "schema_placeholders": self.schema_handler.placeholder_to_temp,
            "source_metadata": src_meta,
            "target_metadata": tgt_meta,
            "total_tables_mapped": len(confirmed_table_pairs),
            "total_columns_evaluated": len(column_reports),
            "confirmed_mappings_count": len(confirmed_mappings_for_export)
        }
        output_json.write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
        logging.info(f"Analysis complete. Generated {output_excel} and {output_json}")
        return summary_json


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Component A: SQL Analysis and Mapping Engine")
    parser.add_argument("--source-sql", required=True, help="Path to Source Pod SQL file")
    parser.add_argument("--target-sql", required=True, help="Path to Target Pod SQL file")
    parser.add_argument("--table-map", required=True, help="Path to initial Excel table mapping")
    parser.add_argument("--out-excel", default="pod_cross_mappings.xlsx", help="Output Excel workbook")
    parser.add_argument("--out-json", default="pod_metadata.json", help="Output metadata JSON")
    args = parser.parse_args()

    pipeline = AnalysisPipeline(args.source_sql, args.target_sql, args.table_map)
    pipeline.run(Path(args.out_excel), Path(args.out_json))