
import json
import re
import sys
from pathlib import Path
from itertools import combinations

import sqlglot
from sqlglot import exp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DIALECT = "databricks"
THRESHOLD = 0.65

# Concept headers such as --wrong_medication or --Concept123
HEADER = re.compile(r"^\s*--([A-Za-z0-9_]+)\s*$", re.MULTILINE)


def split_concepts(text):
    matches = list(HEADER.finditer(text))
    if not matches:
        raise ValueError("No concept headers found, e.g. --wrong_medication")

    concepts = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        concepts.append({
            "name": match.group(1),
            "sql": text[match.end():end].strip()
        })
    return concepts


def analyze(concept):
    # Parse statements; retain an error if a statement cannot be parsed.
    statements = []
    errors = []
    try:
        statements = [
            s for s in sqlglot.parse(concept["sql"], read=DIALECT)
            if s is not None
        ]
    except Exception as e:
        errors.append(str(e))

    tables, columns, joins, operations = [], [], [], []
    fingerprints = []

    for statement in statements:
        tables.extend(
            ".".join(x for x in [t.catalog, t.db, t.name] if x).lower()
            for t in statement.find_all(exp.Table)
        )
        columns.extend(c.name.lower() for c in statement.find_all(exp.Column))
        joins.extend(
            f"{j.args.get('side') or 'INNER'}_JOIN".upper()
            for j in statement.find_all(exp.Join)
        )

        for node_type, label in [
            (exp.Select, "SELECT"), (exp.Insert, "INSERT"),
            (exp.Update, "UPDATE"), (exp.Delete, "DELETE"),
            (exp.Create, "CREATE"), (exp.Drop, "DROP"),
            (exp.Where, "WHERE"), (exp.Group, "GROUP_BY"),
            (exp.Order, "ORDER_BY"), (exp.Having, "HAVING"),
            (exp.Union, "UNION"), (exp.CTE, "CTE"),
        ]:
            if any(True for _ in statement.find_all(node_type)):
                operations.append(label)

        # Build a fingerprint independent of table/column names and literal values.
        normalized = statement.copy()

        def anonymize(node):
            if isinstance(node, exp.Table):
                node.set("this", exp.to_identifier("TABLE_NAME"))
                node.set("db", None)
                node.set("catalog", None)
            elif isinstance(node, exp.Column):
                node.set("this", exp.to_identifier("COLUMN_NAME"))
            elif isinstance(node, exp.Literal):
                node.replace(exp.Var(this="LITERAL"))
            return node

        normalized = normalized.transform(anonymize)
        fingerprints.append(normalized.sql(dialect=DIALECT).lower())

    return {
        "name": concept["name"],
        "statement_count": len(statements),
        "tables": sorted(set(tables)),
        "columns": sorted(set(columns)),
        "joins": sorted(set(joins)),
        "operations": sorted(set(operations)),
        "fingerprint": " ".join(fingerprints),
        "parse_errors": errors,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_sql.py input.sql")
        return

    text = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    concepts = [analyze(c) for c in split_concepts(text)]

    # Similarity uses anonymized SQL structure.
    docs = [
        " ".join([
            c["fingerprint"],
            " ".join(c["joins"]),
            " ".join(c["operations"]),
        ]) or "empty"
        for c in concepts
    ]
    matrix = TfidfVectorizer(ngram_range=(1, 3)).fit_transform(docs)
    scores = cosine_similarity(matrix)

    # Connected components: concepts connected by a similarity >= threshold
    # end up in the same group.
    unseen = set(range(len(concepts)))
    groups = []
    while unseen:
        seed = unseen.pop()
        group = {seed}
        stack = [seed]
        while stack:
            i = stack.pop()
            linked = {
                j for j in unseen
                if scores[i, j] >= THRESHOLD
            }
            unseen -= linked
            group |= linked
            stack.extend(linked)
        groups.append(sorted(group))

    result = {
        "threshold": THRESHOLD,
        "groups": [
            {
                "group": i + 1,
                "concepts": [concepts[j]["name"] for j in group],
            }
            for i, group in enumerate(groups)
        ],
        "concepts": concepts,
        "similarity_pairs": [
            {
                "concept_a": concepts[i]["name"],
                "concept_b": concepts[j]["name"],
                "similarity_percent": round(float(scores[i, j]) * 100, 2),
            }
            for i, j in combinations(range(len(concepts)), 2)
        ],
    }

    Path("analysis.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )

    lines = [f"Concepts analyzed: {len(concepts)}", ""]
    for i, group in enumerate(groups, 1):
        lines.append(f"GROUP {i}")
        for j in group:
            c = concepts[j]
            lines.append(f"  {c['name']} — {c['statement_count']} statements")
            lines.append(f"    Tables: {', '.join(c['tables']) or '-'}")
            lines.append(f"    Joins: {', '.join(c['joins']) or '-'}")
            lines.append(f"    Operations: {', '.join(c['operations']) or '-'}")
            if c["parse_errors"]:
                lines.append(f"    PARSE ERROR: {'; '.join(c['parse_errors'])}")
        lines.append("")

    lines.append("SIMILARITY PAIRS")
    for pair in result["similarity_pairs"]:
        lines.append(
            f"  {pair['concept_a']} <-> {pair['concept_b']}: "
            f"{pair['similarity_percent']}%"
        )

    Path("report.txt").write_text("\n".join(lines), encoding="utf-8")
    print("Created analysis.json and report.txt")


if __name__ == "__main__":
    main()
