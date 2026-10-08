import re
import json
import sys
from pathlib import Path
from collections import Counter

import sqlglot
from sqlglot import exp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


CONCEPT_PATTERN = re.compile(
    r"(?m)^\s*----\s*(.+?)\s*$"
)


def split_concepts(sql_text):
    """
    Split a SQL file into concepts.

    Expected format:

    ---- Concept A
    SELECT ...

    ---- Concept B
    WITH ...
    """

    matches = list(CONCEPT_PATTERN.finditer(sql_text))

    if not matches:
        raise ValueError(
            "No concepts found. Expected lines like: ---- Concept Name"
        )

    concepts = []

    for i, match in enumerate(matches):
        name = match.group(1).strip()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sql_text)

        sql = sql_text[start:end].strip()

        if sql:
            concepts.append({
                "name": name,
                "sql": sql
            })

    return concepts


def remove_comments(sql):
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--.*?$", " ", sql, flags=re.M)
    return sql


def split_statements(sql):
    """
    Split SQL into statements using sqlglot where possible.
    """

    sql = remove_comments(sql)

    try:
        statements = sqlglot.parse(sql)
        return [s for s in statements if s is not None]
    except Exception:
        # Fallback for malformed SQL
        return [
            part.strip()
            for part in sql.split(";")
            if part.strip()
        ]


def get_tables(expression):
    tables = []

    for table in expression.find_all(exp.Table):
        name = table.name
        db = table.db
        catalog = table.catalog

        if catalog:
            full_name = f"{catalog}.{db}.{name}"
        elif db:
            full_name = f"{db}.{name}"
        else:
            full_name = name

        tables.append(full_name.lower())

    return sorted(set(tables))


def get_columns(expression):
    columns = []

    for column in expression.find_all(exp.Column):
        columns.append(column.name.lower())

    return sorted(set(columns))


def get_joins(expression):
    joins = []

    for join in expression.find_all(exp.Join):
        side = join.args.get("side") or "INNER"
        kind = join.args.get("kind") or ""

        joins.append(
            f"{side}_{kind}".strip("_").upper()
        )

    return sorted(joins)


def get_operations(expression):
    operations = []

    operation_types = {
        exp.Select: "SELECT",
        exp.Insert: "INSERT",
        exp.Update: "UPDATE",
        exp.Delete: "DELETE",
        exp.Group: "GROUP_BY",
        exp.Order: "ORDER_BY",
        exp.Having: "HAVING",
        exp.Where: "WHERE",
        exp.Join: "JOIN",
        exp.Union: "UNION",
        exp.Case: "CASE",
        exp.Subquery: "SUBQUERY",
    }

    for node_type, name in operation_types.items():
        if expression.find(node_type):
            operations.append(name)

    return sorted(set(operations))


def get_ctes(expression):
    ctes = []

    for cte in expression.find_all(exp.CTE):
        alias = cte.alias_or_name

        if alias:
            ctes.append(alias.lower())

    return sorted(set(ctes))


def normalize_sql(expression):
    """
    Produce a normalized SQL representation.

    Literals become placeholders so:

        status = 'PAID'

    and:

        status = 'DENIED'

    are structurally similar.
    """

    try:
        normalized = expression.sql(
            pretty=False,
            normalize=True,
            comments=False
        )

        # Replace literal values
        normalized = re.sub(
            r"'(?:''|[^'])*'",
            "<STRING>",
            normalized
        )

        normalized = re.sub(
            r"\b\d+(?:\.\d+)?\b",
            "<NUMBER>",
            normalized
        )

        normalized = re.sub(
            r"\s+",
            " ",
            normalized
        )

        return normalized.lower().strip()

    except Exception:
        return ""


def analyze_concept(concept):
    sql = concept["sql"]
    statements = split_statements(sql)

    all_tables = []
    all_columns = []
    all_joins = []
    all_operations = []
    all_ctes = []
    normalized_statements = []

    parse_errors = []

    for statement in statements:

        if isinstance(statement, str):
            parse_errors.append("Could not parse statement")
            continue

        try:
            all_tables.extend(get_tables(statement))
            all_columns.extend(get_columns(statement))
            all_joins.extend(get_joins(statement))
            all_operations.extend(get_operations(statement))
            all_ctes.extend(get_ctes(statement))

            normalized = normalize_sql(statement)

            if normalized:
                normalized_statements.append(normalized)

        except Exception as exc:
            parse_errors.append(str(exc))

    tables = sorted(set(all_tables))
    columns = sorted(set(all_columns))
    joins = sorted(set(all_joins))
    operations = sorted(set(all_operations))
    ctes = sorted(set(all_ctes))

    # Structural fingerprint.
    fingerprint_parts = [
        f"STATEMENTS:{len(statements)}",
        f"TABLES:{','.join(tables)}",
        f"COLUMNS:{','.join(columns)}",
        f"JOINS:{','.join(joins)}",
        f"OPERATIONS:{','.join(operations)}",
        f"CTES:{','.join(ctes)}",
    ]

    return {
        "name": concept["name"],
        "sql": concept["sql"],
        "statement_count": len(statements),
        "tables": tables,
        "columns": columns,
        "joins": joins,
        "operations": operations,
        "ctes": ctes,
        "normalized_sql": " ".join(normalized_statements),
        "fingerprint": " | ".join(fingerprint_parts),
        "parse_errors": parse_errors,
    }


