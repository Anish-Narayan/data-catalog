python similarity.py source.sql target.sql table_map.xlsx pod_mappings.xlsx


python sql_converter_app.py


pyinstaller --noconfirm --onedir --windowed --name "SQL_Cross_Pollinator" --collect-all sqlglot sql_converter_app.py