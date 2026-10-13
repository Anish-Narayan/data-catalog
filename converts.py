"""
sql_converter_app.py
Component B: SQL Conversion Desktop Application (Tkinter GUI + SQLGlot AST Engine)
"""

import re
import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Dict, Tuple, Set, Optional

import pandas as pd
import sqlglot
from sqlglot import exp

DIALECT = "databricks"


class ASTTransformationEngine:
    """Transforms SQL scripts from Source Pod dialect/schema to Target Pod dialect/schema."""

    SCHEMA_REGEX = re.compile(r"\$\(([a-zA-Z0-9_\.]+)\)")

    def __init__(self, table_mapping: Dict[str, str], column_mapping: Dict[Tuple[str, str], str]):
        # table_mapping: { "claims": "claim_header" }
        self.table_mapping = {k.lower(): v.lower() for k, v in table_mapping.items()}
        # column_mapping: { ("claims", "member_id"): "beneficiary_id" }
        self.column_mapping = {(t.lower(), c.lower()): v.lower() for (t, c), v in column_mapping.items()}

    def convert(self, source_sql: str) -> Tuple[str, Dict[str, int], list]:
        stats = {
            "tables_mapped": 0,
            "columns_mapped": 0,
            "unmapped_tables": 0,
            "unmapped_columns": 0
        }
        warnings = []

        if not source_sql.strip():
            return "", stats, ["Input SQL is empty."]

        # 1. Protect schema placeholders
        placeholder_map = {}
        temp_counter = 0

        def _sub_ph(match: re.Match) -> str:
            nonlocal temp_counter
            ph = match.group(0)
            if ph not in placeholder_map:
                temp_counter += 1
                placeholder_map[ph] = f"tempsch_{temp_counter}"
            return placeholder_map[ph]

        safe_sql = self.SCHEMA_REGEX.sub(_sub_ph, source_sql)

        # 2. Parse into AST
        try:
            statements = [s for s in sqlglot.parse(safe_sql, read=DIALECT) if s is not None]
        except Exception as e:
            return "", stats, [f"Critical AST Parse Error: {str(e)}"]

        converted_statements = []

        for statement in statements:
            # Track local CTEs and created tables to avoid renaming them
            local_ctes = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE) if cte.alias_or_name}
            local_creates = set()
            if isinstance(statement, exp.Create):
                schema_node = statement.this
                tbl_node = schema_node.this if isinstance(schema_node, exp.Schema) else schema_node
                if isinstance(tbl_node, exp.Table):
                    local_creates.add(tbl_node.name.lower())

            # Scope alias -> original table name
            alias_to_table: Dict[str, str] = {}
            for tbl in statement.find_all(exp.Table):
                t_name = tbl.name.lower()
                alias = tbl.alias.lower() if tbl.alias else t_name
                alias_to_table[alias] = t_name

            # Transform Tables
            def transform_table(node):
                if isinstance(node, exp.Table):
                    t_name = node.name.lower()
                    if t_name in local_ctes or t_name in local_creates:
                        return node  # Do not touch internal CTE or created tables

                    if t_name in self.table_mapping:
                        target_tbl = self.table_mapping[t_name]
                        node.set("this", exp.to_identifier(target_tbl))
                        stats["tables_mapped"] += 1
                    else:
                        stats["unmapped_tables"] += 1
                        warnings.append(f"Unmapped external table reference: '{t_name}'")
                return node

            statement = statement.transform(transform_table)

            # Transform Columns in context
            def transform_column(node):
                if isinstance(node, exp.Column):
                    c_name = node.name.lower()
                    t_qualifier = node.table.lower() if node.table else None

                    mapped_target_col = None
                    if t_qualifier:
                        orig_table = alias_to_table.get(t_qualifier, t_qualifier)
                        if (orig_table, c_name) in self.column_mapping:
                            mapped_target_col = self.column_mapping[(orig_table, c_name)]
                    else:
                        # Unqualified column: search uniquely among tables in current query
                        candidate_tables = [t for t in alias_to_table.values() if t not in local_ctes]
                        matches = [self.column_mapping[(t, c_name)] for t in candidate_tables if (t, c_name) in self.column_mapping]
                        if len(matches) == 1:
                            mapped_target_col = matches[0]
                        elif len(matches) > 1:
                            warnings.append(f"Ambiguous column reference '{c_name}' matches multiple tables. Kept unchanged.")

                    if mapped_target_col:
                        node.set("this", exp.to_identifier(mapped_target_col))
                        stats["columns_mapped"] += 1
                    else:
                        stats["unmapped_columns"] += 1

                return node

            statement = statement.transform(transform_column)
            converted_statements.append(statement.sql(dialect=DIALECT, pretty=True))

        result_sql = "\n\n".join(converted_statements)

        # 3. Restore schema placeholders
        for orig_ph, temp_id in placeholder_map.items():
            result_sql = re.sub(rf"\b{re.escape(temp_id)}\b", orig_ph, result_sql)

        return result_sql, stats, warnings