def build_similarity_matrix(concepts):
    """
    Compare concepts based on normalized SQL structure.
    """

    documents = []

    for concept in concepts:
        # Combine normalized SQL with structural features.
        document = " ".join([
            concept["normalized_sql"],
            " ".join(concept["tables"]),
            " ".join(concept["columns"]),
            " ".join(concept["joins"]),
            " ".join(concept["operations"]),
        ])

        documents.append(document)

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 3),
        min_df=1
    )

    matrix = vectorizer.fit_transform(documents)

    return cosine_similarity(matrix)


def calculate_structural_similarity(a, b):
    """
    Additional similarity based on explicit SQL structures.
    """

    def jaccard(x, y):
        x = set(x)
        y = set(y)

        if not x and not y:
            return 1.0

        if not x or not y:
            return 0.0

        return len(x & y) / len(x | y)

    table_score = jaccard(a["tables"], b["tables"])
    column_score = jaccard(a["columns"], b["columns"])
    join_score = jaccard(a["joins"], b["joins"])
    operation_score = jaccard(a["operations"], b["operations"])

    score = (
        table_score * 0.35 +
        column_score * 0.20 +
        join_score * 0.25 +
        operation_score * 0.20
    )

    return score


def calculate_final_similarity(a, b, text_score):
    structural_score = calculate_structural_similarity(a, b)

    # SQL textual similarity gets 40%.
    # Explicit SQL structure gets 60%.
    final_score = (
        text_score * 0.40 +
        structural_score * 0.60
    )

    return round(final_score * 100, 2)


def create_groups(concepts, similarity_matrix, threshold=65):
    """
    Simple grouping algorithm.

    Concepts with similarity >= threshold
    are placed in the same group.
    """

    n = len(concepts)
    visited = set()
    groups = []

    for i in range(n):

        if i in visited:
            continue

        group = [i]
        visited.add(i)

        changed = True

        while changed:
            changed = False

            for j in range(n):

                if j in visited:
                    continue

                if any(
                    similarity_matrix[j][k] >= threshold / 100
                    for k in group
                ):
                    group.append(j)
                    visited.add(j)
                    changed = True

        groups.append(group)

    return groups


def create_report(concepts, similarity_matrix, groups):
    lines = []

    lines.append("=" * 80)
    lines.append("SQL CONCEPT SIMILARITY ANALYSIS")
    lines.append("=" * 80)
    lines.append("")

    for group_number, group in enumerate(groups, start=1):

        lines.append(f"GROUP {group_number}")
        lines.append("-" * 80)

        for index in group:
            concept = concepts[index]

            lines.append(
                f"  {index + 1}. {concept['name']}"
            )

            lines.append(
                f"     Statements : {concept['statement_count']}"
            )

            lines.append(
                f"     Tables     : {', '.join(concept['tables']) or '-'}"
            )

            lines.append(
                f"     Joins      : {', '.join(concept['joins']) or '-'}"
            )

            lines.append(
                f"     Operations : {', '.join(concept['operations']) or '-'}"
            )

            if concept["ctes"]:
                lines.append(
                    f"     CTEs       : {', '.join(concept['ctes'])}"
                )

        lines.append("")

        if len(group) > 1:
            lines.append("  Similarity:")
            lines.append("")

            for x in range(len(group)):
                for y in range(x + 1, len(group)):

                    a = group[x]
                    b = group[y]

                    score = calculate_final_similarity(
                        concepts[a],
                        concepts[b],
                        similarity_matrix[a][b]
                    )

                    lines.append(
                        f"    {concepts[a]['name']} "
                        f"<-> "
                        f"{concepts[b]['name']} : "
                        f"{score}%"
                    )

            lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)


def main():

    if len(sys.argv) < 2:
        print("Usage: python analyze_sql.py input.sql")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(f"File not found: {input_file}")
        sys.exit(1)

    sql_text = input_file.read_text(
        encoding="utf-8",
        errors="replace"
    )

    raw_concepts = split_concepts(sql_text)

    print(f"Found {len(raw_concepts)} concepts.")

    concepts = [
        analyze_concept(concept)
        for concept in raw_concepts
    ]

    similarity_matrix = build_similarity_matrix(concepts)

    groups = create_groups(
        concepts,
        similarity_matrix,
        threshold=65
    )

    report = create_report(
        concepts,
        similarity_matrix,
        groups
    )

    Path("analysis.json").write_text(
        json.dumps(
            {
                "concept_count": len(concepts),
                "groups": [
                    {
                        "group": group_number + 1,
                        "concepts": [
                            concepts[index]["name"]
                            for index in group
                        ]
                    }
                    for group_number, group in enumerate(groups)
                ],
                "concepts": concepts
            },
            indent=2
        ),
        encoding="utf-8"
    )

    Path("report.txt").write_text(
        report,
        encoding="utf-8"
    )

    print("")
    print(report)

    print("")
    print("Generated:")
    print("  analysis.json")
    print("  report.txt")


if __name__ == "__main__":
    main()
