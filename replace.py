"""
replacement.py
Component B: Desktop GUI SQL Conversion Tool (Tkinter + SQLGlot AST Engine)
Packagable into standalone .exe via PyInstaller
"""

import sys
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Dict, Tuple, List, Optional

import pandas as pd
import sqlglot
from sqlglot import exp

DIALECT = "databricks"
PLACEHOLDER_PATTERN = re.compile(r"(\$[\(\{][a-zA-Z0-9_\.\-]+[\)\}]|\$[a-zA-Z0-9_]+)")


class ContextualSQLTransformer:
    """Transforms SQL scripts with context-aware column and alias resolution."""

    def __init__(self, table_map: Dict[str, str], col_map: Dict[Tuple[str, str], str]):
        # table_map: { "claims": "claim_header", "member": "member" }
        self.table_map = {k.lower(): v.lower() for k, v in table_map.items()}
        # col_map: { ("claims", "member_id"): "beneficiary_id", ("member", "member_id"): "member_id" }
        self.col_map = {(t.lower(), c.lower()): v.lower() for (t, c), v in col_map.items()}

    def convert(self, sql_text: str) -> Tuple[str, Dict[str, int], List[str]]:
        stats = {"tables_mapped": 0, "columns_mapped": 0, "unmapped_tables": 0}
        warnings = []

        if not sql_text.strip():
            return "", stats, ["Input SQL is empty."]

        # 1. Protect schema placeholders
        ph_map = {}
        counter = 0

        def _sub_ph(m: re.Match) -> str:
            nonlocal counter
            raw = m.group(0)
            if raw not in ph_map:
                counter += 1
                ph_map[raw] = f"temp_sch_{counter}"
            return ph_map[raw]

        clean_sql = PLACEHOLDER_PATTERN.sub(_sub_ph, sql_text)

        # 2. Parse leniently
        try:
            statements = [s for s in sqlglot.parse(clean_sql, read=DIALECT, error_level=sqlglot.ErrorLevel.IGNORE) if s is not None]
        except Exception as e:
            return "", stats, [f"AST Parse Failure: {str(e)}"]

        converted_statements = []

        for stmt in statements:
            local_ctes = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE) if c.alias_or_name}
            local_creates = set()
            if isinstance(stmt, exp.Create):
                tn = stmt.this
                if isinstance(tn, exp.Schema):
                    tn = tn.this
                if isinstance(tn, exp.Table):
                    local_creates.add(tn.name.lower())

            # Scope alias -> original source table name
            alias_to_src_table: Dict[str, str] = {}
            for tbl in stmt.find_all(exp.Table):
                t_name = tbl.name.lower()
                alias = tbl.alias.lower() if tbl.alias else t_name
                alias_to_src_table[alias] = t_name

            # Transform Tables (c.claims -> c.claim_header)
            def _transform_table(node):
                if isinstance(node, exp.Table):
                    t_name = node.name.lower()
                    if t_name in local_ctes or t_name in local_creates:
                        return node
                    if t_name in self.table_map:
                        node.set("this", exp.to_identifier(self.table_map[t_name]))
                        stats["tables_mapped"] += 1
                    else:
                        stats["unmapped_tables"] += 1
                        warnings.append(f"Unmapped table: '{t_name}'")
                return node

            stmt = stmt.transform(_transform_table)

            # Transform Columns based on originating table
            def _transform_column(node):
                if isinstance(node, exp.Column):
                    c_name = node.name.lower()
                    t_qual = node.table.lower() if node.table else None
                    target_col = None

                    if t_qual:
                        # Find the source table that this alias points to
                        orig_src_table = alias_to_src_table.get(t_qual, t_qual)
                        target_col = self.col_map.get((orig_src_table, c_name))
                    else:
                        # Unqualified: check across all tables in the query
                        ext_tables = [t for t in alias_to_src_table.values() if t not in local_ctes and t not in local_creates]
                        candidates = [self.col_map[(t, c_name)] for t in ext_tables if (t, c_name) in self.col_map]
                        candidates = list(set(candidates))
                        if len(candidates) == 1:
                            target_col = candidates[0]
                        elif len(candidates) > 1:
                            warnings.append(f"Ambiguous column '{c_name}' maps to multiple targets: {candidates}. Left unchanged.")

                    if target_col:
                        node.set("this", exp.to_identifier(target_col))
                        stats["columns_mapped"] += 1

                return node

            stmt = stmt.transform(_transform_column)
            converted_statements.append(stmt.sql(dialect=DIALECT, pretty=True))

        out_sql = "\n\n".join(converted_statements)

        # 3. Restore schema placeholders
        for raw, temp_id in ph_map.items():
            out_sql = re.sub(rf"\b{re.escape(temp_id)}\b", raw, out_sql)

        return out_sql, stats, warnings


