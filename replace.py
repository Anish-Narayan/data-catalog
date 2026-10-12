
import re
import sys
from pathlib import Path

import pandas as pd
import sqlglot
from sqlglot import exp

DIALECT = "databricks"

# Matches concept headers such as --wrong_medication
HEADER = re.compile(r"^\s*--([A-Za-z0-9_]+)\s*$", re.MULTILINE)


def load_mappings(excel_path):
    df = pd.read_excel(excel_path, dtype=str)

    required = {"old_name", "new_name"}
    if not required.issubset(df.columns):
        raise ValueError(
            "Excel must contain columns named old_name and new_name"
        )

    mappings = {}
    for _, row in df.iterrows():
        old = str(row["old_name"]).strip()
        new = str(row["new_name"]).strip()

        if not old or old.lower() == "nan":
            continue
        if not new or new.lower() == "nan":
            raise ValueError(f"Missing replacement for {old}")

        if old in mappings and mappings[old] != new:
            raise ValueError(f"Conflicting mappings for {old}")

        mappings[old] = new

    return mappings


def replace_in_statement(statement, mappings):
    def transform(node):
        # Table names, including CREATE/DROP/INSERT targets
        if isinstance(node, exp.Table):
            old = node.name
            if old in mappings:
                node.set("this", exp.to_identifier(mappings[old]))

        # Column references, including SELECT, WHERE and JOIN expressions
        elif isinstance(node, exp.Column):
            old = node.name
            if old in mappings:
                node.set("this", exp.to_identifier(mappings[old]))

        # Column declarations, e.g. CREATE TABLE (... field_name STRING)
        elif isinstance(node, exp.ColumnDef):
            old = node.name
            if old in mappings:
                node.set("this", exp.to_identifier(mappings[old]))

        return node

    return statement.transform(transform)


def process_sql_section(section, mappings):
    if not section.strip():
        return section

    try:
        statements = sqlglot.parse(section, read=DIALECT)
    except Exception as exc:
        raise ValueError(
            "Could not parse a SQL section. No output was generated for "
            f"this run.\nParser error: {exc}\n"
            "Check the SQL dialect and syntax."
        ) from exc

    output = []
    for statement in statements:
        if statement is None:
            continue

        transformed = replace_in_statement(statement, mappings)
        output.append(
            transformed.sql(dialect=DIALECT, comments=True) + ";"
        )

    return "\n\n".join(output)


def main():
    if len(sys.argv) != 4:
        print(
            "Usage: python replace_sql_names.py "
            "input.sql mapping.xlsx output.sql"
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])
    excel_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    if not input_path.exists():
        sys.exit(f"SQL file not found: {input_path}")
    if not excel_path.exists():
        sys.exit(f"Excel file not found: {excel_path}")

    sql_text = input_path.read_text(encoding="utf-8-sig")
    mappings = load_mappings(excel_path)

    # Preserve concept header lines separately.
    headers = list(HEADER.finditer(sql_text))
    if not headers:
        sections = [(None, sql_text)]
    else:
        sections = []

        # Preserve any text before the first concept header.
        if sql_text[:headers[0].start()].strip():
            sections.append((None, sql_text[:headers[0].start()]))

        for i, match in enumerate(headers):
            end = headers[i + 1].start() if i + 1 < len(headers) else len(sql_text)
            sections.append((match.group(0), sql_text[match.end():end]))

    output_parts = []
    for header, body in sections:
        converted = process_sql_section(body, mappings)
        if header is not None:
            output_parts.append(header)
        output_parts.append(converted)

    output_path.write_text(
        "\n\n".join(part for part in output_parts if part is not None),
        encoding="utf-8",
    )

    print(f"Mappings loaded: {len(mappings)}")
    print(f"Output saved to: {output_path}")


if __name__ == "__main__":
    main()