class SQLConverterGUI(tk.Tk):
    """Clean desktop user interface built with Tkinter."""

    def __init__(self):
        super().__init__()
        self.title("SQL Concept Cross-Pollination & Conversion Tool")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self.table_mappings: Dict[str, str] = {}
        self.column_mappings: Dict[Tuple[str, str], str] = {}
        self.workbook_loaded = False

        self._configure_styles()
        self._build_ui()

    def _configure_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))
        self.style.configure("Status.TLabel", font=("Segoe UI", 9))
        self.style.configure("Action.TButton", font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        # Top Panel: File Upload and Pod Selection
        top_frame = ttk.LabelFrame(self, text=" Configuration & Mapping Model ", padding=10)
        top_frame.pack(fill=tk.X, padx=12, pady=6)

        btn_browse = ttk.Button(top_frame, text="Load Mapping Workbook...", command=self.load_workbook)
        btn_browse.grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)

        self.lbl_file = ttk.Label(top_frame, text="No mapping workbook selected.", foreground="#555")
        self.lbl_file.grid(row=0, column=1, columnspan=3, padx=5, pady=2, sticky=tk.W)

        ttk.Label(top_frame, text="Source Pod:", style="Header.TLabel").grid(row=1, column=0, padx=5, pady=6, sticky=tk.W)
        self.combo_source = ttk.Combobox(top_frame, state="readonly", width=25)
        self.combo_source.grid(row=1, column=1, padx=5, pady=6, sticky=tk.W)

        ttk.Label(top_frame, text="Target Pod:", style="Header.TLabel").grid(row=1, column=2, padx=5, pady=6, sticky=tk.W)
        self.combo_target = ttk.Combobox(top_frame, state="readonly", width=25)
        self.combo_target.grid(row=1, column=3, padx=5, pady=6, sticky=tk.W)

        # Center Panel: Side-by-Side SQL Editors
        editors_frame = ttk.Frame(self, padding=8)
        editors_frame.pack(fill=tk.BOTH, expand=True, padx=8)

        # Left: Source SQL
        left_box = ttk.LabelFrame(editors_frame, text=" Source SQL (Editable) ", padding=5)
        left_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self.txt_source = tk.Text(left_box, wrap=tk.NONE, font=("Consolas", 10), undo=True)
        src_scroll_y = ttk.Scrollbar(left_box, orient=tk.VERTICAL, command=self.txt_source.yview)
        src_scroll_x = ttk.Scrollbar(left_box, orient=tk.HORIZONTAL, command=self.txt_source.xview)
        self.txt_source.configure(yscrollcommand=src_scroll_y.set, xscrollcommand=src_scroll_x.set)

        src_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        src_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_source.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right: Target SQL
        right_box = ttk.LabelFrame(editors_frame, text=" Converted SQL (Editable) ", padding=5)
        right_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4)

        self.txt_target = tk.Text(right_box, wrap=tk.NONE, font=("Consolas", 10), undo=True)
        tgt_scroll_y = ttk.Scrollbar(right_box, orient=tk.VERTICAL, command=self.txt_target.yview)
        tgt_scroll_x = ttk.Scrollbar(right_box, orient=tk.HORIZONTAL, command=self.txt_target.xview)
        self.txt_target.configure(yscrollcommand=tgt_scroll_y.set, xscrollcommand=tgt_scroll_x.set)

        tgt_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tgt_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_target.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Action Toolbar
        action_bar = ttk.Frame(self, padding=6)
        action_bar.pack(fill=tk.X, padx=12)

        btn_convert = ttk.Button(action_bar, text="▶ Convert SQL", style="Action.TButton", command=self.run_conversion)
        btn_convert.pack(side=tk.LEFT, padx=4)

        btn_clear = ttk.Button(action_bar, text="Clear", command=self.clear_fields)
        btn_clear.pack(side=tk.LEFT, padx=4)

        btn_copy = ttk.Button(action_bar, text="Copy Output", command=self.copy_output)
        btn_copy.pack(side=tk.RIGHT, padx=4)

        btn_save = ttk.Button(action_bar, text="Save SQL As...", command=self.save_output)
        btn_save.pack(side=tk.RIGHT, padx=4)

        # Status & Warning Console
        status_box = ttk.LabelFrame(self, text=" Conversion Summary & Diagnostic Log ", padding=6)
        status_box.pack(fill=tk.X, padx=12, pady=6)

        self.txt_status = tk.Text(status_box, height=5, font=("Segoe UI", 9), wrap=tk.WORD)
        self.txt_status.pack(fill=tk.BOTH, expand=True)
        self.txt_status.insert(tk.END, "Ready. Load an Excel mapping workbook to begin.")
        self.txt_status.configure(state=tk.DISABLED)

    def log(self, text: str, clear: bool = False):
        self.txt_status.configure(state=tk.NORMAL)
        if clear:
            self.txt_status.delete("1.0", tk.END)
        self.txt_status.insert(tk.END, text + "\n")
        self.txt_status.see(tk.END)
        self.txt_status.configure(state=tk.DISABLED)

    def load_workbook(self):
        file_path = filedialog.askopenfilename(
            title="Select Mapping Workbook",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not file_path:
            return

        try:
            excel_path = Path(file_path)
            xls = pd.ExcelFile(excel_path)
            
            # Identify sheets
            sheet_names = xls.sheet_names
            tbl_sheet = "Table_Mappings" if "Table_Mappings" in sheet_names else sheet_names[0]
            dict_sheet = "Mapping_Dictionary" if "Mapping_Dictionary" in sheet_names else (sheet_names[1] if len(sheet_names) > 1 else sheet_names[0])

            tbl_df = pd.read_excel(excel_path, sheet_name=tbl_sheet)
            dict_df = pd.read_excel(excel_path, sheet_name=dict_sheet)

            # Dropdown labels based on header names
            source_label = str(tbl_df.columns[0]).strip()
            target_label = str(tbl_df.columns[1]).strip()

            self.combo_source["values"] = [source_label]
            self.combo_source.current(0)
            self.combo_target["values"] = [target_label]
            self.combo_target.current(0)

            # Populate tables
            self.table_mappings = {}
            for _, r in tbl_df.iterrows():
                s = str(r[0]).strip().lower()
                t = str(r[1]).strip().lower()
                if s and t and s != "nan" and t != "nan":
                    self.table_mappings[s.split(".")[-1]] = t.split(".")[-1]

            # Populate columns
            self.column_mappings = {}
            if "Source_Pod_Table" in dict_df.columns:
                for _, r in dict_df.iterrows():
                    st = str(r["Source_Pod_Table"]).strip().lower()
                    sc = str(r["Source_Pod_Column"]).strip().lower()
                    tc = str(r["Target_Pod_Column"]).strip().lower()
                    if st and sc and tc and tc != "nan":
                        self.column_mappings[(st, sc)] = tc
            else:
                # Fallback to column indices if headers differ
                for _, r in dict_df.iterrows():
                    st = str(r.iloc[0]).strip().lower()
                    sc = str(r.iloc[1]).strip().lower()
                    tc = str(r.iloc[3]).strip().lower()
                    if st and sc and tc and tc != "nan":
                        self.column_mappings[(st, sc)] = tc

            self.workbook_loaded = True
            self.lbl_file.config(text=f"{excel_path.name} (Loaded: {len(self.table_mappings)} tables, {len(self.column_mappings)} columns)", foreground="#0b6623")
            self.log(f"Workbook '{excel_path.name}' loaded successfully.", clear=True)

        except Exception as e:
            messagebox.showerror("Workbook Read Error", f"Failed to load Excel workbook:\n{str(e)}")
            self.log(f"Error loading workbook: {str(e)}")

    def run_conversion(self):
        if not self.workbook_loaded:
            messagebox.showwarning("Prerequisite Missing", "Please load a mapping Excel workbook first.")
            return

        source_sql = self.txt_source.get("1.0", tk.END).strip()
        if not source_sql:
            messagebox.showwarning("Input Required", "Please paste or enter SQL into the Source SQL area.")
            return

        engine = ASTTransformationEngine(self.table_mappings, self.column_mappings)
        converted_sql, stats, warnings = engine.convert(source_sql)

        if not converted_sql and warnings:
            self.log(f"Conversion failed:\n" + "\n".join(warnings), clear=True)
            return

        self.txt_target.delete("1.0", tk.END)
        self.txt_target.insert(tk.END, converted_sql)

        # Log summary statistics
        self.log(f"=== Conversion Completed Successfully ===", clear=True)
        self.log(f"• Tables Mapped: {stats['tables_mapped']}")
        self.log(f"• Columns Mapped: {stats['columns_mapped']}")
        self.log(f"• Unmapped Table References: {stats['unmapped_tables']}")
        self.log(f"• Unmapped Column References: {stats['unmapped_columns']}")
        if warnings:
            self.log(f"\nDiagnostics & Warnings ({len(warnings)}):")
            for w in warnings:
                self.log(f"  [WARN] {w}")

    def clear_fields(self):
        self.txt_source.delete("1.0", tk.END)
        self.txt_target.delete("1.0", tk.END)
        self.log("Editors cleared.")

    def copy_output(self):
        target_text = self.txt_target.get("1.0", tk.END).strip()
        if target_text:
            self.clipboard_clear()
            self.clipboard_append(target_text)
            messagebox.showinfo("Clipboard", "Converted SQL copied to clipboard.")
        else:
            messagebox.showwarning("Clipboard", "Target SQL area is empty.")

    def save_output(self):
        target_text = self.txt_target.get("1.0", tk.END).strip()
        if not target_text:
            messagebox.showwarning("Save Error", "Target SQL area is empty.")
            return

        out_path = filedialog.asksaveasfilename(
            defaultextension=".sql",
            filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
            title="Save Converted SQL"
        )
        if out_path:
            Path(out_path).write_text(target_text, encoding="utf-8")
            messagebox.showinfo("Saved", f"SQL saved to {Path(out_path).name}")


if __name__ == "__main__":
    app = SQLConverterGUI()
    app.mainloop()