class ConverterApp(tk.Tk):
    """Desktop GUI."""

    def __init__(self):
        super().__init__()
        self.title("SQL Concept Conversion Tool")
        self.geometry("1050x700")
        self.minsize(850, 550)

        self.table_map: Dict[str, str] = {}
        self.col_map: Dict[Tuple[str, str], str] = {}
        self.workbook_loaded = False

        self._init_theme()
        self._build_widgets()

    def _init_theme(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Bold.TLabel", font=("Segoe UI", 9, "bold"))
        self.style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"))

    def _build_widgets(self):
        top = ttk.LabelFrame(self, text=" Mapping Configuration ", padding=8)
        top.pack(fill=tk.X, padx=10, pady=5)

        btn_load = ttk.Button(top, text="Load Mapping Workbook...", command=self.load_workbook)
        btn_load.grid(row=0, column=0, padx=5, pady=4, sticky=tk.W)

        self.lbl_file = ttk.Label(top, text="No workbook loaded.", foreground="#666")
        self.lbl_file.grid(row=0, column=1, columnspan=3, padx=5, pady=4, sticky=tk.W)

        ttk.Label(top, text="Source Pod:", style="Bold.TLabel").grid(row=1, column=0, padx=5, pady=4, sticky=tk.W)
        self.combo_src = ttk.Combobox(top, state="readonly", width=25)
        self.combo_src.grid(row=1, column=1, padx=5, pady=4, sticky=tk.W)

        ttk.Label(top, text="Target Pod:", style="Bold.TLabel").grid(row=1, column=2, padx=5, pady=4, sticky=tk.W)
        self.combo_tgt = ttk.Combobox(top, state="readonly", width=25)
        self.combo_tgt.grid(row=1, column=3, padx=5, pady=4, sticky=tk.W)

        panes = ttk.Frame(self, padding=5)
        panes.pack(fill=tk.BOTH, expand=True, padx=8)

        left_frame = ttk.LabelFrame(panes, text=" Source SQL (Editable) ", padding=4)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self.txt_source = tk.Text(left_frame, wrap=tk.NONE, font=("Consolas", 10), undo=True)
        s_scroll_y = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.txt_source.yview)
        s_scroll_x = ttk.Scrollbar(left_frame, orient=tk.HORIZONTAL, command=self.txt_source.xview)
        self.txt_source.configure(yscrollcommand=s_scroll_y.set, xscrollcommand=s_scroll_x.set)
        s_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        s_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_source.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_frame = ttk.LabelFrame(panes, text=" Converted SQL (Editable) ", padding=4)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4)

        self.txt_target = tk.Text(right_frame, wrap=tk.NONE, font=("Consolas", 10), undo=True)
        t_scroll_y = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.txt_target.yview)
        t_scroll_x = ttk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.txt_target.xview)
        self.txt_target.configure(yscrollcommand=t_scroll_y.set, xscrollcommand=t_scroll_x.set)
        t_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        t_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_target.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill=tk.X, padx=10)

        btn_run = ttk.Button(bar, text="▶ Convert SQL", style="Primary.TButton", command=self.execute_conversion)
        btn_run.pack(side=tk.LEFT, padx=3)

        btn_clear = ttk.Button(bar, text="Clear", command=self.clear_all)
        btn_clear.pack(side=tk.LEFT, padx=3)

        btn_copy = ttk.Button(bar, text="Copy Output", command=self.copy_output)
        btn_copy.pack(side=tk.RIGHT, padx=3)

        btn_save = ttk.Button(bar, text="Save SQL...", command=self.save_output)
        btn_save.pack(side=tk.RIGHT, padx=3)

        bottom = ttk.LabelFrame(self, text=" Status & Conversion Diagnostics ", padding=5)
        bottom.pack(fill=tk.X, padx=10, pady=5)

        self.txt_log = tk.Text(bottom, height=4, font=("Segoe UI", 9), wrap=tk.WORD)
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        self.txt_log.insert(tk.END, "Ready. Load an Excel workbook generated by similarity.py to start.")
        self.txt_log.configure(state=tk.DISABLED)

    def log(self, msg: str, reset: bool = False):
        self.txt_log.configure(state=tk.NORMAL)
        if reset:
            self.txt_log.delete("1.0", tk.END)
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.configure(state=tk.DISABLED)

    def load_workbook(self):
        f = filedialog.askopenfilename(title="Open Mapping Excel", filetypes=[("Excel Files", "*.xlsx *.xls")])
        if not f:
            return
        try:
            excel_path = Path(f)
            xls = pd.ExcelFile(excel_path)
            sheets = xls.sheet_names

            tbl_sheet = "Table_Mappings" if "Table_Mappings" in sheets else sheets[0]
            dict_sheet = "Mapping_Dictionary" if "Mapping_Dictionary" in sheets else (sheets[1] if len(sheets) > 1 else sheets[0])

            df_tbl = pd.read_excel(excel_path, sheet_name=tbl_sheet)
            df_dict = pd.read_excel(excel_path, sheet_name=dict_sheet)

            self.combo_src["values"] = [str(df_tbl.columns[0]).strip()]
            self.combo_src.current(0)
            self.combo_tgt["values"] = [str(df_tbl.columns[1]).strip()]
            self.combo_tgt.current(0)

            self.table_map = {}
            for _, r in df_tbl.iterrows():
                s = str(r.iloc[0]).strip().lower()
                t = str(r.iloc[1]).strip().lower()
                if s and t and s != "nan" and t != "nan":
                    self.table_map[s.split(".")[-1]] = t.split(".")[-1]

            # Contextual column mappings: (Source_Table, Source_Column) -> Target_Column
            self.col_map = {}
            for _, r in df_dict.iterrows():
                st = str(r["Source_Table"]).strip().lower()
                sc = str(r["Source_Column"]).strip().lower()
                tc = str(r["Target_Column"]).strip().lower()
                if st and sc and tc and tc != "nan":
                    self.col_map[(st, sc)] = tc

            self.workbook_loaded = True
            self.lbl_file.configure(
                text=f"{excel_path.name} ({len(self.table_map)} tables, {len(self.col_map)} contextual column rules)",
                foreground="#0b6623"
            )
            self.log(f"Successfully loaded {excel_path.name}.", reset=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Excel:\n{str(e)}")
            self.log(f"Load error: {str(e)}")

    def execute_conversion(self):
        if not self.workbook_loaded:
            messagebox.showwarning("Warning", "Please load a mapping Excel workbook first.")
            return

        sql_in = self.txt_source.get("1.0", tk.END).strip()
        if not sql_in:
            messagebox.showwarning("Warning", "Source SQL area is empty.")
            return

        transformer = ContextualSQLTransformer(self.table_map, self.col_map)
        converted, stats, warnings = transformer.convert(sql_in)

        self.txt_target.delete("1.0", tk.END)
        self.txt_target.insert(tk.END, converted)

        self.log("=== Conversion Complete ===", reset=True)
        self.log(f"• Tables Mapped: {stats['tables_mapped']} | Contextual Columns Mapped: {stats['columns_mapped']}")
        if warnings:
            self.log(f"Diagnostics ({len(warnings)}):")
            for w in warnings:
                self.log(f"  [!] {w}")

    def clear_all(self):
        self.txt_source.delete("1.0", tk.END)
        self.txt_target.delete("1.0", tk.END)
        self.log("Fields cleared.")

    def copy_output(self):
        out = self.txt_target.get("1.0", tk.END).strip()
        if out:
            self.clipboard_clear()
            self.clipboard_append(out)
            messagebox.showinfo("Copied", "Converted SQL copied to clipboard.")

    def save_output(self):
        out = self.txt_target.get("1.0", tk.END).strip()
        if not out:
            return
        f = filedialog.asksaveasfilename(defaultextension=".sql", filetypes=[("SQL Files", "*.sql")])
        if f:
            Path(f).write_text(out, encoding="utf-8")
            messagebox.showinfo("Saved", f"Saved to {Path(f).name}")


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()