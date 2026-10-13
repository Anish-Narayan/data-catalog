python sql_analysis_engine.py --source-sql source_pod.sql --target-sql target_pod.sql --table-map initial_table_map.xlsx --out-excel pod_cross_mappings.xlsx



python sql_converter_app.py


pyinstaller --noconfirm --onedir --windowed --name "SQL_Cross_Pollinator" --collect-all sqlglot sql_converter_app.py